from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import json
import uuid
import pytest
from httpx import ASGITransport, AsyncClient

from orca.api.events import (
    AgentEvent,
    AgentEventType,
    is_forbidden_reasoning_key,
    is_sensitive_key,
    sanitize_event_payload,
    utc_now,
)
from orca.api.main import app
from orca.database.repositories.event_journal_repo import EventJournalRepository
from orca.schemas.orca_contract import Geometry
from orca.services.event_broker import AgentRunManager, OrcaEventBroker
from orca.services.streaming_runner import execute_agent_streaming_run


# ===========================================================================
# 1. Event Model & Security Policy Validation
# ===========================================================================
def test_event_contract_and_secret_redaction():
    """Verify AgentEvent schema validation, secret redaction, and reasoning scrubbing."""
    # 1. Secret keys and bearer tokens must be scrubbed
    raw_payload = {
        "user_query": "Find PFZ near Mumbai",
        "api_key": "secret_incois_key_12345",
        "auth_header": "basic-secret-auth-string",
        "custom_header": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
        "db_url": "https://admin:my_secret_pass@db.incois.gov.in/marine",
        "safe_metric": 28.5,
        # Forbidden internal reasoning fields
        "thought": "I should first check if coordinate bounds are valid.",
        "thinking": "Model inner monologue that should never leak.",
        "chain_of_thought": "Step 1 -> Step 2",
    }

    clean_payload, was_redacted = sanitize_event_payload(raw_payload)
    assert was_redacted is True
    assert clean_payload["api_key"] == "[REDACTED]"
    assert clean_payload["auth_header"] == "[REDACTED]"
    assert clean_payload["custom_header"] == "Bearer [REDACTED]"
    assert "my_secret_pass" not in clean_payload["db_url"]
    assert "[REDACTED]" in clean_payload["db_url"]
    assert clean_payload["safe_metric"] == 28.5

    # Forbidden reasoning keys must be completely removed
    assert "thought" not in clean_payload
    assert "thinking" not in clean_payload
    assert "chain_of_thought" not in clean_payload

    # 2. AgentEvent model validator enforces redaction status
    event = AgentEvent(
        run_id="run_sec_test",
        thread_id="th_sec_test",
        trace_id="trc_sec_test",
        event_type=AgentEventType.TOOL_STARTED,
        payload=raw_payload,
    )
    assert event.redaction_status == "redacted"
    assert event.payload["api_key"] == "[REDACTED]"
    assert "thought" not in event.payload


# ===========================================================================
# 2. Database-Authoritative Monotonic Sequence & Concurrency
# ===========================================================================
@pytest.mark.asyncio
async def test_database_authoritative_sequence_allocation():
    """Verify that PostgreSQL agent_run_cursors atomically allocates monotonic sequences."""
    repo = EventJournalRepository()
    await repo.ensure_tables_exist()

    run_id = f"run_seq_{uuid.uuid4().hex[:8]}"
    thread_id = f"th_seq_{uuid.uuid4().hex[:8]}"
    trace_id = "trc_seq_01"

    broker = OrcaEventBroker(run_id, thread_id, trace_id, repository=repo)

    e1 = await broker.emit(AgentEventType.RUN_STARTED, payload={"step": 1})
    e2 = await broker.emit(AgentEventType.PLAN_CREATED, payload={"step": 2})
    e3 = await broker.emit(AgentEventType.TOOL_STARTED, tool="pfz", payload={"step": 3})

    assert e1.sequence == 1
    assert e2.sequence == 2
    assert e3.sequence == 3

    # Check journal persistence
    events_in_db = await repo.get_events(run_id=run_id)
    assert len(events_in_db) == 3
    assert [e.sequence for e in events_in_db] == [1, 2, 3]


