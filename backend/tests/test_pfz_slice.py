from datetime import timedelta

import pytest

from orca.schemas.orca_contract import AgentStatus, Geometry, ResponseType, ToolName, utc_now
from orca.schemas.pfz_contract import DistanceRequest, PFZPoint
from orca.agents.pfz_pipeline import (
    MockPFZDataSource,
    calculate_distance,
    geospatial_rank_by_distance,
    run_pfz_query,
)

GOA_USER_LOCATION = Geometry(lat=15.49, lon=73.83)


@pytest.mark.asyncio
async def test_nearest_pfz_happy_path_has_pfZ_and_distance_tool_trace():
    source = MockPFZDataSource()
    state = await run_pfz_query(
        query_text="Where is the nearest PFZ today?",
        location=GOA_USER_LOCATION,
        valid_at=utc_now(),
        sources=[source],
    )
    assert state.plan is not None
    assert state.final_answer is not None
    assert state.final_answer.response_type == ResponseType.FACTUAL
    assert len(state.final_answer.evidence_summary) >= 1
    assert state.final_answer.map_overlays[0].layer_id == "nearest-pfz"
    calls = [tc for ar in state.agent_results for tc in ar.tool_calls]
    assert any(tc.tool == ToolName.GET_PFZ for tc in calls)
    assert any(tc.tool == ToolName.CALCULATE_DISTANCE for tc in calls)


@pytest.mark.asyncio
async def test_radius_filter_is_actually_applied():
    source = MockPFZDataSource()
    state = await run_pfz_query(
        query_text="Nearest PFZ within radius",
        location=GOA_USER_LOCATION,
        valid_at=utc_now(),
        radius_km=1.0,
        sources=[source],
    )
    assert state.final_answer.response_type == ResponseType.ERROR
    assert "within 1 km" in state.final_answer.answer_text


@pytest.mark.asyncio
async def test_expired_pfz_candidate_is_rejected():
    state = await run_pfz_query(
        query_text="Nearest PFZ?",
        location=GOA_USER_LOCATION,
        valid_at=utc_now(),
        sources=[MockPFZDataSource()],
    )
    returned_ids = {
        f["properties"]["pfz_id"]
        for f in state.final_answer.map_overlays[0].data["features"]
    }
    assert "pfz_goa_003_expired" not in returned_ids


@pytest.mark.asyncio
async def test_sector_filter_is_applied():
    now = utc_now()
    points = [
        PFZPoint(
            pfz_id="goa",
            location=Geometry(lat=15.4, lon=73.7),
            sector="GOA",
            valid_from=now - timedelta(hours=1),
            valid_until=now + timedelta(hours=24),
        ),
        PFZPoint(
            pfz_id="mh",
            location=Geometry(lat=18.0, lon=73.0),
            sector="MAHARASHTRA",
            valid_from=now - timedelta(hours=1),
            valid_until=now + timedelta(hours=24),
        ),
    ]
    state = await run_pfz_query(
        query_text="Nearest PFZ in Goa",
        location=GOA_USER_LOCATION,
        valid_at=now,
        sector="goa",
        sources=[MockPFZDataSource(points=points)],
    )
    assert state.final_answer.response_type == ResponseType.FACTUAL
    assert all(
        f["properties"]["sector"] == "GOA"
        for f in state.final_answer.map_overlays[0].data["features"]
    )


@pytest.mark.asyncio
async def test_no_valid_pfz_is_honest_not_fabricated():
    now = utc_now()
    all_expired = [
        PFZPoint(
            pfz_id="pfz_stale",
            location=Geometry(lat=15.5, lon=73.6),
            sector="GOA",
            valid_from=now - timedelta(days=3),
            valid_until=now - timedelta(days=1),
        )
    ]
    state = await run_pfz_query(
        query_text="Nearest PFZ?",
        location=GOA_USER_LOCATION,
        valid_at=now,
        sources=[MockPFZDataSource(points=all_expired)],
    )
    assert state.final_answer.response_type == ResponseType.ERROR
    assert "No currently valid PFZ" in state.final_answer.answer_text


@pytest.mark.asyncio
async def test_primary_failure_triggers_exactly_one_replan():
    state = await run_pfz_query(
        query_text="Nearest PFZ?",
        location=GOA_USER_LOCATION,
        valid_at=utc_now(),
        sources=[MockPFZDataSource(fail=True)],
        fallback_sources=[MockPFZDataSource()],
    )
    assert state.replan_count == 1
    assert state.final_answer.response_type == ResponseType.FACTUAL
    assert len(state.agent_results) == 3
    assert [r.agent for r in state.agent_results] == ["pfz_agent", "pfz_agent", "geospatial_agent"]


@pytest.mark.asyncio
async def test_two_source_failures_do_not_trigger_third_attempt():
    state = await run_pfz_query(
        query_text="Nearest PFZ?",
        location=GOA_USER_LOCATION,
        valid_at=utc_now(),
        sources=[MockPFZDataSource(fail=True)],
        fallback_sources=[MockPFZDataSource(fail=True)],
    )
    assert state.replan_count == 1
    assert not state.can_replan()
    assert state.final_answer.response_type == ResponseType.ERROR
    assert len(state.agent_results) == 2


@pytest.mark.asyncio
async def test_evidence_provenance_and_distance_trace():
    state = await run_pfz_query(
        query_text="Nearest PFZ?",
        location=GOA_USER_LOCATION,
        valid_at=utc_now(),
        sources=[MockPFZDataSource()],
    )
    pfz_ar = next(r for r in state.agent_results if r.agent == "pfz_agent" and r.status == AgentStatus.SUCCESS)
    geo_ar = next(r for r in state.agent_results if r.agent == "geospatial_agent")
    pfz_evidence_ids = {e.id for e in pfz_ar.evidence}
    pfz_tool = next(tc for tc in pfz_ar.tool_calls if tc.tool == ToolName.GET_PFZ)
    assert pfz_evidence_ids == set(pfz_tool.evidence_ids)

    geo_evidence_ids = {e.id for e in geo_ar.evidence}
    distance_tool = next(tc for tc in geo_ar.tool_calls if tc.tool == ToolName.CALCULATE_DISTANCE)
    assert geo_evidence_ids == set(distance_tool.evidence_ids)
    output_distances = distance_tool.output["distances_km"]
    ui_distances = [
        f["properties"]["distance_km"]
        for f in state.final_answer.map_overlays[0].data["features"]
    ]
    assert [round(x, 2) for x in output_distances] == ui_distances
    assert any(t.node == "geospatial_agent" and t.duration_ms > 0 for t in state.final_answer.trace)


def test_distance_is_deterministic():
    result = calculate_distance(
        DistanceRequest(
            origin=Geometry(lat=15.49, lon=73.83),
            destinations=[Geometry(lat=15.62, lon=73.55)],
        )
    )
    assert 30.0 < result.distances_km[0] < 36.0
    assert result.method == "haversine_fallback"


def test_ranking_overrides_input_order():
    origin = GOA_USER_LOCATION
    far = PFZPoint(
        pfz_id="far",
        location=Geometry(lat=20.0, lon=73.0),
        sector="GOA",
    )
    near = PFZPoint(
        pfz_id="near",
        location=Geometry(lat=15.50, lon=73.84),
        sector="GOA",
    )
    ranked, distances = geospatial_rank_by_distance(origin, [far, near])
    assert ranked[0].pfz_id == "near"
    assert distances.distances_km == sorted(distances.distances_km)
