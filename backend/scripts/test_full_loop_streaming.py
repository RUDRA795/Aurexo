import asyncio
import json
import logging
import sys
from typing import Any

import httpx
from httpx import ASGITransport

from orca.api.main import app

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def parse_sse_stream(response: httpx.Response) -> list[dict[str, Any]]:
    """Parse Server-Sent Events from an HTTP response stream."""
    events = []
    current_event = {}
    async for line in response.aiter_lines():
        line = line.strip()
        if not line:
            if current_event:
                events.append(current_event)
                current_event = {}
            continue
        if line.startswith(":"):
            # Comment / keepalive
            continue
        if line.startswith("event:"):
            current_event["event"] = line.split("event:", 1)[1].strip()
        elif line.startswith("id:"):
            current_event["id"] = line.split("id:", 1)[1].strip()
        elif line.startswith("data:"):
            raw_data = line.split("data:", 1)[1].strip()
            try:
                current_event["data"] = json.loads(raw_data)
            except Exception:
                current_event["data"] = raw_data
        elif line.startswith("retry:"):
            current_event["retry"] = line.split("retry:", 1)[1].strip()

    if current_event:
        events.append(current_event)
    return events


async def run_full_loop_test() -> bool:
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=30.0) as client:
        # Test 0: Health Endpoint
        logger.info("=== STEP 0: Health Check ===")
        health_resp = await client.get("/health")
        assert health_resp.status_code == 200, f"Health check failed: {health_resp.text}"
        health_json = health_resp.json()
        logger.info("Health OK: %s", health_json)

        # Test 1: First Query (Goa PFZ)
        logger.info("=== STEP 1: Query 1 (Goa PFZ) ===")
        payload1 = {
            "query": "Identify nearest verified Potential Fishing Zone coordinates near Goa with SST and Chlorophyll-a"
        }
        resp1 = await client.post("/v1/agent/stream", json=payload1)
        assert resp1.status_code == 200, f"Failed stream request: {resp1.status_code}"
        assert "text/event-stream" in resp1.headers.get("content-type", "")

        events1 = await parse_sse_stream(resp1)
        logger.info("Query 1 received %d events", len(events1))
        assert len(events1) > 0, "No events received for Query 1"

        event_types1 = [ev.get("event") for ev in events1]
        logger.info("Event types: %s", event_types1)

        # Verify key event types are present
        assert "RUN_STARTED" in event_types1, "Missing RUN_STARTED"
        assert "PLAN_CREATED" in event_types1, "Missing PLAN_CREATED"
        assert "TOOL_COMPLETED" in event_types1, "Missing TOOL_COMPLETED"
        assert "EVIDENCE_ADDED" in event_types1, "Missing EVIDENCE_ADDED"
        assert "MAP_OVERLAY_UPDATED" in event_types1, "Missing MAP_OVERLAY_UPDATED"
        assert "SYNTHESIS_COMPLETED" in event_types1, "Missing SYNTHESIS_COMPLETED"
        assert "RUN_COMPLETED" in event_types1, "Missing RUN_COMPLETED"

        # Verify sequence numbers are monotonic
        seqs1 = [int(ev["id"]) for ev in events1 if "id" in ev]
        assert seqs1 == sorted(seqs1), f"Sequences not sorted: {seqs1}"
        assert len(seqs1) == len(set(seqs1)), "Duplicate sequence numbers detected"

        # Verify coordinates resolved to Goa region (~15.4°N, ~73.8°E)
        map_evs = [ev for ev in events1 if ev.get("event") == "MAP_OVERLAY_UPDATED"]
        assert len(map_evs) >= 1, "No map overlay events found"
        coords = map_evs[0]["data"]["payload"]["coordinates"]
        lon, lat = coords[0], coords[1]
        logger.info("Resolved Coordinates for Goa query: lat=%.2f, lon=%.2f", lat, lon)
        assert 14.0 <= lat <= 16.5, f"Expected Goa latitude range, got {lat}"
        assert 72.0 <= lon <= 75.0, f"Expected Goa longitude range, got {lon}"

        run_id_1 = events1[0]["data"].get("run_id")
        logger.info("Query 1 Run ID: %s, Total sequences: %d", run_id_1, max(seqs1))

        # Test 2: Multi-turn / Second Query (Mumbai Marine Conditions)
        logger.info("=== STEP 2: Query 2 (Mumbai Marine Conditions) ===")
        payload2 = {
            "query": "Analyze current marine conditions near Mumbai with fishing suitability and weather"
        }
        resp2 = await client.post("/v1/agent/stream", json=payload2)
        assert resp2.status_code == 200, f"Failed stream request: {resp2.status_code}"
        events2 = await parse_sse_stream(resp2)
        logger.info("Query 2 received %d events", len(events2))
        assert len(events2) > 0, "No events received for Query 2"

        event_types2 = [ev.get("event") for ev in events2]
        assert "RUN_STARTED" in event_types2, "Missing RUN_STARTED in Query 2"
        assert "RUN_COMPLETED" in event_types2, "Missing RUN_COMPLETED in Query 2"

        run_id_2 = events2[0]["data"].get("run_id")
        logger.info("Query 2 Run ID: %s", run_id_2)
        assert run_id_1 != run_id_2, "Query 2 should have independent run_id"

        map_evs2 = [ev for ev in events2 if ev.get("event") == "MAP_OVERLAY_UPDATED"]
        assert len(map_evs2) >= 1, "No map overlay events found for Mumbai query"
        coords2 = map_evs2[0]["data"]["payload"]["coordinates"]
        lon2, lat2 = coords2[0], coords2[1]
        logger.info("Resolved Coordinates for Mumbai query: lat=%.2f, lon=%.2f", lat2, lon2)
        assert 18.0 <= lat2 <= 20.0, f"Expected Mumbai latitude range, got {lat2}"
        assert 71.5 <= lon2 <= 74.0, f"Expected Mumbai longitude range, got {lon2}"

        # Test 3: Resilient Error Handling (Empty Query)
        logger.info("=== STEP 3: Query 3 (Empty Query Handling) ===")
        payload3 = {"query": "    "}
        resp3 = await client.post("/v1/agent/stream", json=payload3)
        assert resp3.status_code == 200
        events3 = await parse_sse_stream(resp3)
        event_types3 = [ev.get("event") for ev in events3]
        logger.info("Empty query event types: %s", event_types3)
        assert "RUN_FAILED" in event_types3, f"Expected RUN_FAILED, got {event_types3}"
        failed_ev = [ev for ev in events3 if ev.get("event") == "RUN_FAILED"][0]
        err_msg = failed_ev["data"]["payload"].get("error", "")
        logger.info("Graceful error message: '%s'", err_msg)
        assert "cannot be empty" in err_msg.lower(), f"Unexpected error message: {err_msg}"

        # Test 4: Reconnection with Last-Event-ID replay
        logger.info("=== STEP 4: Reconnection with Last-Event-ID ===")
        resume_payload = {
            "query": payload1["query"],
            "run_id": run_id_1,
        }
        reconnect_resp = await client.post(
            "/v1/agent/stream",
            json=resume_payload,
            headers={"Last-Event-ID": "3"},
        )
        assert reconnect_resp.status_code == 200
        reconnect_events = await parse_sse_stream(reconnect_resp)
        logger.info("Reconnection replayed %d events", len(reconnect_events))
        assert len(reconnect_events) > 0, "Expected replayed events from journal"
        replayed_seqs = [int(ev["id"]) for ev in reconnect_events if "id" in ev]
        assert all(s > 3 for s in replayed_seqs), f"Replayed events should be > 3, got {replayed_seqs}"
        assert replayed_seqs[0] == 4, f"First replayed sequence should be 4, got {replayed_seqs[0]}"

        logger.info("=== ALL FULL LOOP VERIFICATIONS PASSED SUCCESSFULLY! ===")
        return True


if __name__ == "__main__":
    success = asyncio.run(run_full_loop_test())
    sys.exit(0 if success else 1)
