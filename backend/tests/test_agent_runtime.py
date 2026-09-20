from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import pytest
from pydantic import BaseModel, Field

from orca.agents.runtime import (
    COASTAL_GAZETTEER,
    OrcaAgentRuntime,
    parse_intent,
    resolve_spatial_parameters,
)
from orca.safety.geographic_policy import (
    GeographicRegionPolicy,
    PREDEFINED_REGIONS,
    get_operational_region_policy,
    is_within_operational_region,
)
from orca.safety.source_policy import SourcePolicyRegistry, SourceTrustTier
from orca.schemas.agent_runtime import (
    AgentRuntimeResult,
    ClaimGrounding,
    EvidenceRequirement,
    IntentEnum,
    PlanStep,
    SufficiencyEvaluationResult,
    TaskPlan,
)
from orca.schemas.orca_contract import (
    AccessMethod,
    DataQuality,
    Evidence,
    FinalResponse,
    Geometry,
    ResponseType,
    SourceMetadata,
    utc_now,
)
from orca.schemas.pfz_contract import (
    PFZAccessTier,
    PFZPoint,
    PFZQuery,
    PFZQueryResult,
)
from orca.tools.marine_tools import (
    AdvisoryRAGTool,
    ChlorophyllRetrievalTool,
    CopernicusMarineTool,
    IMDMarineWeatherTool,
    INCOISOceanStateTool,
    MarineWeatherRouterTool,
    NOAAWeatherTool,
    PFZRetrievalTool,
    SpatialQueryTool,
    SSTRetrievalTool,
    TranslationTool,
    create_default_tool_registry,
)
from orca.tools.registry import (
    BaseMarineTool,
    ToolExecutionResult,
    ToolRegistry,
    ToolStatus,
)


# ===========================================================================
# Fixture Mocks for Deterministic Testing
# ===========================================================================

class MockPFZProvider:
    def __init__(self, tier: PFZAccessTier = PFZAccessTier.STRUCTURED_SPATIAL, points: list[PFZPoint] | None = None, fail: bool = False):
        self.tier = tier
        self.fail = fail
        self.points = points or [
            PFZPoint(
                pfz_id="PFZ-BOM-001",
                location=Geometry(lat=18.95, lon=72.75),
                bearing_from_landing_center_deg=260.0,
                distance_from_landing_center_km=15.2,
                depth_m=35.0,
                landing_center="Sassoon Dock",
                sector="MAHARASHTRA",
            )
        ]

    async def fetch(self, query: PFZQuery) -> PFZQueryResult:
        if self.fail:
            raise RuntimeError("INCOIS WFS Service Unavailable")
        return PFZQueryResult(
            points=self.points,
            source=SourceMetadata(
                source_id="incois_pfz_wfs",
                organization="INCOIS",
                dataset="PFZ_ADVISORY",
                authority="official",
                access=AccessMethod.WEBGIS,
            ),
            access_tier=self.tier,
            retrieved_at=utc_now(),
        )


class MockSSTAdapter:
    def __init__(self, sst_val: float = 28.4, is_degraded: bool = False, fail: bool = False):
        self.sst_val = sst_val
        self.is_degraded = is_degraded
        self.fail = fail

    async def resolve_endpoint(self) -> str:
        return "https://incois.gov.in/thredds/dodsC/sst.nc"

    def extract_sst(self, location: Geometry) -> Evidence:
        if self.fail:
            raise RuntimeError("NetCDF slice read timeout")
        return Evidence(
            source=SourceMetadata(
                source_id="incois_sst_catalog",
                organization="INCOIS",
                dataset="SST_DAILY_20260920",
                authority="official",
                access=AccessMethod.ERDDAP,
            ),
            variable="sea_surface_temperature",
            value=self.sst_val,
            unit="degC",
            geometry=location,
            retrieved_at=utc_now(),
            quality=DataQuality.DEGRADED if self.is_degraded else DataQuality.GOOD,
            derived=True,
        )


class MockCHLAdapter:
    def __init__(self, chl_val: float = 0.42, is_degraded: bool = False, fail: bool = False):
        self.chl_val = chl_val
        self.is_degraded = is_degraded
        self.fail = fail

    async def resolve_endpoint(self) -> str:
        return "https://incois.gov.in/thredds/dodsC/chl.nc"

    def extract_chlorophyll(self, location: Geometry) -> Evidence:
        if self.fail:
            raise RuntimeError("Chlorophyll rolling dataset unavailable")
        return Evidence(
            source=SourceMetadata(
                source_id="incois_chl_catalog",
                organization="INCOIS",
                dataset="CHL_MODIS_20260920",
                authority="official",
                access=AccessMethod.ERDDAP,
            ),
            variable="chlorophyll_a",
            value=self.chl_val,
            unit="mg/m3",
            geometry=location,
            retrieved_at=utc_now(),
            quality=DataQuality.DEGRADED if self.is_degraded else DataQuality.GOOD,
            derived=True,
        )


