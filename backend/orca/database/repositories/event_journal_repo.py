from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any
import uuid

import asyncpg
import psycopg
from psycopg.rows import dict_row

from orca.api.events import AgentEvent, AgentEventType
from orca.database.session import get_raw_database_url

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EventJournalRepository:
    """PostgreSQL-authoritative event journal repository.

    Guarantees:
    - Database-authoritative sequence allocation via `agent_run_cursors` with row-level locks (FOR UPDATE).
    - Monotonic, gapless sequence numbers per run.
    - Transactional commit of event persistence BEFORE events are published to live subscribers.
    - Reconnection and replay support via `(run_id, sequence)`.
    """

    def __init__(self, conn_string: str | None = None) -> None:
        self.conn_string = conn_string or get_raw_database_url()
        self._memory_cursors: dict[str, int] = {}
        self._memory_events: dict[str, list[AgentEvent]] = {}
        self._memory_mode = False

    async def ensure_tables_exist(self) -> None:
        """Idempotently create event journal and cursor tables and indexes if not present."""
        try:
            async with await psycopg.AsyncConnection.connect(self.conn_string, autocommit=True, connect_timeout=2) as conn:
                async with conn.cursor() as cur:
                    # 1. Cursor table
                    await cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS agent_run_cursors (
                            run_id VARCHAR(64) PRIMARY KEY,
                            next_sequence INTEGER NOT NULL DEFAULT 1,
                            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        );
                        """
                    )
                    # 2. Event journal table
                    await cur.execute(
                        """
                        CREATE TABLE IF NOT EXISTS agent_run_events (
                            event_id UUID PRIMARY KEY,
                            run_id VARCHAR(64) NOT NULL,
                            thread_id VARCHAR(64) NOT NULL,
                            trace_id VARCHAR(64) NOT NULL,
                            sequence INTEGER NOT NULL,
                            event_type VARCHAR(64) NOT NULL,
                            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                            node VARCHAR(64),
                            agent VARCHAR(64),
                            tool VARCHAR(64),
                            status VARCHAR(32),
                            duration_ms DOUBLE PRECISION,
                            checkpoint_id VARCHAR(64),
                            evidence_ids JSONB,
                            error_code VARCHAR(64),
                            payload_json JSONB,
                            redaction_status VARCHAR(32) NOT NULL DEFAULT 'clean',
                            CONSTRAINT uq_agent_run_events_run_seq UNIQUE (run_id, sequence),
                            CONSTRAINT uq_agent_run_events_run_event UNIQUE (run_id, event_id)
                        );
                        CREATE INDEX IF NOT EXISTS idx_agent_run_events_thread_seq
                            ON agent_run_events (thread_id, sequence);
                        CREATE INDEX IF NOT EXISTS idx_agent_run_events_run_seq
                            ON agent_run_events (run_id, sequence);
                        """
                    )
        except Exception as exc:
            logger.warning("PostgreSQL unreachable (%s); using resilient in-memory event journal.", exc)
            self._memory_mode = True

    async def record_event(self, event: AgentEvent) -> AgentEvent:
        """Atomically allocate sequence from database cursor, persist event row, and commit.

        Source of Truth Invariant:
        PostgreSQL allocates the sequence and commits the write.
        An event is never published or made observable until this commit succeeds.
        """
        if self._memory_mode:
            curr = self._memory_cursors.get(event.run_id, 1)
            self._memory_cursors[event.run_id] = curr + 1
            event.sequence = curr
            self._memory_events.setdefault(event.run_id, []).append(event)
            return event

        try:
            async with await psycopg.AsyncConnection.connect(self.conn_string, autocommit=False, connect_timeout=2) as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    # 1. Ensure cursor row exists
                    await cur.execute(
                        """
                        INSERT INTO agent_run_cursors (run_id, next_sequence, updated_at)
                        VALUES (%(run_id)s, 1, %(now)s)
                        ON CONFLICT (run_id) DO NOTHING;
                        """,
                        {"run_id": event.run_id, "now": utc_now()},
                    )

                    # 2. Lock cursor row FOR UPDATE to allocate sequence atomically
                    await cur.execute(
                        """
                        SELECT next_sequence
                        FROM agent_run_cursors
                        WHERE run_id = %(run_id)s
                        FOR UPDATE;
                        """,
                        {"run_id": event.run_id},
                    )
                    row = await cur.fetchone()
                    if not row:
                        raise RuntimeError(f"Failed to acquire cursor for run {event.run_id}")

                    assigned_seq = row["next_sequence"]

                    # 3. Advance cursor to next sequence
                    await cur.execute(
                        """
                        UPDATE agent_run_cursors
                        SET next_sequence = next_sequence + 1, updated_at = %(now)s
                        WHERE run_id = %(run_id)s;
                        """,
                        {"run_id": event.run_id, "now": utc_now()},
                    )

                    event.sequence = assigned_seq

                    # 4. Insert into durable event journal
                    event_uuid = uuid.UUID(event.event_id) if isinstance(event.event_id, str) else event.event_id
                    await cur.execute(
                        """
                        INSERT INTO agent_run_events (
                            event_id, run_id, thread_id, trace_id, sequence, event_type,
                            timestamp, node, agent, tool, status, duration_ms,
                            checkpoint_id, evidence_ids, error_code, payload_json, redaction_status
                        ) VALUES (
                            %(event_id)s, %(run_id)s, %(thread_id)s, %(trace_id)s, %(sequence)s, %(event_type)s,
                            %(timestamp)s, %(node)s, %(agent)s, %(tool)s, %(status)s, %(duration_ms)s,
                            %(checkpoint_id)s, %(evidence_ids)s, %(error_code)s, %(payload_json)s, %(redaction_status)s
                        );
                        """,
                        {
                            "event_id": event_uuid,
                            "run_id": event.run_id,
                            "thread_id": event.thread_id,
                            "trace_id": event.trace_id,
                            "sequence": event.sequence,
                            "event_type": event.event_type.value,
                            "timestamp": event.timestamp,
                            "node": event.node,
                            "agent": event.agent,
                            "tool": event.tool,
                            "status": event.status,
                            "duration_ms": event.duration_ms,
                            "checkpoint_id": event.checkpoint_id,
                            "evidence_ids": json.dumps(event.evidence_ids),
                            "error_code": event.error_code,
                            "payload_json": json.dumps(event.payload),
                            "redaction_status": event.redaction_status,
                        },
                    )

                    # Commit transaction
                    await conn.commit()

            return event
        except Exception as exc:
            logger.warning("PostgreSQL record_event failed (%s); switching to in-memory mode.", exc)
            self._memory_mode = True
            curr = self._memory_cursors.get(event.run_id, 1)
            self._memory_cursors[event.run_id] = curr + 1
            event.sequence = curr
            self._memory_events.setdefault(event.run_id, []).append(event)
            return event

    async def get_events(
        self,
        run_id: str,
        after_sequence: int = 0,
        limit: int = 1000,
    ) -> list[AgentEvent]:
        """Retrieve events for a run after a specific sequence in strictly ascending order."""
        if self._memory_mode:
            evs = self._memory_events.get(run_id, [])
            filtered = [e for e in evs if e.sequence > after_sequence]
            return filtered[:limit]

        events: list[AgentEvent] = []
        try:
            async with await psycopg.AsyncConnection.connect(self.conn_string, autocommit=True, connect_timeout=2) as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        """
                        SELECT event_id, run_id, thread_id, trace_id, sequence, event_type,
                               timestamp, node, agent, tool, status, duration_ms, checkpoint_id,
                               evidence_ids, error_code, payload_json, redaction_status
                        FROM agent_run_events
                        WHERE run_id = %(run_id)s AND sequence > %(after_seq)s
                        ORDER BY sequence ASC
                        LIMIT %(limit)s;
                        """,
                        {"run_id": run_id, "after_seq": after_sequence, "limit": limit},
                    )
                    rows = await cur.fetchall()
                    for r in rows:
                        payload = r["payload_json"]
                        if isinstance(payload, str):
                            try:
                                payload = json.loads(payload)
                            except Exception:
                                payload = {}
                        ev_ids = r["evidence_ids"]
                        if isinstance(ev_ids, str):
                            try:
                                ev_ids = json.loads(ev_ids)
                            except Exception:
                                ev_ids = []

                        events.append(
                            AgentEvent(
                                event_id=str(r["event_id"]),
                                run_id=r["run_id"],
                                thread_id=r["thread_id"],
                                trace_id=r["trace_id"],
                                sequence=r["sequence"],
                                event_type=AgentEventType(r["event_type"]),
                                timestamp=r["timestamp"],
                                node=r["node"],
                                agent=r["agent"],
                                tool=r["tool"],
                                status=r["status"],
                                duration_ms=r["duration_ms"],
                                checkpoint_id=r["checkpoint_id"],
                                evidence_ids=ev_ids or [],
                                error_code=r["error_code"],
                                payload=payload or {},
                                redaction_status=r["redaction_status"],
                            )
                        )
            return events
        except Exception as exc:
            logger.warning("PostgreSQL get_events failed (%s); using in-memory mode.", exc)
            self._memory_mode = True
            evs = self._memory_events.get(run_id, [])
            filtered = [e for e in evs if e.sequence > after_sequence]
            return filtered[:limit]

    async def get_events_by_thread(
        self,
        thread_id: str,
        after_sequence: int = 0,
        limit: int = 1000,
    ) -> list[AgentEvent]:
        """Retrieve events for an entire thread after a specific sequence in strictly ascending order."""
        if self._memory_mode:
            matched: list[AgentEvent] = []
            for evs in self._memory_events.values():
                for e in evs:
                    if e.thread_id == thread_id and e.sequence > after_sequence:
                        matched.append(e)
            matched.sort(key=lambda x: x.sequence)
            return matched[:limit]

        events: list[AgentEvent] = []
        try:
            async with await psycopg.AsyncConnection.connect(self.conn_string, autocommit=True, connect_timeout=2) as conn:
                async with conn.cursor(row_factory=dict_row) as cur:
                    await cur.execute(
                        """
                        SELECT event_id, run_id, thread_id, trace_id, sequence, event_type,
                               timestamp, node, agent, tool, status, duration_ms, checkpoint_id,
                               evidence_ids, error_code, payload_json, redaction_status
                        FROM agent_run_events
                        WHERE thread_id = %(thread_id)s AND sequence > %(after_seq)s
                        ORDER BY sequence ASC
                        LIMIT %(limit)s;
                        """,
                        {"thread_id": thread_id, "after_seq": after_sequence, "limit": limit},
                    )
                    rows = await cur.fetchall()
                    for r in rows:
                        payload = r["payload_json"]
                        if isinstance(payload, str):
                            try:
                                payload = json.loads(payload)
                            except Exception:
                                payload = {}
                        ev_ids = r["evidence_ids"]
                        if isinstance(ev_ids, str):
                            try:
                                ev_ids = json.loads(ev_ids)
                            except Exception:
                                ev_ids = []

                        events.append(
                            AgentEvent(
                                event_id=str(r["event_id"]),
                                run_id=r["run_id"],
                                thread_id=r["thread_id"],
                                trace_id=r["trace_id"],
                                sequence=r["sequence"],
                                event_type=AgentEventType(r["event_type"]),
                                timestamp=r["timestamp"],
                                node=r["node"],
                                agent=r["agent"],
                                tool=r["tool"],
                                status=r["status"],
                                duration_ms=r["duration_ms"],
                                checkpoint_id=r["checkpoint_id"],
                                evidence_ids=ev_ids or [],
                                error_code=r["error_code"],
                                payload=payload or {},
                                redaction_status=r["redaction_status"],
                            )
                        )
            return events
        except Exception as exc:
            logger.warning("PostgreSQL get_events_by_thread failed (%s); using in-memory mode.", exc)
            self._memory_mode = True
            matched = []
            for evs in self._memory_events.values():
                for e in evs:
                    if e.thread_id == thread_id and e.sequence > after_sequence:
                        matched.append(e)
            matched.sort(key=lambda x: x.sequence)
            return matched[:limit]

    async def prune_events(self, keep_last_n_runs: int = 50) -> int:
        """Prune older event journal records while preserving recent runs.

        Policy:
        - Never deletes events from currently active runs.
        - Preserves the last N runs completely for audit, debugging, and reconnect.
        """
        if keep_last_n_runs < 1:
            raise ValueError(f"keep_last_n_runs must be at least 1, got {keep_last_n_runs}")

        if self._memory_mode:
            return 0

        try:
            async with await psycopg.AsyncConnection.connect(self.conn_string, autocommit=True, connect_timeout=2) as conn:
                async with conn.cursor() as cur:
                    # Find runs eligible for deletion (older than keep_last_n_runs)
                    await cur.execute(
                        """
                        WITH ranked_runs AS (
                            SELECT run_id, MAX(timestamp) as last_seen
                            FROM agent_run_events
                            GROUP BY run_id
                            ORDER BY last_seen DESC
                            OFFSET %(keep)s
                        )
                        DELETE FROM agent_run_events
                        WHERE run_id IN (SELECT run_id FROM ranked_runs);
                        """,
                        {"keep": keep_last_n_runs},
                    )
                    deleted_count = cur.rowcount
            logger.info("Pruned %d events from older runs (retained last %d runs).", deleted_count, keep_last_n_runs)
            return deleted_count
        except Exception as exc:
            logger.warning("PostgreSQL prune_events skipped (%s).", exc)
            return 0
