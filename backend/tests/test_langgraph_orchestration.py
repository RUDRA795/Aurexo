from datetime import datetime, timedelta, timezone
from typing import Any
import pytest

from orca.agents.graph import create_orca_graph
from orca.agents.pfz_pipeline import MockPFZDataSource, PFZDataSource, run_pfz_query_graph
from orca.agents.state import OrcaGraphState
from orca.data.adapters.base import SourceUnavailableError
from orca.schemas.orca_contract import (
    AccessMethod,
    DataQuality,
    Evidence,
    FinalResponse,
    Geometry,
    ResponseType,
    SourceMetadata,
    VerificationSeverity,
    utc_now,
)
from orca.schemas.pfz_contract import PFZAccessTier, PFZPoint, PFZQuery, PFZQueryResult


class MockTieredPFZSource(PFZDataSource):
    def __init__(self, tier: PFZAccessTier, points: list[PFZPoint] | None = None, fail: bool = False):
        self.tier = tier
        self.points = points or []
        self.fail = fail

    async def fetch(self, query: PFZQuery) -> PFZQueryResult:
        if self.fail:
            raise SourceUnavailableError(f"Tier {self.tier.value} simulated failure")
        return PFZQueryResult(
            points=self.points,
            source=SourceMetadata(
                source_id=f"incois_{self.tier.value}",
                organization="INCOIS",
                dataset=f"PFZ_{self.tier.value}",
                authority="official",
                access=AccessMethod.API,
            ),
            access_tier=self.tier,
            retrieved_at=utc_now(),
        )



class MockSSTAdapter:
    def __init__(self, val: float = 28.5, fail: bool = False):
        self.val = val
        self.fail = fail

    def extract_sst(self, location: Geometry) -> Evidence:
        if self.fail:
            raise SourceUnavailableError("SST extraction failed")
        return Evidence(
            source=SourceMetadata(
                source_id="incois_osf_sst",
                organization="INCOIS",
                dataset="SST_IO_20260920.nc",
                authority="official",
                access=AccessMethod.ERDDAP,
            ),
            variable="sea_surface_temperature",
            value=self.val,
            unit="degC",
            geometry=location,
            retrieved_at=utc_now(),
            quality=DataQuality.GOOD,
            derived=True,
        )


class MockCHLAdapter:
    def __init__(self, val: float = 0.35, fail: bool = False):
        self.val = val
        self.fail = fail

    def extract_chlorophyll(self, location: Geometry) -> Evidence:
        if self.fail:
            raise SourceUnavailableError("Chlorophyll extraction failed")
        return Evidence(
            source=SourceMetadata(
                source_id="incois_viirs_chl",
                organization="INCOIS",
                dataset="VIIRS-CHL-20260920.nc",
                authority="official",
                access=AccessMethod.ERDDAP,
            ),
            variable="chlorophyll_a",
            value=self.val,
            unit="mg/m3",
            geometry=location,
            retrieved_at=utc_now(),
            quality=DataQuality.GOOD,
            derived=True,
        )


class MockWeatherAdapter:
    def __init__(self, fail: bool = False):
        self.fail = fail

    async def fetch_forecast(self, location: Geometry) -> Evidence:
        if self.fail:
            raise SourceUnavailableError("Weather service down")
        return Evidence(
            source=SourceMetadata(
                source_id="noaa_nws_weather",
                organization="NOAA",
                dataset="NWS Marine Weather",
                authority="official",
                access=AccessMethod.API,
            ),
            variable="marine_weather_forecast",
            value={
                "temperature_c": 28.0,
                "wind_speed": "10 to 15 knots",
                "short_forecast": "Slight Breeze",
            },
            unit="forecast_record",
            geometry=location,
            retrieved_at=utc_now(),
            quality=DataQuality.GOOD,
        )


def _make_valid_pfz_point(pfz_id: str = "pfz_001", sector: str = "GOA", offset_hours: float = 24.0) -> PFZPoint:
    now = utc_now()
    return PFZPoint(
        pfz_id=pfz_id,
        location=Geometry(lat=15.45, lon=73.40),
        sector=sector,
        depth_m=40.0,
        source_valid_from=now - timedelta(hours=12),
        source_valid_until=None,
        freshness_deadline=now + timedelta(hours=offset_hours),
        geometry_derivation="line_midpoint_derived",
        validity_derivation="orca_freshness_policy",
    )