class MockWeatherAdapter:
    def __init__(self, wind_speed: str = "12 knots SW", forecast: str = "Scattered showers", fail: bool = False):
        self.wind_speed = wind_speed
        self.forecast = forecast
        self.fail = fail

    async def fetch_forecast(self, location: Geometry) -> Evidence:
        if self.fail:
            raise RuntimeError("NOAA NWS API timeout")
        return Evidence(
            source=SourceMetadata(
                source_id="noaa_weather_forecast",
                organization="NOAA",
                dataset="National Weather Service Marine Forecast",
                authority="official",
                access=AccessMethod.API,
            ),
            variable="marine_weather_forecast",
            value={"wind_speed": self.wind_speed, "short_forecast": self.forecast},
            geometry=location,
            retrieved_at=utc_now(),
            quality=DataQuality.GOOD,
        )


class MockINCOISOSFAdapter:
    def __init__(self, fail: bool = False):
        self.fail = fail

    async def fetch_ocean_state(self, location: Geometry, sector: str | None = None) -> list[Evidence]:
        if self.fail:
            raise RuntimeError("INCOIS OSF dataset unavailable")
        now = utc_now()
        source_meta = SourceMetadata(
            source_id="incois_osf_ocean_state",
            organization="INCOIS",
            dataset="Ocean State Forecast",
            authority="official",
            access=AccessMethod.API,
        )
        return [
            Evidence(
                source=source_meta,
                variable="significant_wave_height",
                value=1.3,
                unit="m",
                geometry=location,
                retrieved_at=now,
                quality=DataQuality.GOOD,
            ),
            Evidence(
                source=source_meta,
                variable="wind",
                value={"wind_speed_knots": 14.0, "wind_direction_deg": 260.0},
                unit="knots",
                geometry=location,
                retrieved_at=now,
                quality=DataQuality.GOOD,
            ),
            Evidence(
                source=source_meta,
                variable="ocean_state",
                value={"sea_state": "Slight to Moderate", "swell_height_m": 0.8},
                geometry=location,
                retrieved_at=now,
                quality=DataQuality.GOOD,
            ),
        ]


class MockIMDWeatherAdapter:
    def __init__(self, fail: bool = False):
        self.fail = fail

    async def fetch_fishermen_warning(self, location: Geometry, sector: str | None = None) -> Evidence:
        if self.fail:
            raise RuntimeError("IMD coastal bulletin timeout")
        now = utc_now()
        return Evidence(
            source=SourceMetadata(
                source_id="imd_marine_warning",
                organization="India Meteorological Department",
                dataset="IMD Coastal Marine Bulletin",
                authority="official",
                access=AccessMethod.API,
            ),
            variable="fishermen_warning",
            value={
                "warning_level": "NO_WARNING",
                "fishermen_warning": "No warning for fishermen along Maharashtra coast for next 24 hours.",
            },
            geometry=location,
            retrieved_at=now,
            quality=DataQuality.GOOD,
        )


class MockAdvisoryRepo:
    def __init__(self, items: list[dict[str, Any]] | None = None, fail: bool = False):
        self.fail = fail
        self.items = items or [
            {
                "title": "Monsoon Safety Bulletin",
                "content": "Advisory for small fishing craft operating off Maharashtra coast.",
                "sector": "MAHARASHTRA",
            }
        ]

    async def search_advisories(self, query_text: str, sector: str | None = None, language: str | None = None, limit: int = 3):
        if self.fail:
            raise RuntimeError("Advisory pgvector search failed")
        class SearchResult:
            def __init__(self, item: dict[str, Any]):
                self.evidence = Evidence(
                    source=SourceMetadata(
                        source_id="incois_advisory_bulletin",
                        organization="INCOIS",
                        dataset="Advisory Bulletins Vector Store",
                        authority="official",
                        access=AccessMethod.API,
                    ),
                    variable="advisory_context",
                    value=item,
                    retrieved_at=utc_now(),
                    quality=DataQuality.GOOD,
                )
        return [SearchResult(it) for it in self.items[:limit]]


# Custom Flaky Tool for testing Supervisor Retries
class FlakyParams(BaseModel):
    key: str = Field(..., min_length=1)


