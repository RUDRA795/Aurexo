from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
from typing import Any, AsyncGenerator
import uuid

from orca.api.events import AgentEvent, AgentEventType, utc_now
from orca.database.repositories.event_journal_repo import EventJournalRepository

logger = logging.getLogger(__name__)


class OrcaEventBroker:
    """Coordinates PostgreSQL-authoritative event durability with real-time SSE distribution.

    Invariants:
    - Sequence allocation is owned strictly by PostgreSQL (`agent_run_cursors`).
    - Every event is committed to `agent_run_events` BEFORE being published to subscriber queues.
    - Subscribers never observe uncommitted or phantom events.
    - Multi-worker and concurrent producer safe.
    """

    def __init__(
        self,
        run_id: str,
        thread_id: str,
        trace_id: str,
        repository: EventJournalRepository | None = None,
    ) -> None:
        self.run_id = run_id
        self.thread_id = thread_id
        self.trace_id = trace_id
        self.repository = repository or EventJournalRepository()

        self._subscribers: set[asyncio.Queue[AgentEvent | None]] = set()
        self._lock = asyncio.Lock()
        self._is_closed = False
        self._cancellation_event = asyncio.Event()
        self._cancellation_reason: str | None = None

    @property
    def is_cancelled(self) -> bool:
        return self._cancellation_event.is_set()

    @property
    def cancellation_reason(self) -> str | None:
        return self._cancellation_reason

    def request_cancellation(self, reason: str = "Client requested cancellation") -> None:
        """Signal explicit cancellation to the executing agent."""
        self._cancellation_reason = reason
        self._cancellation_event.set()
        logger.info("Cancellation requested for run %s: %s", self.run_id, reason)

    async def emit(
        self,
        event_type: AgentEventType,
        *,
        node: str | None = None,
        agent: str | None = None,
        tool: str | None = None,
        status: str | None = None,
        duration_ms: float | None = None,
        checkpoint_id: str | None = None,
        evidence_ids: list[str] | None = None,
        error_code: str | None = None,
        progress: float | None = None,
        payload: dict[str, Any] | None = None,
    ) -> AgentEvent:
        """Create, sanitize, durably persist, and publish an event to live subscribers."""
        event = AgentEvent(
            event_id=str(uuid.uuid4()),
            sequence=0,  # Assigned strictly by database cursor
            event_type=event_type,
            run_id=self.run_id,
            thread_id=self.thread_id,
            trace_id=self.trace_id,
            timestamp=utc_now(),
            node=node,
            agent=agent,
            tool=tool,
            status=status,
            duration_ms=duration_ms,
            checkpoint_id=checkpoint_id,
            evidence_ids=evidence_ids or [],
            error_code=error_code,
            progress=progress,
            payload=payload or {},
        )

        # 1. Authoritative DB sequence allocation and commit
        committed_event = await self.repository.record_event(event)

        # 2. Publish to live in-memory subscriber queues
        async with self._lock:
            dead_subscribers = set()
            for sub_q in self._subscribers:
                try:
                    sub_q.put_nowait(committed_event)
                except asyncio.QueueFull:
                    dead_subscribers.add(sub_q)
            self._subscribers.difference_update(dead_subscribers)

        return committed_event

    def create_subscriber_queue(self) -> asyncio.Queue[AgentEvent | None]:
        """Synchronously create and register a subscriber queue.

        Guarantees that events published after this call are enqueued immediately,
        preventing any race condition before an async loop begins.
        """
        queue: asyncio.Queue[AgentEvent | None] = asyncio.Queue(maxsize=500)
        self._subscribers.add(queue)
        return queue

    def remove_subscriber_queue(self, queue: asyncio.Queue[AgentEvent | None]) -> None:
        """Unregister a subscriber queue."""
        self._subscribers.discard(queue)

    async def subscribe(self) -> AsyncGenerator[AgentEvent, None]:
        """Subscribe to live committed events published by this broker."""
        queue = self.create_subscriber_queue()
        try:
            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
        finally:
            self.remove_subscriber_queue(queue)

    async def close(self) -> None:
        """Close the broker and notify active subscribers of completion."""
        async with self._lock:
            if self._is_closed:
                return
            self._is_closed = True
            for sub_q in self._subscribers:
                try:
                    sub_q.put_nowait(None)
                except Exception:
                    pass
            self._subscribers.clear()


class AgentRunHandle:
    """Manages active background execution for a specific run."""

    def __init__(
        self,
        run_id: str,
        thread_id: str,
        broker: OrcaEventBroker,
        task: asyncio.Task[Any] | None = None,
    ) -> None:
        self.run_id = run_id
        self.thread_id = thread_id
        self.broker = broker
        self.task = task
        self.created_at = utc_now()
        self.completed_at: datetime | None = None
        self.error: Exception | None = None

    @property
    def is_active(self) -> bool:
        if self.task is None:
            return False
        return not self.task.done()


class AgentRunManager:
    """Singleton run manager decoupling agent execution lifetime from HTTP connection lifetime.

    Key Architectural Guarantee:
    - Client network disconnect does NOT cancel or corrupt the background agent run.
    - Reconnecting clients re-attach to the durable journal and active event stream.
    - Explicit cancellation is distinct from network drops.
    """

    _instance: AgentRunManager | None = None

    def __init__(self, repository: EventJournalRepository | None = None) -> None:
        self.repository = repository or EventJournalRepository()
        self._runs: dict[str, AgentRunHandle] = {}
        self._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls, repository: EventJournalRepository | None = None) -> AgentRunManager:
        if cls._instance is None:
            cls._instance = AgentRunManager(repository)
        elif repository is not None:
            cls._instance.repository = repository
        return cls._instance

    async def get_or_create_broker(
        self,
        run_id: str,
        thread_id: str,
        trace_id: str,
    ) -> OrcaEventBroker:
        async with self._lock:
            if run_id in self._runs:
                return self._runs[run_id].broker
            broker = OrcaEventBroker(
                run_id=run_id,
                thread_id=thread_id,
                trace_id=trace_id,
                repository=self.repository,
            )
            self._runs[run_id] = AgentRunHandle(
                run_id=run_id,
                thread_id=thread_id,
                broker=broker,
            )
            return broker

    async def register_run_task(
        self,
        run_id: str,
        task: asyncio.Task[Any],
    ) -> None:
        async with self._lock:
            if run_id in self._runs:
                self._runs[run_id].task = task

    async def get_run_handle(self, run_id: str) -> AgentRunHandle | None:
        async with self._lock:
            return self._runs.get(run_id)

    async def cancel_run(self, run_id: str, reason: str = "Client requested cancellation") -> bool:
        """Explicitly request cancellation of a running agent execution."""
        handle = await self.get_run_handle(run_id)
        if not handle:
            return False

        handle.broker.request_cancellation(reason)
        if handle.task and not handle.task.done():
            handle.task.cancel()

        await handle.broker.emit(
            AgentEventType.RUN_CANCELLED,
            status="CANCELLED",
            error_code="CLIENT_CANCELLED",
            payload={"reason": reason},
        )
        await handle.broker.close()
        return True
