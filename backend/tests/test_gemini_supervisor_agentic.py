"""Hermetic and Live Integration Tests for ORCA Autonomous Gemini Supervisor,

Web Search Grounding, URL Context Inspection, Multi-Source Marine Data,
and Deep Research Engine (ISRO PS 26176).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import pytest

from orca.agents.gemini_supervisor import (
    DEEP_RESEARCH_AGENT,
    FAST_MODEL,
    ORCA_FUNCTION_DECLARATIONS,
    GeminiSupervisor,
    UrlContextReader,
    WebSearchGrounder,
)
from orca.api.events import AgentEvent, AgentEventType, utc_now
from orca.data.adapters.copernicus_marine import CopernicusMarineAdapter
from orca.data.adapters.noaa_ndbc import NOAANDBCAdapter
from orca.data.adapters.open_meteo_marine import OpenMeteoMarineAdapter
from orca.database.repositories.event_journal_repo import EventJournalRepository
from orca.schemas.orca_contract import (
    AccessMethod,
    DataQuality,
    Evidence,
    EvidenceItem,
    EvidenceType,
    FreshnessClass,
    Geometry,
    SourceMetadata,
    compute_freshness,
)
from orca.services.event_broker import OrcaEventBroker
from orca.verification.scientific import ScientificVerifier, SourceArbitrator


# ===========================================================================
# 1. Supervisor Execution Mode Determination (Fast Mode vs Deep Research)
# ===========================================================================
def test_supervisor_execution_mode_detection():
    supervisor = GeminiSupervisor()

    # Fast mode questions
    assert supervisor.determine_execution_mode("What are current wave heights near Goa?") == "FAST"
    assert supervisor.determine_execution_mode("Should a small fishing vessel leave Malim tomorrow?") == "FAST"
    assert supervisor.determine_execution_mode("What is the SST front at 15.45, 73.80?") == "FAST"

    # Deep Research questions
    assert supervisor.determine_execution_mode(
        "Research why fish productivity has declined along the west coast of India over the last five years and compare satellite, oceanographic and fisheries evidence."
    ) == "DEEP_RESEARCH"
    assert supervisor.determine_execution_mode(
        "Investigate the causes of declining sardine catches near Kochi and distinguish correlation from causation"
    ) == "DEEP_RESEARCH"

    # Explicit research flag
    assert supervisor.determine_execution_mode("What is the SST?", explicit_research=True) == "DEEP_RESEARCH"


# ===========================================================================
# 2. Tool Function Declarations Contract Validation
# ===========================================================================
def test_orca_function_declarations_schema():
    assert len(ORCA_FUNCTION_DECLARATIONS) == 12
    tool_names = {t["name"] for t in ORCA_FUNCTION_DECLARATIONS}
    expected_names = {
        "get_pfz",
        "get_marine_weather",
        "get_sst",
        "get_chlorophyll",
        "get_wave_conditions",
        "get_ocean_currents",
        "check_imbl_geofence",
        "check_marine_protected_area",
        "calculate_safe_route",
        "analyze_ocean_productivity",
        "check_cyclone_alerts",
        "get_advisories",
    }
    assert tool_names == expected_names
    for decl in ORCA_FUNCTION_DECLARATIONS:
        assert decl["type"] == "function"
        assert "description" in decl and len(decl["description"]) > 10
        assert "parameters" in decl
        assert decl["parameters"]["type"] == "object"
        assert "properties" in decl["parameters"]


# ===========================================================================
# 3. Web Search Grounder & URL Context Reader
# ===========================================================================
@pytest.mark.asyncio
async def test_web_search_grounder():
    grounder = WebSearchGrounder(timeout_sec=5.0)
    results = await grounder.search("cyclone warning and high wave alert Indian coast")

    assert len(results) >= 2
    for r in results:
        assert "title" in r and len(r["title"]) > 0
        assert "url" in r and r["url"].startswith("http")
        assert "domain" in r
        assert "snippet" in r
        assert r["source_type"] in ("OFFICIAL ADVISORY", "SCIENTIFIC SOURCE", "MARINE DATA", "WEB SEARCH")
        assert "retrieved_at" in r


@pytest.mark.asyncio
async def test_url_context_reader():
    reader = UrlContextReader(timeout_sec=5.0)
    res = await reader.inspect_url("https://incois.gov.in/site/index.jsp")

    assert res["url"] == "https://incois.gov.in/site/index.jsp"
    assert "incois.gov.in" in res["domain"]
    assert "title" in res
    assert "summary" in res
    assert "retrieved_at" in res


# ===========================================================================
# 4. Multi-Source Marine Adapters (Open-Meteo, NOAA NDBC, Copernicus)
# ===========================================================================
@pytest.mark.asyncio
async def test_open_meteo_marine_adapter():
    adapter = OpenMeteoMarineAdapter()
    geom = Geometry(lat=15.45, lon=73.80)
    evidences = await adapter.fetch_marine_forecast(geom)

    assert len(evidences) >= 3
    variables = {e.variable for e in evidences}
    assert "significant_wave_height" in variables
    assert "wave_period" in variables

    for ev in evidences:
        assert ev.source.organization == "Open-Meteo"
        assert ev.metadata["provider"] == "Open-Meteo"
        assert "warning" in ev.metadata
        assert ev.evidence_type == EvidenceType.FORECAST


@pytest.mark.asyncio
async def test_noaa_ndbc_adapter():
    adapter = NOAANDBCAdapter()
    geom = Geometry(lat=15.45, lon=73.80)
    evidences = await adapter.fetch_station_observations(geom)

    assert len(evidences) >= 1
    for ev in evidences:
        assert "ndbc" in ev.source.source_id.lower()
        assert ev.metadata["provider"] == "NOAA NDBC"
        assert ev.evidence_type == EvidenceType.OBSERVATION


def test_copernicus_marine_adapter_waves_and_currents():
    adapter = CopernicusMarineAdapter()
    geom = Geometry(lat=15.45, lon=73.80)

    waves = adapter.extract_wave_ocean_state(geom)
    assert len(waves) >= 1
    assert waves[0].variable == "significant_wave_height"

    currents = adapter.extract_surface_currents(geom)
    assert currents.variable == "surface_current"
    assert "velocity_m_s" in currents.value or isinstance(currents.value, dict)


# ===========================================================================
# 5. Cross-Source Conflict Arbitration
# ===========================================================================
def test_source_arbitrator_conflict_detection():
    arbitrator = SourceArbitrator()
    geom = Geometry(lat=15.45, lon=73.80)
    now = utc_now()

    # Create conflicting wave observations
    incois_meta = SourceMetadata(source_id="incois_osf_waves", organization="INCOIS", dataset="OSF", authority="official", access=AccessMethod.API)
    open_meteo_meta = SourceMetadata(source_id="open_meteo_marine", organization="Open-Meteo", dataset="Forecast", authority="commercial", access=AccessMethod.API)

    ev_incois = Evidence(
        source=incois_meta,
        variable="significant_wave_height",
        value=1.2,
        unit="m",
        evidence_type=EvidenceType.OBSERVATION,
        geometry=geom,
        observed_at=now,
        quality=DataQuality.GOOD,
    )
    ev_meteo = Evidence(
        source=open_meteo_meta,
        variable="significant_wave_height",
        value=1.8,  # Difference is 0.6m > threshold 0.3m
        unit="m",
        evidence_type=EvidenceType.FORECAST,
        geometry=geom,
        observed_at=now,
        quality=DataQuality.GOOD,
    )

    arbitration = arbitrator.arbitrate([ev_incois, ev_meteo])

    assert len(arbitration.conflicts) >= 1
    conflict = arbitration.conflicts[0]
    assert conflict.variable == "significant_wave_height"
    assert conflict.resolution == "report_spread"
    assert conflict.preferred_source == "incois_osf_waves"


# ===========================================================================
# 6. Full Supervisor SSE Streaming Lifecycle
# ===========================================================================
@pytest.mark.asyncio
async def test_gemini_supervisor_streaming_run():
    repo = EventJournalRepository()
    await repo.ensure_tables_exist()

    run_id = f"run_sup_test_{datetime.now().strftime('%H%M%S')}"
    broker = OrcaEventBroker(run_id=run_id, thread_id="th_test", trace_id="trc_test", repository=repo)

    supervisor = GeminiSupervisor()
    query = "Should a small fishing vessel leave Malim tomorrow morning? Check wave heights and nearest PFZ."

    await supervisor.run_supervisor_stream(
        broker=broker,
        query=query,
        coordinates=Geometry(lat=15.45, lon=73.80),
        sector="GOA",
    )

    events = await repo.get_events(run_id=run_id)
    event_types = [e.event_type.value for e in events]

    # Verify canonical event chain
    assert "RUN_STARTED" in event_types
    assert "PLAN_CREATED" in event_types
    assert "SEARCH_QUERY" in event_types
    assert "SEARCH_RESULT" in event_types
    assert "SOURCE_OPENED" in event_types
    assert "SOURCE_ADDED" in event_types
    assert "DATA_SOURCE_STARTED" in event_types
    assert "DATA_SOURCE_COMPLETED" in event_types
    assert "EVIDENCE_CHECK" in event_types
    assert "SYNTHESIS_STARTED" in event_types
    assert "CITATION_ADDED" in event_types
    assert "SYNTHESIS_COMPLETED" in event_types
    assert "RUN_COMPLETED" in event_types

    # Invariants:
    # 1. Monotonic sequence numbering
    seqs = [e.sequence for e in events]
    assert seqs == list(range(1, len(events) + 1))

    # 2. Synthesis completed payload contains citations
    synth_ev = next(e for e in events if e.event_type == AgentEventType.SYNTHESIS_COMPLETED)
    assert "answer_text" in synth_ev.payload
    assert "citations" in synth_ev.payload
    assert len(synth_ev.payload["citations"]) > 0


# ===========================================================================
# 7. Deep Research Mode Lifecycle & Progress
# ===========================================================================
@pytest.mark.asyncio
async def test_deep_research_mode_streaming_lifecycle():
    repo = EventJournalRepository()
    await repo.ensure_tables_exist()

    run_id = f"run_dr_test_{datetime.now().strftime('%H%M%S')}"
    broker = OrcaEventBroker(run_id=run_id, thread_id="th_dr_test", trace_id="trc_dr_test", repository=repo)

    supervisor = GeminiSupervisor()
    query = "Research why sardine fish productivity has declined around Kochi over the last five years and distinguish correlation from causation."

    await supervisor.run_supervisor_stream(
        broker=broker,
        query=query,
        coordinates=Geometry(lat=9.93, lon=76.26),
        sector="KERALA",
        explicit_research=True,
    )

    events = await repo.get_events(run_id=run_id)
    event_types = [e.event_type.value for e in events]

    assert "RUN_STARTED" in event_types
    assert "RESEARCH_STARTED" in event_types
    assert "RESEARCH_PROGRESS" in event_types
    assert "RESEARCH_COMPLETED" in event_types
    assert "RUN_COMPLETED" in event_types

    dr_start_ev = next(e for e in events if e.event_type == AgentEventType.RESEARCH_STARTED)
    assert dr_start_ev.payload["model"] == DEEP_RESEARCH_AGENT
    assert "plan" in dr_start_ev.payload