class FlakyTool(BaseMarineTool):
    name = "flaky_tool"
    description = "A tool that fails initially and succeeds on attempt 2"
    parameter_schema = FlakyParams

    def __init__(self, fail_count: int = 1):
        self.fail_count = fail_count
        self.attempts = 0

    async def execute(self, params: FlakyParams) -> ToolExecutionResult:
        self.attempts += 1
        if self.attempts <= self.fail_count:
            return ToolExecutionResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                errors=[f"Simulated transient network timeout (attempt {self.attempts})"],
                quality=DataQuality.UNRELIABLE,
            )
        return ToolExecutionResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            evidence=[
                Evidence(
                    source=SourceMetadata(
                        source_id="flaky_recovery_source",
                        organization="Test Suite",
                        dataset="Flaky Data",
                        authority="official",
                        access=AccessMethod.API,
                    ),
                    variable="flaky_test_metric",
                    value={"key": params.key, "recovered": True},
                    retrieved_at=utc_now(),
                    quality=DataQuality.GOOD,
                )
            ],
            quality=DataQuality.GOOD,
        )


def build_test_runtime(
    pfz_tier: PFZAccessTier = PFZAccessTier.STRUCTURED_SPATIAL,
    pfz_fail: bool = False,
    sst_fail: bool = False,
    sst_degraded: bool = False,
    chl_fail: bool = False,
    weather_fail: bool = False,
    advisory_fail: bool = False,
    max_steps: int = 6,
) -> OrcaAgentRuntime:
    """Helper to assemble an OrcaAgentRuntime populated with test fixtures."""
    registry = ToolRegistry()
    registry.register_tool(PFZRetrievalTool(provider=MockPFZProvider(tier=pfz_tier, fail=pfz_fail)))
    registry.register_tool(SSTRetrievalTool(adapter=MockSSTAdapter(is_degraded=sst_degraded, fail=sst_fail)))
    registry.register_tool(ChlorophyllRetrievalTool(adapter=MockCHLAdapter(fail=chl_fail)))
    registry.register_tool(
        MarineWeatherRouterTool(
            incois_osf=MockINCOISOSFAdapter(fail=weather_fail),
            imd_adapter=MockIMDWeatherAdapter(fail=weather_fail),
            noaa_adapter=MockWeatherAdapter(fail=weather_fail),
        )
    )
    registry.register_tool(INCOISOceanStateTool(adapter=MockINCOISOSFAdapter(fail=weather_fail)))
    registry.register_tool(IMDMarineWeatherTool(adapter=MockIMDWeatherAdapter(fail=weather_fail)))
    registry.register_tool(NOAAWeatherTool(adapter=MockWeatherAdapter(fail=weather_fail)))
    registry.register_tool(CopernicusMarineTool())
    registry.register_tool(AdvisoryRAGTool(repository=MockAdvisoryRepo(fail=advisory_fail)))
    registry.register_tool(SpatialQueryTool())
    registry.register_tool(TranslationTool())

    return OrcaAgentRuntime(tool_registry=registry, max_steps=max_steps)


# ===========================================================================
# 1. Intent Parsing & Rejection Tests
# ===========================================================================

def test_intent_parsing_all_categories():
    """Verify deterministic intent classification across all supported marine and non-marine intents."""
    assert parse_intent("Where are the active PFZ zones?") == IntentEnum.PFZ_SEEKING
    assert parse_intent("Fishing suitability condition near Mumbai with weather and SST") == IntentEnum.FISHING_SUITABILITY
    assert parse_intent("What is the wind speed and wave forecast for Goa coast?") == IntentEnum.WEATHER_FORECAST
    assert parse_intent("Check current sea surface temperature and chlorophyll") == IntentEnum.OCEAN_METRICS
    assert parse_intent("Search official INCOIS ocean advisory bulletins") == IntentEnum.ADVISORY_SEARCH
    assert parse_intent("Calculate distance and bearing from Mumbai to Betul port") == IntentEnum.SPATIAL_QUERY
    assert parse_intent("Translate advisory warning in Malayalam") == IntentEnum.TRANSLATION
    assert parse_intent("What if wind speed increases to 40 knots, simulate scenario") == IntentEnum.SCENARIO_SIMULATION
    assert parse_intent("General marine biology question about Arabian Sea reefs") == IntentEnum.GENERAL_MARINE_QUERY


def test_intent_parsing_unsupported_rejection():
    """Verify non-marine queries (crypto, poems, stocks, recipes) are cleanly flagged as UNSUPPORTED_INTENT."""
    assert parse_intent("Write a poem about dolphins") == IntentEnum.UNSUPPORTED_INTENT
    assert parse_intent("What is the price of bitcoin and crypto stocks?") == IntentEnum.UNSUPPORTED_INTENT
    assert parse_intent("Give me a recipe for fish curry") == IntentEnum.UNSUPPORTED_INTENT
    assert parse_intent("Who won the cricket match yesterday?") == IntentEnum.UNSUPPORTED_INTENT