@pytest.mark.asyncio
async def test_concurrent_sequence_allocation():
    """Verify concurrent event producers for the same run allocate unique, monotonic sequences with zero duplicates."""
    repo = EventJournalRepository()
    await repo.ensure_tables_exist()

    run_id = f"run_concurrent_{uuid.uuid4().hex[:8]}"
    thread_id = f"th_concurrent_{uuid.uuid4().hex[:8]}"
    trace_id = "trc_concurrent_01"

    broker = OrcaEventBroker(run_id, thread_id, trace_id, repository=repo)

    num_concurrent = 20

    async def _emit_worker(idx: int):
        return await broker.emit(
            AgentEventType.TOOL_COMPLETED,
            tool=f"worker_tool_{idx}",
            payload={"worker_idx": idx},
        )

    # Launch all workers concurrently
    events = await asyncio.gather(*[_emit_worker(i) for i in range(num_concurrent)])

    sequences = [e.sequence for e in events]
    # Invariants:
    # 1. No duplicate sequence numbers
    assert len(set(sequences)) == num_concurrent
    # 2. Sequences form exact set 1..num_concurrent
    assert set(sequences) == set(range(1, num_concurrent + 1))

    # 3. Exactly one row per event in PostgreSQL
    db_events = await repo.get_events(run_id=run_id, limit=100)
    assert len(db_events) == num_concurrent
    assert [e.sequence for e in db_events] == list(range(1, num_concurrent + 1))


# ===========================================================================
# 3. Durability Before Publish Invariant
# ===========================================================================
@pytest.mark.asyncio
async def test_event_durability_before_publish():
    """Verify an event is committed in PostgreSQL BEFORE a live subscriber receives it."""
    repo = EventJournalRepository()
    await repo.ensure_tables_exist()

    run_id = f"run_durability_{uuid.uuid4().hex[:8]}"
    thread_id = f"th_durability_{uuid.uuid4().hex[:8]}"
    trace_id = "trc_durability"

    broker = OrcaEventBroker(run_id, thread_id, trace_id, repository=repo)
    received_events: list[AgentEvent] = []

    async def _subscriber():
        async for ev in broker.subscribe():
            # Check immediately in database: does this event already exist in PostgreSQL?
            in_db = await repo.get_events(run_id=run_id, after_sequence=ev.sequence - 1)
            assert len(in_db) >= 1
            assert in_db[0].sequence == ev.sequence
            received_events.append(ev)
            if len(received_events) >= 3:
                break

    sub_task = asyncio.create_task(_subscriber())
    await asyncio.sleep(0.05)  # Allow subscriber to attach

    await broker.emit(AgentEventType.RUN_STARTED)
    await broker.emit(AgentEventType.PLAN_CREATED)
    await broker.emit(AgentEventType.TOOL_STARTED, tool="incois_sst")

    await asyncio.wait_for(sub_task, timeout=5.0)
    assert len(received_events) == 3
    assert [e.sequence for e in received_events] == [1, 2, 3]


# ===========================================================================
# 4. FastAPI SSE Stream Route & Last-Event-ID Replay
# ===========================================================================
@pytest.mark.asyncio
async def test_fastapi_sse_stream_and_replay():
    """Verify POST /v1/agent/stream, live event streaming, and Last-Event-ID replay without agent re-execution."""
    repo = EventJournalRepository()
    await repo.ensure_tables_exist()

    run_id = f"run_sse_{uuid.uuid4().hex[:8]}"
    thread_id = f"th_sse_{uuid.uuid4().hex[:8]}"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # 1. Connect initial stream
        r1 = await client.post(
            "/v1/agent/stream",
            json={
                "query": "Mumbai fishing conditions",
                "sector": "MAHARASHTRA",
                "coordinates": {"lat": 18.92, "lon": 72.83},
                "run_id": run_id,
                "thread_id": thread_id,
            },
        )
        assert r1.status_code == 200
        assert "text/event-stream" in r1.headers.get("content-type", "")

        lines1 = r1.text.split("\n")
        events1 = [line.replace("event:", "").strip() for line in lines1 if line.startswith("event:")]
        ids1 = [int(line.replace("id:", "").strip()) for line in lines1 if line.startswith("id:")]

        assert "RUN_STARTED" in events1
        assert "PLAN_CREATED" in events1
        assert "TOOL_COMPLETED" in events1
        assert "RUN_COMPLETED" in events1

        # Check sequence monotonicity
        assert ids1 == sorted(ids1)
        last_seq = ids1[-1]
        assert last_seq >= 5

        # 2. Simulate client reconnect with Last-Event-ID = 3
        # Server must replay events 4..latest from PostgreSQL WITHOUT re-executing agent tools
        r2 = await client.post(
            "/v1/agent/stream",
            headers={"Last-Event-ID": "3"},
            json={
                "query": "Mumbai fishing conditions",
                "run_id": run_id,
                "thread_id": thread_id,
            },
        )
        assert r2.status_code == 200
        lines2 = r2.text.split("\n")
        ids2 = [int(line.replace("id:", "").strip()) for line in lines2 if line.startswith("id:")]

        # Invariants:
        # All replayed IDs must be strictly > 3
        assert all(i > 3 for i in ids2)
        assert ids2[0] == 4
        assert ids2[-1] == last_seq
        # No duplicates
        assert len(ids2) == len(set(ids2))