@pytest.mark.asyncio
async def test_langgraph_normal_end_to_end():
    p = _make_valid_pfz_point()
    source = MockTieredPFZSource(tier=PFZAccessTier.WEBGIS_LAYER, points=[p])
    graph = create_orca_graph(
        pfz_sources=[source],
        sst_adapter=MockSSTAdapter(val=28.7),
        chl_adapter=MockCHLAdapter(val=0.45),
    )

    state: OrcaGraphState = {
        "user_query": "Where is the nearest PFZ for Goa coast?",
        "coordinates": Geometry(lat=15.2, lon=73.6),
    }

    result = await graph.ainvoke(state)

    assert result["selected_pfz"] is not None
    assert result["selected_pfz"].pfz_id == "pfz_001"
    assert result["sst_evidence"] is not None
    assert result["sst_evidence"].value == 28.7
    assert result["chlorophyll_evidence"] is not None
    assert result["chlorophyll_evidence"].value == 0.45

    ans: FinalResponse = result["final_answer"]
    assert ans is not None
    assert ans.response_type == ResponseType.FACTUAL
    assert "pfz_001" in ans.answer_text
    assert "28.7°C" in ans.answer_text
    assert "0.450 mg/m³" in ans.answer_text
    assert "ORCA freshness deadline" in ans.answer_text
    assert "source expiration unstated" in ans.answer_text


@pytest.mark.asyncio
async def test_langgraph_supervisor_routing_intent():
    p = _make_valid_pfz_point(sector="KERALA")
    source = MockTieredPFZSource(tier=PFZAccessTier.WEBGIS_LAYER, points=[p])
    graph = create_orca_graph(pfz_sources=[source], sst_adapter=MockSSTAdapter(), chl_adapter=MockCHLAdapter())

    # User query contains "Kerala" without explicit sector field
    state: OrcaGraphState = {
        "user_query": "Give me advisory for Kerala waters",
    }
    result = await graph.ainvoke(state)
    assert result["sector"] == "KERALA"


@pytest.mark.asyncio
async def test_langgraph_wfs_failure_to_text_fallback():
    p_text = _make_valid_pfz_point(pfz_id="pfz_text_001")
    src_wfs = MockTieredPFZSource(tier=PFZAccessTier.WEBGIS_LAYER, fail=True)
    src_text = MockTieredPFZSource(tier=PFZAccessTier.TEXT_ADVISORY, points=[p_text])
    src_cache = MockTieredPFZSource(tier=PFZAccessTier.CACHED, fail=True)


    graph = create_orca_graph(
        pfz_sources=[src_wfs, src_text, src_cache],
        sst_adapter=MockSSTAdapter(),
        chl_adapter=MockCHLAdapter(),
    )
    result = await graph.ainvoke({"user_query": "Goa PFZ", "coordinates": Geometry(lat=15.0, lon=73.5)})

    assert result["selected_pfz"].pfz_id == "pfz_text_001"
    assert result["pfz_tier_used"] == PFZAccessTier.TEXT_ADVISORY.value


@pytest.mark.asyncio
async def test_langgraph_text_failure_to_postgis_cache():
    p_cache = _make_valid_pfz_point(pfz_id="pfz_cache_001")
    src_wfs = MockTieredPFZSource(tier=PFZAccessTier.WEBGIS_LAYER, fail=True)
    src_text = MockTieredPFZSource(tier=PFZAccessTier.TEXT_ADVISORY, fail=True)
    src_cache = MockTieredPFZSource(tier=PFZAccessTier.CACHED, points=[p_cache])

    graph = create_orca_graph(
        pfz_sources=[src_wfs, src_text, src_cache],
        sst_adapter=MockSSTAdapter(),
        chl_adapter=MockCHLAdapter(),
    )
    result = await graph.ainvoke({"user_query": "Goa PFZ", "coordinates": Geometry(lat=15.0, lon=73.5)})

    assert result["selected_pfz"].pfz_id == "pfz_cache_001"
    assert result["pfz_tier_used"] == PFZAccessTier.CACHED.value