# ===========================================================================
# 2. Coastal Gazetteer & Spatial Resolution Tests
# ===========================================================================

def test_coastal_gazetteer_resolution():
    """Verify coastal port/landing center detection and coordinate resolution."""
    loc, sec = resolve_spatial_parameters("Find PFZ zones near Mumbai harbor")
    assert loc is not None
    assert round(loc.lat, 2) == 18.92
    assert round(loc.lon, 2) == 72.83
    assert sec == "MAHARASHTRA"

    loc_goa, sec_goa = resolve_spatial_parameters("Check conditions around Betul")
    assert loc_goa is not None
    assert loc_goa.lat == 15.20
    assert loc_goa.lon == 73.70
    assert sec_goa == "GOA"

    explicit = Geometry(lat=12.0, lon=75.0)
    loc_exp, sec_exp = resolve_spatial_parameters("Near Mumbai", explicit_location=explicit, explicit_sector="KERALA")
    assert loc_exp.lat == 12.0
    assert loc_exp.lon == 75.0
    assert sec_exp == "KERALA"

    loc_regex, _ = resolve_spatial_parameters("Check SST at 15.45, 73.80 please")
    assert loc_regex is not None
    assert loc_regex.lat == 15.45
    assert loc_regex.lon == 73.80


# ===========================================================================
# 3. Parallel Task Plan Generation & Step Dependencies
# ===========================================================================

def test_task_plan_generation_parallel_environment():
    """Verify plan decomposition: environmental tools (PFZ, SST, CHL, weather) have independent dependencies."""
    runtime = build_test_runtime()

    plan = runtime.generate_plan(
        IntentEnum.FISHING_SUITABILITY,
        "Is it safe to fish near Mumbai?",
        Geometry(lat=18.92, lon=72.83),
        "MAHARASHTRA",
    )
    assert len(plan.steps) == 5
    tool_names = [s.tool_name for s in plan.steps]
    assert tool_names == ["pfz_retrieval", "sst_retrieval", "chlorophyll_retrieval", "marine_weather", "advisory_rag"]

    # Environmental tools have no artificial sequential dependencies (can execute concurrently)
    assert plan.steps[0].dependencies == []
    assert plan.steps[1].dependencies == []
    assert plan.steps[2].dependencies == []
    assert plan.steps[3].dependencies == []

    # Unsupported intent generates 0 steps
    unsupported_plan = runtime.generate_plan(IntentEnum.UNSUPPORTED_INTENT, "Write a poem", None, None)
    assert len(unsupported_plan.steps) == 0


# ===========================================================================
# 4. Tool Registry, Schema Validation & Domain Pre-Check
# ===========================================================================

@pytest.mark.asyncio
async def test_tool_registry_validation():
    """Verify tool parameter schema validation and rejection of invalid coordinates."""
    registry = create_default_tool_registry()

    res = await registry.execute_tool("spatial_query", {"origin_lat": 15.0, "origin_lon": 73.0})
    assert res.status == ToolStatus.SUCCESS
    assert len(res.evidence) == 1

    res_invalid = await registry.execute_tool("spatial_query", {"origin_lat": 195.0, "origin_lon": 73.0})
    assert res_invalid.status == ToolStatus.ERROR
    assert any("Parameter validation" in err for err in res_invalid.errors)

    res_missing = await registry.execute_tool("spatial_query", {"origin_lat": 15.0})
    assert res_missing.status == ToolStatus.ERROR


@pytest.mark.asyncio
async def test_noaa_out_of_domain_for_mumbai():
    """Verify NOAA is immediately rejected as OUT_OF_DOMAIN for Mumbai coordinates without HTTP call."""
    tool = NOAAWeatherTool()
    # Mumbai coordinates
    assert tool.is_applicable(18.92, 72.83) is False

    # Execute directly
    res = await tool.execute(tool.parameter_schema(lat=18.92, lon=72.83))
    assert res.status == ToolStatus.OUT_OF_DOMAIN
    assert any("out of operational domain" in err for err in res.errors)

    # US coordinates
    assert tool.is_applicable(25.76, -80.19) is True  # Miami