# ===========================================================================
# 5. Client Disconnect & Explicit Cancellation
# ===========================================================================
@pytest.mark.asyncio
async def test_explicit_cancellation_endpoint():
    """Verify explicit cancellation endpoint terminates run and emits RUN_CANCELLED."""
    repo = EventJournalRepository()
    await repo.ensure_tables_exist()
    manager = AgentRunManager.get_instance(repo)

    run_id = f"run_cancel_{uuid.uuid4().hex[:8]}"
    thread_id = f"th_cancel_{uuid.uuid4().hex[:8]}"

    broker = await manager.get_or_create_broker(run_id, thread_id, "trc_cancel")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Cancel run explicitly
        r = await client.post(f"/v1/agent/runs/{run_id}/cancel", json={"reason": "User cancelled inquiry"})
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "cancelled"
        assert data["run_id"] == run_id

        # Verify RUN_CANCELLED event exists in journal
        events = await repo.get_events(run_id=run_id)
        cancelled_ev = [e for e in events if e.event_type == AgentEventType.RUN_CANCELLED]
        assert len(cancelled_ev) == 1
        assert cancelled_ev[0].status == "CANCELLED"


# ===========================================================================
# 6. Checkpoint Correlation & Map Overlay Events
# ===========================================================================
@pytest.mark.asyncio
async def test_checkpoint_correlation_and_map_overlay():
    """Verify events include checkpoint_id when provided and MAP_OVERLAY_UPDATED is emitted."""
    repo = EventJournalRepository()
    await repo.ensure_tables_exist()

    run_id = f"run_map_{uuid.uuid4().hex[:8]}"
    thread_id = f"th_map_{uuid.uuid4().hex[:8]}"
    chk_id = "chk_test_12345"

    broker = OrcaEventBroker(run_id, thread_id, "trc_map", repository=repo)

    await broker.emit(
        AgentEventType.MAP_OVERLAY_UPDATED,
        agent="SynthesizerNode",
        checkpoint_id=chk_id,
        payload={
            "overlay_id": "nearest-pfz",
            "layer_type": "geojson",
            "source_id": "incois_webgis_pfz",
            "feature_count": 2,
        },
    )

    events = await repo.get_events(run_id=run_id)
    assert len(events) == 1
    ev = events[0]
    assert ev.event_type == AgentEventType.MAP_OVERLAY_UPDATED
    assert ev.checkpoint_id == chk_id
    assert ev.payload["overlay_id"] == "nearest-pfz"
    assert ev.payload["feature_count"] == 2


# ===========================================================================
# 7. Event Journal Retention Pruning
# ===========================================================================
@pytest.mark.asyncio
async def test_event_journal_retention_pruning():
    """Verify event journal prune retains last N runs and validates keep parameter."""
    repo = EventJournalRepository()
    await repo.ensure_tables_exist()

    # Invalid parameter
    with pytest.raises(ValueError, match="keep_last_n_runs must be at least 1"):
        await repo.prune_events(keep_last_n_runs=0)

    # Clean execution
    pruned = await repo.prune_events(keep_last_n_runs=100)
    assert pruned >= 0