@pytest.mark.asyncio
async def test_langgraph_all_sources_fail_returns_unavailable():
    src_wfs = MockTieredPFZSource(tier=PFZAccessTier.WEBGIS_LAYER, fail=True)
    src_text = MockTieredPFZSource(tier=PFZAccessTier.TEXT_ADVISORY, fail=True)
    src_cache = MockTieredPFZSource(tier=PFZAccessTier.CACHED, fail=True)


    graph = create_orca_graph(
        pfz_sources=[src_wfs, src_text, src_cache],
        sst_adapter=MockSSTAdapter(),
        chl_adapter=MockCHLAdapter(),
    )
    result = await graph.ainvoke({"user_query": "Goa PFZ", "coordinates": Geometry(lat=15.0, lon=73.5)})

    assert result["selected_pfz"] is None
    assert result["pfz_unavailable"] is True
    ans = result["final_answer"]
    assert ans.response_type == ResponseType.ERROR
    assert "UNAVAILABLE" in ans.answer_text


@pytest.mark.asyncio
async def test_langgraph_parallel_environmental_and_weather():
    p = _make_valid_pfz_point()
    source = MockTieredPFZSource(tier=PFZAccessTier.WEBGIS_LAYER, points=[p])
    graph = create_orca_graph(
        pfz_sources=[source],
        sst_adapter=MockSSTAdapter(val=29.1),
        chl_adapter=MockCHLAdapter(val=0.52),
        weather_adapter=MockWeatherAdapter(),
    )

    result = await graph.ainvoke({
        "user_query": "What is the weather and PFZ for Goa?",
        "coordinates": Geometry(lat=15.0, lon=73.5),
    })

    assert result["sst_evidence"] is not None
    assert result["chlorophyll_evidence"] is not None
    assert result["weather_evidence"] is not None
    assert "10 to 15 knots" in result["final_answer"].answer_text


@pytest.mark.asyncio
async def test_langgraph_deterministic_stale_pfz_rejection():
    # PFZ expired 2 hours ago
    now = utc_now()
    stale_point = PFZPoint(
        pfz_id="pfz_stale_001",
        location=Geometry(lat=15.45, lon=73.40),
        sector="GOA",
        depth_m=40.0,
        source_valid_from=now - timedelta(hours=48),
        freshness_deadline=now - timedelta(hours=2),
    )
    source = MockTieredPFZSource(tier=PFZAccessTier.WEBGIS_LAYER, points=[stale_point])
    graph = create_orca_graph(pfz_sources=[source], sst_adapter=MockSSTAdapter(), chl_adapter=MockCHLAdapter())

    result = await graph.ainvoke({"user_query": "Goa PFZ", "coordinates": Geometry(lat=15.0, lon=73.5)})

    v_results = result["verification_results"]
    assert len(v_results) > 0
    assert v_results[-1].passed is False

    ans = result["final_answer"]
    assert ans.response_type == ResponseType.ERROR
    assert "UNAVAILABLE" in ans.answer_text


@pytest.mark.asyncio
async def test_langgraph_deterministic_provenance_rejection():
    p = _make_valid_pfz_point()
    source = MockTieredPFZSource(tier=PFZAccessTier.WEBGIS_LAYER, points=[p])

    # Inject corrupt evidence without source_id
    bad_evidence = Evidence(
        source=SourceMetadata(source_id="", organization="Unknown", dataset=""),
        variable="sea_surface_temperature",
        value=28.0,
        retrieved_at=utc_now(),
    )

    class CorruptSSTAdapter:
        def extract_sst(self, loc):
            return bad_evidence

    graph = create_orca_graph(pfz_sources=[source], sst_adapter=CorruptSSTAdapter(), chl_adapter=MockCHLAdapter())
    result = await graph.ainvoke({"user_query": "Goa PFZ", "coordinates": Geometry(lat=15.0, lon=73.5)})

    v_results = result["verification_results"]
    assert v_results[-1].passed is False

    ans = result["final_answer"]
    assert ans.response_type == ResponseType.ERROR
    assert "UNAVAILABLE" in ans.answer_text


@pytest.mark.asyncio
async def test_pipeline_bridge_backward_compatibility():
    p = _make_valid_pfz_point()
    source = MockTieredPFZSource(tier=PFZAccessTier.WEBGIS_LAYER, points=[p])

    state = await run_pfz_query_graph(
        query_text="Where is nearest PFZ for Goa?",
        location=Geometry(lat=15.0, lon=73.5),
        sources=[source],
        sst_adapter=MockSSTAdapter(val=28.3),
        chl_adapter=MockCHLAdapter(val=0.41),
    )

    assert state["final_answer"] is not None
    assert state["final_answer"].response_type == ResponseType.FACTUAL
    assert "pfz_001" in state["final_answer"].answer_text