@pytest.mark.asyncio
async def test_noaa_out_of_domain_does_not_consume_retry_budget():
    """Verify supervisor halts out-of-domain tools immediately with retry_count=0."""
    registry = ToolRegistry()
    registry.register_tool(NOAAWeatherTool())
    runtime = OrcaAgentRuntime(tool_registry=registry)

    plan = TaskPlan(
        plan_id="plan_noaa_domain",
        intent=IntentEnum.WEATHER_FORECAST,
        query="Weather at Mumbai",
        steps=[
            PlanStep(
                step_id="step_noaa",
                tool_name="noaa_weather",
                parameters={"lat": 18.92, "lon": 72.83},
                max_retries=2,
            )
        ],
    )

    result = await runtime.run("Weather at Mumbai", plan=plan)
    assert plan.steps[0].retry_count == 0  # Zero retries wasted!
    assert plan.steps[0].status == "failed"
    assert result.execution_metadata["traces"][0]["status"] == ToolStatus.OUT_OF_DOMAIN.value


# ===========================================================================
# 5. Indian Marine Weather & Ocean State Routing Tests
# ===========================================================================

@pytest.mark.asyncio
async def test_indian_weather_source_routing():
    """Verify MarineWeatherRouterTool routes Mumbai coordinates to INCOIS OSF and IMD Marine."""
    tool = MarineWeatherRouterTool()
    res = await tool.execute(tool.parameter_schema(lat=18.92, lon=72.83))
    assert res.status == ToolStatus.SUCCESS
    assert res.provenance["routing"] == "INDIAN_OPERATIONAL"

    variables = [e.variable for e in res.evidence]
    assert "significant_wave_height" in variables
    assert "wind" in variables
    assert "ocean_state" in variables
    assert "fishermen_warning" in variables


@pytest.mark.asyncio
async def test_incois_osf_routing():
    """Verify direct INCOISOceanStateTool execution for wave, swell, and currents."""
    tool = INCOISOceanStateTool()
    res = await tool.execute(tool.parameter_schema(lat=15.50, lon=73.80))
    assert res.status == ToolStatus.SUCCESS
    assert len(res.evidence) >= 2
    assert any(e.variable == "significant_wave_height" for e in res.evidence)


@pytest.mark.asyncio
async def test_imd_warning_routing():
    """Verify direct IMDMarineWeatherTool execution for coastal bulletins."""
    tool = IMDMarineWeatherTool()
    res = await tool.execute(tool.parameter_schema(lat=18.92, lon=72.83))
    assert res.status == ToolStatus.SUCCESS
    assert res.evidence[0].variable == "fishermen_warning"
    assert res.evidence[0].source.source_id == "imd_marine_warning"


# ===========================================================================
# 6. Supervisor Execution Loop & Retries
# ===========================================================================

@pytest.mark.asyncio
async def test_supervisor_retry_mechanism():
    """Verify supervisor retries flaky tools up to step.max_retries and recovers."""
    registry = ToolRegistry()
    flaky = FlakyTool(fail_count=1)
    registry.register_tool(flaky)

    runtime = OrcaAgentRuntime(tool_registry=registry)

    plan = TaskPlan(
        plan_id="plan_retry_test",
        intent=IntentEnum.GENERAL_MARINE_QUERY,
        query="Test flaky recovery",
        steps=[
            PlanStep(
                step_id="step_flaky",
                tool_name="flaky_tool",
                parameters={"key": "test_param"},
                max_retries=2,
            )
        ],
    )

    res = await runtime.run("Test flaky recovery", plan=plan)
    assert flaky.attempts == 2
    assert plan.steps[0].retry_count == 1
    assert plan.steps[0].status == "completed"
    assert len(res.all_evidence) == 1
    assert res.all_evidence[0].variable == "flaky_test_metric"


@pytest.mark.asyncio
async def test_supervisor_max_steps_limit():
    """Verify runtime enforces max_steps boundary and halts gracefully."""
    runtime = build_test_runtime(max_steps=2)

    result = await runtime.run("Evaluate fishing suitability near Mumbai with weather and sst")
    assert result.execution_metadata["steps_executed"] == 2
    assert result.execution_metadata["steps_planned"] == 5
    traces = result.execution_metadata["traces"]
    assert any(t.get("status") == "limit_exceeded" for t in traces)


# ===========================================================================
# 7. Deterministic Fallback & Degraded Quality Propagation
# ===========================================================================

@pytest.mark.asyncio
async def test_fallback_and_degraded_provenance():
    """Verify fallback from primary WFS to text advisory propagates DEGRADED quality."""
    runtime = build_test_runtime(
        pfz_tier=PFZAccessTier.TEXT_ADVISORY,
        sst_degraded=True,
    )

    result = await runtime.run("Where are the PFZ zones near Mumbai?")
    assert result.final_response.response_type == ResponseType.FACTUAL
    assert result.execution_metadata["data_quality"] == DataQuality.DEGRADED.value
    assert result.final_response.confidence < 1.0


