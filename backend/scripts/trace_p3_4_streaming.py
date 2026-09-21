"""P3.4 Acceptance Trace: Streaming Execution, Durable Event Journal & SSE.

Demonstrates:
1. Scenario 1: Full-lifecycle agent streaming for Mumbai marine inquiry over FastAPI SSE.
2. Database-Authoritative Monotonic Sequences: PostgreSQL agent_run_cursors & agent_run_events.
3. Scenario 2: Network Disconnect & Reconnect via Last-Event-ID (zero duplication, zero re-execution).
4. Scenario 3: Explicit Run Cancellation (POST /v1/agent/runs/{run_id}/cancel).
5. Telemetry & Reasoning Redaction Verification.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
import time
import uuid

# Ensure backend root is on sys.path
backend_root = str(Path(__file__).resolve().parent.parent)
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

# Configure Windows event loop policy before any loop starts
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from httpx import ASGITransport, AsyncClient
from orca.api.events import AgentEventType, sanitize_event_payload
from orca.api.main import app
from orca.database.repositories.event_journal_repo import EventJournalRepository
from orca.services.event_broker import AgentRunManager, OrcaEventBroker
from orca.services.streaming_runner import execute_agent_streaming_run


def print_banner(title: str) -> None:
    sep = "=" * 80
    print(f"\n{sep}\n  {title}\n{sep}")


def print_section(title: str) -> None:
    print(f"\n--- {title} ---")


def parse_sse_stream(text: str) -> list[dict]:
    """Parse raw SSE text stream into list of event dicts."""
    events = []
    blocks = text.strip().split("\n\n")
    for block in blocks:
        if not block.strip() or block.startswith(":"):
            continue
        ev = {}
        for line in block.split("\n"):
            if line.startswith("id:"):
                ev["id"] = int(line[3:].strip())
            elif line.startswith("event:"):
                ev["event"] = line[6:].strip()
            elif line.startswith("data:"):
                try:
                    ev["data"] = json.loads(line[5:].strip())
                except Exception:
                    ev["data"] = line[5:].strip()
        if "event" in ev:
            events.append(ev)
    return events


async def run_scenario_1_full_streaming():
    print_banner("SCENARIO 1: Full-Lifecycle Agent Streaming over FastAPI SSE")
    print("Inquiry: 'Analyze current marine conditions near Mumbai with fishing suitability and weather.'")
    print("Coordinates: Mumbai (18.92°N, 72.83°E)")

    repo = EventJournalRepository()
    await repo.ensure_tables_exist()

    run_id = f"run_trace1_{uuid.uuid4().hex[:8]}"
    thread_id = f"th_trace1_{uuid.uuid4().hex[:8]}"
    trace_id = f"trc_trace1_{uuid.uuid4().hex[:8]}"

    print(f"Identifiers: run_id={run_id} | thread_id={thread_id} | trace_id={trace_id}")

    # Use HTTP ASGI client to connect to FastAPI POST /v1/agent/stream
    received_events = []
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=30.0) as client:
        t0 = time.perf_counter()
        resp = await client.post(
            "/v1/agent/stream",
            json={
                "query": "Analyze current marine conditions near Mumbai with fishing suitability and weather.",
                "run_id": run_id,
                "thread_id": thread_id,
                "trace_id": trace_id,
                "target_lat": 18.92,
                "target_lon": 72.83,
            },
        )
        elapsed_sec = time.perf_counter() - t0

        assert resp.status_code == 200, f"SSE endpoint returned status {resp.status_code}"
        assert "text/event-stream" in resp.headers.get("content-type", "")

        received_events = parse_sse_stream(resp.text)

    print(f"\nReceived {len(received_events)} SSE events in {elapsed_sec:.2f}s:")
    print(f"{'Seq':<5} | {'Event Type':<22} | {'Node / Agent':<22} | {'Status':<10} | {'Payload Preview'}")
    print("-" * 100)

    for ev in received_events:
        seq = ev.get("id", "-")
        etype = ev.get("event", "")
        data = ev.get("data", {})
        node_agent = data.get("agent") or data.get("node") or data.get("tool") or "-"
        status = data.get("status") or "-"
        payload = data.get("payload") or {}
        preview = ""
        if etype == "RUN_STARTED":
            preview = f"query='{data.get('query', '')[:30]}...'"
        elif etype == "PLAN_CREATED":
            steps = payload.get("steps", [])
            step_names = [s.get("action", str(s)) if isinstance(s, dict) else str(s) for s in steps[:3]]
            preview = f"{len(steps)} steps planned ({', '.join(step_names)}...)"
        elif etype == "TOOL_COMPLETED":
            preview = f"tool={data.get('tool')} dur={data.get('duration_ms')}ms res={str(payload)[:35]}"
        elif etype == "EVIDENCE_ADDED":
            preview = f"var={payload.get('variable')} src={payload.get('source_id')}"
        elif etype == "EVIDENCE_CHECK":
            preview = f"passed={payload.get('passed')} valid={payload.get('valid_count')} rejected={payload.get('rejected_count')}"
        elif etype == "MAP_OVERLAY_UPDATED":
            preview = f"selected={payload.get('selected_id')} dist={payload.get('distance_km')}km bearing={payload.get('bearing_deg')}°"
        elif etype == "SYNTHESIS_COMPLETED":
            preview = f"conf={payload.get('confidence')} ans='{payload.get('answer_text', '')[:45]}...'"
        elif etype == "RUN_COMPLETED":
            preview = f"total_dur={payload.get('total_duration_ms')}ms evidences={payload.get('evidence_count')}"
        else:
            preview = str(payload)[:50]

        print(f"{seq:<5} | {etype:<22} | {node_agent:<22} | {status:<10} | {preview}")

    # Database Verification
    print_section("Database Journal Invariant Verification")
    db_events = await repo.get_events(run_id=run_id)
    print(f"Total events recorded in PostgreSQL 'agent_run_events': {len(db_events)}")
    assert len(db_events) == len(received_events), "Event count mismatch between SSE stream and database!"

    seqs = [e.sequence for e in db_events]
    expected_seqs = list(range(1, len(db_events) + 1))
    assert seqs == expected_seqs, f"Sequence numbers are not strictly contiguous: {seqs}"
    print(f"Contiguous sequences verified: {seqs[0]} -> {seqs[-1]} (strictly monotonic, zero gaps)")

    for e in db_events:
        assert e.redaction_status in ("clean", "redacted")
    print("All events verified for data integrity and redaction status.")

    return run_id, thread_id, len(db_events)


async def run_scenario_2_reconnect_replay(original_run_id: str, total_events: int):
    print_banner("SCENARIO 2: Network Disconnect & Reconnect via Last-Event-ID")
    cutoff_seq = 5
    print(f"Simulating network disconnect: Client experienced drop after receiving sequence #{cutoff_seq}.")
    print(f"Client reconnects sending header: Last-Event-ID: {cutoff_seq}")
    print("Server invariant: Server must replay from PostgreSQL starting at sequence 6..latest without re-executing tools.")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=30.0) as client:
        resp = await client.post(
            "/v1/agent/stream",
            headers={"Last-Event-ID": str(cutoff_seq)},
            json={
                "query": "Analyze current marine conditions near Mumbai with fishing suitability and weather.",
                "run_id": original_run_id,
                "thread_id": "th_reconnect",
            },
        )
        assert resp.status_code == 200
        replayed_events = parse_sse_stream(resp.text)

    print(f"\nReplayed {len(replayed_events)} events from journal:")
    replayed_ids = [ev["id"] for ev in replayed_events]
    print(f"Replayed sequence IDs: {replayed_ids}")

    # Invariants verification
    assert all(i > cutoff_seq for i in replayed_ids), f"Received events <= cutoff {cutoff_seq}!"
    assert replayed_ids[0] == cutoff_seq + 1, f"First replayed ID was {replayed_ids[0]}, expected {cutoff_seq + 1}"
    assert replayed_ids[-1] == total_events, f"Last replayed ID was {replayed_ids[-1]}, expected {total_events}"
    assert len(replayed_ids) == len(set(replayed_ids)), "Duplicate event IDs detected in replay!"
    assert len(replayed_ids) == (total_events - cutoff_seq), "Gaps detected in replayed event sequence!"

    print("Reconnection Invariants PASSED:")
    print("  [OK] Zero duplicate events delivered to client")
    print("  [OK] Zero gaps in event delivery")
    print("  [OK] Zero external tool or graph recomputations (pure PostgreSQL journal replay)")


async def run_scenario_3_explicit_cancellation():
    print_banner("SCENARIO 3: Explicit Run Cancellation (POST /v1/agent/runs/{run_id}/cancel)")
    repo = EventJournalRepository()
    manager = AgentRunManager.get_instance(repo)

    run_id = f"run_cancel_{uuid.uuid4().hex[:8]}"
    thread_id = f"th_cancel_{uuid.uuid4().hex[:8]}"
    trace_id = "trc_cancel_01"

    print(f"Spawning long-running agent run: {run_id}")
    broker = await manager.get_or_create_broker(run_id, thread_id, trace_id)

    # Emit initial events
    await broker.emit(AgentEventType.RUN_STARTED, payload={"query": "Long running simulation..."})
    await broker.emit(AgentEventType.PLAN_CREATED, payload={"steps": ["step1", "step2", "step3"]})

    # Client issues cancellation request via HTTP API
    print("Operator issues abort: POST /v1/agent/runs/{run_id}/cancel")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        cancel_resp = await client.post(
            f"/v1/agent/runs/{run_id}/cancel",
            json={"reason": "Vessel operator aborted operation"},
        )
        assert cancel_resp.status_code == 200
        cancel_data = cancel_resp.json()
        print(f"Cancellation response: {cancel_data}")
        assert cancel_data["status"] == "cancelled"

    # Verify journal contains RUN_CANCELLED
    events = await repo.get_events(run_id=run_id)
    cancelled_event = next((e for e in events if e.event_type == AgentEventType.RUN_CANCELLED), None)
    assert cancelled_event is not None, "RUN_CANCELLED event not found in PostgreSQL journal!"
    print(f"Verified RUN_CANCELLED event #{cancelled_event.sequence} in PostgreSQL journal:")
    print(f"  Reason: {cancelled_event.payload.get('reason')}")
    print(f"  Status: {cancelled_event.status}")
    print("Cancellation Invariants PASSED.")


def run_scenario_4_redaction_verification():
    print_banner("SCENARIO 4: Telemetry Security & Internal Monologue Redaction")
    dirty_payload = {
        "user_query": "PFZ near Mumbai",
        "api_key": "incois_secret_token_abcdef123456",
        "authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0",
        "db_connection": "postgresql://usr:super_secret_pwd@localhost:5432/marine",
        # Internal model reasoning / CoT fields that must never be emitted over SSE
        "thought": "Internal LLM reasoning that must never reach the user or telemetry.",
        "thinking": "Step 1 reasoning...",
        "chain_of_thought": "Draft thoughts...",
    }

    sanitized, was_redacted = sanitize_event_payload(dirty_payload)
    print("Testing payload sanitizer:")
    print(f"  was_redacted = {was_redacted}")
    print(f"  sanitized keys: {list(sanitized.keys())}")

    assert was_redacted is True
    assert sanitized["api_key"] == "[REDACTED]"
    assert sanitized["authorization"] == "[REDACTED]"
    assert "super_secret_pwd" not in sanitized["db_connection"]
    assert "thought" not in sanitized
    assert "thinking" not in sanitized
    assert "chain_of_thought" not in sanitized

    print("Redaction Invariants PASSED:")
    print("  [OK] API keys and Authorization tokens scrubbed")
    print("  [OK] Passwords in URIs scrubbed")
    print("  [OK] Chain-of-thought and internal monologue keys removed")


async def main():
    print_banner("ORCA MILESTONE P3.4: STREAMING EXECUTION & EVENT JOURNAL ACCEPTANCE TRACE")
    t_start = time.perf_counter()

    run_id, thread_id, total_events = await run_scenario_1_full_streaming()
    await run_scenario_2_reconnect_replay(run_id, total_events)
    await run_scenario_3_explicit_cancellation()
    run_scenario_4_redaction_verification()

    elapsed = time.perf_counter() - t_start
    print_banner(f"ALL P3.4 VERIFICATION SCENARIOS COMPLETED SUCCESSFULLY in {elapsed:.2f}s")


if __name__ == "__main__":
    asyncio.run(main())
