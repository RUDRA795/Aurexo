import asyncio
import json
import logging
from typing import Any
import httpx
from httpx import AsyncClient, ASGITransport
from orca.api.main import app

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("orca-test-marine")

async def parse_sse_stream(response: httpx.Response) -> list[dict[str, Any]]:
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

async def test_query(client: AsyncClient, query: str, label: str):
    logger.info(f"\n==================================================")
    logger.info(f"TESTING: {label}")
    logger.info(f"QUERY: {query}")
    logger.info(f"==================================================")

    response = await client.post(
        "/v1/agent/stream",
        json={"query": query, "session_id": "test_presentation_rehearsal"},
    )
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    raw_events = await parse_sse_stream(response)
    event_types = []
    final_answer = ""
    overlay_data = None

    for ev in raw_events:
        evt_type = ev.get("event")
        data = ev.get("data", {})
        if isinstance(data, dict):
            inner_evt = data.get("event_type") or evt_type
            event_types.append(inner_evt)
            if inner_evt == "SYNTHESIS_COMPLETED":
                final_answer = data.get("payload", {}).get("answer_text", "")
            if inner_evt == "MAP_OVERLAY_UPDATED":
                overlay_data = data.get("payload", {})
        else:
            event_types.append(evt_type)

    logger.info(f"Total events received: {len(raw_events)}")
    logger.info(f"Event Types: {list(dict.fromkeys(event_types))}")
    if overlay_data:
        logger.info(f"Map Overlay Type: {overlay_data.get('type')}")
        if "restricted" in overlay_data:
            logger.info(f"Restricted Standoff: {overlay_data.get('restricted')}")
        if "alerts" in overlay_data:
            logger.info(f"Overlay Alerts: {overlay_data.get('alerts')}")
        if "route_waypoints" in overlay_data:
            logger.info(f"Route Waypoints Count: {len(overlay_data.get('route_waypoints', []))}")
    logger.info(f"SYNTHESIZED ANSWER PREVIEW:\n{final_answer[:300]}...\n")
    return event_types, final_answer, overlay_data

async def main():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver", timeout=45.0) as client:
        # 1. Golden Demo (Malim to PFZ with Safe Route & Geofence)
        evts1, ans1, over1 = await test_query(
            client,
            "I am fishing near Malim. Find the nearest verified PFZ, check whether it is safe to go tomorrow morning, avoid restricted maritime zones, and show me the safest route.",
            "GOLDEN DEMO: Malim PFZ + Safe Route + Geofence",
        )
        assert "MAP_OVERLAY_UPDATED" in evts1, "Expected MAP_OVERLAY_UPDATED event"
        assert over1 is not None, "Expected overlay payload"

        # 2. IMBL Stand-off Check near Rameshwaram / Palk Strait
        evts2, ans2, over2 = await test_query(
            client,
            "I am fishing out of Rameshwaram. Can I head towards the Palk Strait boundary?",
            "IMBL Stand-off Verification: Rameshwaram",
        )
        assert over2 is not None

        # 3. Fish Decline Q7 near Kochi
        evts3, ans3, over3 = await test_query(
            client,
            "Fish catch has declined 40% near Kochi this monsoon compared to last year. Analyze satellite SST and chlorophyll-a trends.",
            "Q7 Fish Productivity Decline: Kochi Shelf",
        )
        assert len(ans3) > 0

        # 4. Cyclone & Squall Q4
        evts4, ans4, over4 = await test_query(
            client,
            "Any cyclone, squall, or lightning alerts between Mangalore and Goa today?",
            "Q4 Cyclone & Squall Hazard Advisory",
        )
        assert len(ans4) > 0

    logger.info("\n>>> ALL 4 CANONICAL SIH SCENARIOS VERIFIED 100% SUCCEEDED! <<<")

if __name__ == "__main__":
    asyncio.run(main())