# ===========================================================================
# 8. Evidence Sufficiency & Grounding Verification (P3.0-G Core Gates)
# ===========================================================================

def test_evidence_sufficiency_evaluation():
    """Verify typed EvidenceRequirement evaluation and separated completeness vs confidence."""
    runtime = build_test_runtime()

    ev_pfz = Evidence(
        source=SourceMetadata(source_id="incois_pfz", organization="INCOIS", dataset="PFZ", authority="official", access=AccessMethod.API),
        variable="pfz_point",
        value={"pfz_id": "PFZ-1"},
        retrieved_at=utc_now(),
        quality=DataQuality.GOOD,
    )
    suff_pfz: SufficiencyEvaluationResult = runtime.evaluate_evidence_sufficiency(IntentEnum.PFZ_SEEKING, [ev_pfz])
    assert suff_pfz.is_sufficient is True
    assert suff_pfz.evidence_quality == DataQuality.GOOD
    assert suff_pfz.evidence_completeness == 1.0
    assert suff_pfz.answer_confidence == 1.0
    assert len(suff_pfz.missing_mandatory) == 0


def test_mandatory_weather_failure_degrades_sufficiency():
    """NEGATIVE TEST: Mandatory marine weather failure MUST NOT return score=1.0 or GOOD."""
    runtime = build_test_runtime()

    ev_pfz = Evidence(
        source=SourceMetadata(source_id="incois_pfz", organization="INCOIS", dataset="PFZ", authority="official", access=AccessMethod.API),
        variable="pfz_point",
        value={"pfz_id": "PFZ-1"},
        retrieved_at=utc_now(),
        quality=DataQuality.GOOD,
    )
    ev_sst = Evidence(
        source=SourceMetadata(source_id="incois_sst", organization="INCOIS", dataset="SST", authority="official", access=AccessMethod.API),
        variable="sea_surface_temperature",
        value=29.0,
        retrieved_at=utc_now(),
        quality=DataQuality.GOOD,
    )
    ev_chl = Evidence(
        source=SourceMetadata(source_id="incois_chl", organization="INCOIS", dataset="CHL", authority="official", access=AccessMethod.API),
        variable="chlorophyll_a",
        value=0.3,
        retrieved_at=utc_now(),
        quality=DataQuality.GOOD,
    )

    # 3 of 4 mandatory variables present (weather missing)
    suff: SufficiencyEvaluationResult = runtime.evaluate_evidence_sufficiency(
        IntentEnum.FISHING_SUITABILITY,
        [ev_pfz, ev_sst, ev_chl],
    )
    assert suff.is_sufficient is False
    assert suff.evidence_quality == DataQuality.DEGRADED
    assert suff.evidence_completeness == 0.75  # 3 of 4 mandatory satisfied
    assert suff.answer_confidence < 0.75
    assert "marine_operational_conditions" in suff.missing_mandatory
    assert any("Missing mandatory evidence variables" in n for n in suff.notes)


def test_optional_advisory_failure_preserves_sufficiency():
    """Verify failure of optional advisory does NOT invalidate otherwise sufficient physical observations."""
    runtime = build_test_runtime()

    ev_pfz = Evidence(
        source=SourceMetadata(source_id="incois_pfz", organization="INCOIS", dataset="PFZ", authority="official", access=AccessMethod.API),
        variable="pfz_point",
        value={"pfz_id": "PFZ-1"},
        retrieved_at=utc_now(),
        quality=DataQuality.GOOD,
    )
    ev_sst = Evidence(
        source=SourceMetadata(source_id="incois_sst", organization="INCOIS", dataset="SST", authority="official", access=AccessMethod.API),
        variable="sea_surface_temperature",
        value=29.0,
        retrieved_at=utc_now(),
        quality=DataQuality.GOOD,
    )
    ev_chl = Evidence(
        source=SourceMetadata(source_id="incois_chl", organization="INCOIS", dataset="CHL", authority="official", access=AccessMethod.API),
        variable="chlorophyll_a",
        value=0.3,
        retrieved_at=utc_now(),
        quality=DataQuality.GOOD,
    )
    ev_weather = Evidence(
        source=SourceMetadata(source_id="incois_osf", organization="INCOIS", dataset="OSF", authority="official", access=AccessMethod.API),
        variable="significant_wave_height",
        value=1.2,
        retrieved_at=utc_now(),
        quality=DataQuality.GOOD,
    )

    # All 4 mandatory variables present, advisory missing
    suff: SufficiencyEvaluationResult = runtime.evaluate_evidence_sufficiency(
        IntentEnum.FISHING_SUITABILITY,
        [ev_pfz, ev_sst, ev_chl, ev_weather],
    )
    assert suff.is_sufficient is True
    assert suff.evidence_quality == DataQuality.GOOD
    assert suff.evidence_completeness == 1.0
    assert len(suff.missing_mandatory) == 0
    assert "advisory_context" in suff.missing_optional


