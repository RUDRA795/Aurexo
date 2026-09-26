from __future__ import annotations

import asyncio
from datetime import datetime
import json
import logging
from typing import Any, AsyncGenerator
import uuid

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel, Field

from orca.api.events import AgentEvent, AgentEventType, utc_now
from orca.database.repositories.event_journal_repo import EventJournalRepository
from orca.schemas.orca_contract import Geometry
from orca.services.event_broker import AgentRunManager, OrcaEventBroker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/agent", tags=["agent-streaming"])


class AgentStreamRequest(BaseModel):
    """Payload for initiating or attaching to an observable agent execution stream."""

    query: str = Field(default="Where is the nearest verified Potential Fishing Zone?")
    coordinates: Geometry | None = None
    sector: str | None = None
    thread_id: str | None = None
    run_id: str | None = None
    session_id: str | None = None


class CancelRunRequest(BaseModel):
    reason: str = Field(default="User requested cancellation")


@router.post("/runs/{run_id}/cancel")
async def cancel_agent_run(run_id: str, payload: CancelRunRequest | None = None) -> dict[str, Any]:
    """Explicitly cancel an active background agent execution run."""
    manager = AgentRunManager.get_instance()
    reason = payload.reason if payload else "User requested cancellation"
    cancelled = await manager.cancel_run(run_id, reason=reason)
    if not cancelled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run '{run_id}' not found or already completed.",
        )
    return {"status": "cancelled", "run_id": run_id, "reason": reason}


@router.get("/events/{run_id}")
async def get_run_events(run_id: str, after_sequence: int = 0) -> list[dict[str, Any]]:
    """Retrieve journaled events for an active or completed agent execution run."""
    manager = AgentRunManager.get_instance()
    repo = manager.repository
    try:
        events = await repo.get_events(run_id=run_id, after_sequence=after_sequence)
        return [ev.to_sse_dict() for ev in events]
    except Exception as exc:
        logger.warning("Could not retrieve events from DB for %s: %s", run_id, exc)
        return []


@router.post("/stream", response_class=EventSourceResponse)
async def stream_agent_execution(
    payload: AgentStreamRequest,
    request: Request,
    last_event_id: str | None = Header(None, alias="Last-Event-ID"),
) -> AsyncGenerator[ServerSentEvent, None]:
    """Execute or attach to an ORCA agent stream via Server-Sent Events.

    Features:
    - POST-based streaming with typed Pydantic payloads.
    - Automatic `Last-Event-ID` reconnection and journal replay without re-running agent tools.
    - PostgreSQL-authoritative monotonic event ordering.
    - Client disconnect does NOT cancel backend agent run.
    - Transport keepalive comments without burning sequence numbers.
    """
    manager = AgentRunManager.get_instance()
    repo = manager.repository
    await repo.ensure_tables_exist()

    # 1. Resolve run_id, thread_id, trace_id
    run_id = payload.run_id or f"run_{uuid.uuid4().hex[:12]}"
    thread_id = payload.thread_id or f"th_{uuid.uuid4().hex[:10]}"
    trace_id = f"trc_{uuid.uuid4().hex[:16]}"

    last_acked_seq = 0
    if last_event_id:
        try:
            last_acked_seq = int(last_event_id.strip())
        except ValueError:
            last_acked_seq = 0

    # 2. Obtain or register broker for live distribution
    broker = await manager.get_or_create_broker(
        run_id=run_id,
        thread_id=thread_id,
        trace_id=trace_id,
    )

    # 3. Synchronously register subscriber queue BEFORE launching task so no early events are dropped
    subscriber_queue = broker.create_subscriber_queue()

    # 4. Replay unacknowledged events from durable event journal
    replayed_events = await repo.get_events(run_id=run_id, after_sequence=last_acked_seq)
    highest_seq = last_acked_seq

    for ev in replayed_events:
        yield ServerSentEvent(
            event=ev.event_type.value,
            id=str(ev.sequence),
            data=ev.to_sse_dict(),
            retry=3000,
        )
        if ev.sequence > highest_seq:
            highest_seq = ev.sequence

    # If the run has already completed or failed in journal, finish immediately
    is_terminal = any(
        ev.event_type in (AgentEventType.RUN_COMPLETED, AgentEventType.RUN_FAILED, AgentEventType.RUN_CANCELLED)
        for ev in replayed_events
    )
    if is_terminal:
        broker.remove_subscriber_queue(subscriber_queue)
        return

    # 5. Check if background run execution is already active; launch if not
    handle = await manager.get_run_handle(run_id)
    if not handle or not handle.is_active:
        from orca.services.streaming_runner import execute_agent_streaming_run

        task = asyncio.create_task(
            execute_agent_streaming_run(
                broker=broker,
                query=payload.query,
                coordinates=payload.coordinates,
                sector=payload.sector,
                thread_id=thread_id,
                session_id=payload.session_id,
            )
        )
        await manager.register_run_task(run_id, task)

    # 6. Stream live committed events with keepalive comments and disconnect detection
    keepalive_interval = 15.0  # seconds

    try:
        while True:
            # Check client disconnect
            if await request.is_disconnected():
                logger.info("Client disconnected from run %s; agent execution continues in background.", run_id)
                break

            try:
                # Wait for next event or keepalive timeout
                event = await asyncio.wait_for(subscriber_queue.get(), timeout=keepalive_interval)
            except asyncio.TimeoutError:
                # Emit proxy keepalive comment (does NOT burn sequence numbers)
                yield ServerSentEvent(comment="keepalive")
                continue

            if event is None:
                break

            # Deduplication: avoid re-emitting events already replayed from journal
            if event.sequence <= highest_seq:
                continue

            highest_seq = event.sequence
            yield ServerSentEvent(
                event=event.event_type.value,
                id=str(event.sequence),
                data=event.to_sse_dict(),
                retry=3000,
            )

            if event.event_type in (
                AgentEventType.RUN_COMPLETED,
                AgentEventType.RUN_FAILED,
                AgentEventType.RUN_CANCELLED,
            ):
                break
    finally:
        broker.remove_subscriber_queue(subscriber_queue)