def test_advisory_cannot_substitute_for_physical_observation():
    """Verify that an advisory bulletin CANNOT substitute for a missing physical marine observation."""
    runtime = build_test_runtime()

    ev_pfz = Evidence(
        source=SourceMetadata(source_id="incois_pfz", organization="INCOIS", dataset="PFZ", authority="official", access=AccessMethod.API),
        variable="pfz_point",
        value={"pfz_id": "PFZ-1"},
        retrieved_at=utc_now(),
        quality=DataQuality.GOOD,
    )
    ev_sst = Evidence(
        source=SourceMetadata(source_id="incois_sst", organization="INCOIS", dataset="SST", authority="official", access=AccessMethod.API),
        variable="sea_surface_temperature",
        value=29.0,
        retrieved_at=utc_now(),
        quality=DataQuality.GOOD,
    )
    ev_chl = Evidence(
        source=SourceMetadata(source_id="incois_chl", organization="INCOIS", dataset="CHL", authority="official", access=AccessMethod.API),
        variable="chlorophyll_a",
        value=0.3,
        retrieved_at=utc_now(),
        quality=DataQuality.GOOD,
    )
    ev_adv = Evidence(
        source=SourceMetadata(source_id="incois_bulletin", organization="INCOIS", dataset="Bulletin", authority="official", access=AccessMethod.API),
        variable="advisory_context",
        value={"title": "Text bulletin", "content": "Weather looks okay"},
        retrieved_at=utc_now(),
        quality=DataQuality.GOOD,
    )

    # Advisory is present, but physical weather is missing!
    suff: SufficiencyEvaluationResult = runtime.evaluate_evidence_sufficiency(
        IntentEnum.FISHING_SUITABILITY,
        [ev_pfz, ev_sst, ev_chl, ev_adv],
    )
    # MUST NOT be sufficient
    assert suff.is_sufficient is False
    assert suff.evidence_completeness == 0.75
    assert "marine_operational_conditions" in suff.missing_mandatory


# ===========================================================================
# 9. Grounded Synthesis & Claim-to-Evidence Binding
# ===========================================================================

def test_grounded_synthesis_claim_binding():
    """Verify that every synthesized factual statement is bound to an official evidence ID."""
    runtime = build_test_runtime()

    ev1 = Evidence(
        source=SourceMetadata(source_id="incois_pfz_official", organization="INCOIS", dataset="PFZ", authority="official", access=AccessMethod.API),
        variable="pfz_point",
        value={"pfz_id": "PFZ-99", "sector": "MAHARASHTRA"},
        geometry=Geometry(lat=18.9, lon=72.8),
        retrieved_at=utc_now(),
        quality=DataQuality.GOOD,
    )
    ev2 = Evidence(
        source=SourceMetadata(source_id="incois_sst_sensor", organization="INCOIS", dataset="SST", authority="official", access=AccessMethod.API),
        variable="sea_surface_temperature",
        value=29.1,
        retrieved_at=utc_now(),
        quality=DataQuality.GOOD,
    )

    suff = SufficiencyEvaluationResult(
        is_sufficient=True,
        evidence_quality=DataQuality.GOOD,
        evidence_completeness=1.0,
        answer_confidence=0.95,
        missing_mandatory=[],
        missing_optional=[],
    )

    final_resp, claims = runtime.synthesize_grounded_response(
        intent=IntentEnum.OCEAN_METRICS,
        query="Check SST",
        evidence_list=[ev1, ev2],
        sufficiency=suff,
        session_id="test_sess",
    )

    assert final_resp.response_type == ResponseType.FACTUAL
    assert "29.1°C" in final_resp.answer_text
    assert len(claims) >= 1
    for claim in claims:
        assert len(claim.supporting_evidence_ids) > 0


# ===========================================================================
# 10. Refusal on Unsupported Out-of-Domain Query
# ===========================================================================

@pytest.mark.asyncio
async def test_unsupported_intent_refusal():
    """Verify out-of-domain queries trigger immediate deterministic refusal."""
    runtime = build_test_runtime()

    result = await runtime.run("Write a recipe for cooking fish with crypto stock prices")
    assert result.intent == IntentEnum.UNSUPPORTED_INTENT
    assert result.final_response.response_type == ResponseType.ERROR
    assert result.final_response.confidence == 0.0
    assert "REFUSAL:" in result.final_response.answer_text
    assert result.execution_metadata["steps_executed"] == 0


# ===========================================================================
# 11. Full End-to-End Runtime Execution Fixture & Negative Test
# ===========================================================================

@pytest.mark.asyncio
async def test_end_to_end_runtime_mumbai_query():
    """Verify full end-to-end execution flow: Query -> Intent -> Plan -> Parallel Tool Loop -> Sufficiency -> Grounded Synthesis."""
    runtime = build_test_runtime()

    result: AgentRuntimeResult = await runtime.run(
        user_query="Analyze current marine conditions near Mumbai with fishing suitability and weather",
        session_id="sess_prod_test_001",
        thread_id="th_prod_test_001",
    )

    assert result.run_id.startswith("run_")
    assert result.trace_id.startswith("trc_")
    assert result.session_id == "sess_prod_test_001"
    assert result.thread_id == "th_prod_test_001"
    assert result.intent == IntentEnum.FISHING_SUITABILITY

    # 5 steps planned
    assert len(result.plan.steps) == 5
    assert result.execution_metadata["steps_executed"] == 5

    # Evidence collected across all mandatory dimensions
    variables = [e.variable for e in result.all_evidence]
    assert "pfz_point" in variables
    assert "sea_surface_temperature" in variables
    assert "chlorophyll_a" in variables
    assert "significant_wave_height" in variables or "wind" in variables

    assert result.execution_metadata["evidence_completeness"] == 1.0
    assert result.final_response.response_type == ResponseType.FACTUAL
    assert result.final_response.confidence >= 0.85
    assert len(result.claims) >= 3

    assert len(result.final_response.map_overlays) > 0
    assert result.final_response.map_overlays[0].layer_id == "pfz-candidates"


@pytest.mark.asyncio
async def test_negative_end_to_end_mumbai_missing_weather():
    """NEGATIVE E2E TEST: When marine weather is forced unavailable, runtime must degrade completeness & confidence."""
    # Build runtime with weather_fail=True
    runtime = build_test_runtime(weather_fail=True)

    result: AgentRuntimeResult = await runtime.run(
        user_query="Analyze current marine conditions near Mumbai with fishing suitability and weather",
        session_id="sess_neg_test_001",
    )

    assert result.intent == IntentEnum.FISHING_SUITABILITY
    # Weather failed, so completeness is 0.75
    assert result.execution_metadata["evidence_completeness"] == 0.75
    assert result.execution_metadata["data_quality"] == DataQuality.DEGRADED.value
    assert result.final_response.confidence < 0.75

    # Missing mandatory variables explicitly recorded
    assert "marine_operational_conditions" in result.execution_metadata["missing_mandatory"]

    # Final response explicitly states the missing weather limitation
    assert "LIMITATION:" in result.final_response.answer_text
    assert "marine_operational_conditions" in result.final_response.answer_text


# ===========================================================================
# 12. Geographic Policy & Source Trust Registries
# ===========================================================================

def test_geographic_policy_configuration():
    """Verify operational region boundary checks and configurability."""
    assert is_within_operational_region(18.92, 72.83) is True  # Mumbai
    assert is_within_operational_region(10.0, 75.0) is True   # Arabian Sea
    assert is_within_operational_region(40.71, -74.0) is False  # New York (Atlantic)

    policy = get_operational_region_policy()
    assert policy.region_id == "INDIAN_OCEAN"
    assert policy.min_lat == -15.0
    assert policy.max_lat == 30.0


def test_source_policy_registry():
    """Verify source trust tiers, authorized variables, and max freshness windows."""
    sources = SourcePolicyRegistry()

    assert sources.is_authorized_variable("incois_wfs", "pfz_point") is True
    tier, max_age = sources.get_trust_tier("incois_wfs")
    assert tier == SourceTrustTier.OPERATIONAL
    assert max_age.total_seconds() >= 36 * 3600

    # INCOIS OSF & IMD are operational
    assert sources.is_authorized_variable("incois_osf_ocean_state", "significant_wave_height") is True
    assert sources.is_authorized_variable("imd_marine_warning", "fishermen_warning") is True

    # NOAA Weather is operational
    assert sources.is_authorized_variable("noaa_weather", "marine_weather_forecast") is True

    # Untrusted / unknown source
    tier_unk, _ = sources.get_trust_tier("unverified_third_party")
    assert tier_unk == SourceTrustTier.UNTRUSTED
