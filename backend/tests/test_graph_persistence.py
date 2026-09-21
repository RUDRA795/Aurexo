from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import os
import sys
from typing import Any
import pytest
from pydantic import BaseModel

from orca.agents.graph import create_orca_graph
from orca.agents.persistence import (
    OrcaPersistenceManager,
    VALID_STORE_PREFIXES,
    configure_windows_event_loop_policy,
    enforce_strict_msgpack_security,
    validate_store_namespace,
)
from orca.agents.state import OrcaGraphState
from orca.schemas.orca_contract import (
    AccessMethod,
    DataQuality,
    Evidence,
    FinalResponse,
    Geometry,
    ResponseType,
    SafetyStatus,
    SourceMetadata,
    utc_now,
)
from orca.schemas.pfz_contract import PFZAccessTier, PFZPoint, PFZQuery, PFZQueryResult
from tests.test_langgraph_orchestration import (
    MockCHLAdapter,
    MockSSTAdapter,
    MockTieredPFZSource,
    MockWeatherAdapter,
)


class CountingPFZSource(MockTieredPFZSource):
    """Mock source that records call count to verify zero-recomputation invariants."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.call_count = 0

    async def fetch(self, query: PFZQuery) -> PFZQueryResult:
        self.call_count += 1
        return await super().fetch(query)


def _make_mumbai_pfz_points() -> list[PFZPoint]:
    now = utc_now()
    return [
        PFZPoint(
            pfz_id="pfz_mumbai_near",
            location=Geometry(lat=18.85, lon=72.70),
            sector="MAHARASHTRA",
            depth_m=35.0,
            source_valid_from=now - timedelta(hours=6),
            source_valid_until=now + timedelta(hours=18),
            freshness_deadline=now + timedelta(hours=24),
            geometry_derivation="line_midpoint_derived",
            validity_derivation="source_provided",
        ),
        PFZPoint(
            pfz_id="pfz_mumbai_far",
            location=Geometry(lat=18.15, lon=72.05),
            sector="MAHARASHTRA",
            depth_m=55.0,
            source_valid_from=now - timedelta(hours=6),
            source_valid_until=now + timedelta(hours=18),
            freshness_deadline=now + timedelta(hours=24),
            geometry_derivation="line_midpoint_derived",
            validity_derivation="source_provided",
        ),
    ]


# ===========================================================================
# 1. Setup & Schema Initializations
# ===========================================================================
@pytest.mark.asyncio
async def test_checkpointer_and_store_setup():
    """Verify official LangGraph PostgreSQL setup executes idempotently."""
    mgr = OrcaPersistenceManager()
    await mgr.setup()
    # Check that checkpointer and store can be opened
    async with mgr.get_checkpointer() as cp:
        assert cp is not None
    async with mgr.get_store() as store:
        assert store is not None


# ===========================================================================
# 2. Strict MessagePack Security
# ===========================================================================
def test_strict_msgpack_security_enforcement():
    """Verify LANGGRAPH_STRICT_MSGPACK enforcement and safe/unauthorized class handling."""
    assert enforce_strict_msgpack_security(fail_fast=True) is True
    assert os.getenv("LANGGRAPH_STRICT_MSGPACK") == "true"

    from langgraph.checkpoint.serde._msgpack import SAFE_MSGPACK_TYPES, STRICT_MSGPACK_ENABLED
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    assert STRICT_MSGPACK_ENABLED is True
    assert ("orca.schemas.orca_contract", "Geometry") in SAFE_MSGPACK_TYPES
    assert ("orca.schemas.pfz_contract", "PFZPoint") in SAFE_MSGPACK_TYPES
    assert ("orca.schemas.agent_runtime", "IntentEnum") in SAFE_MSGPACK_TYPES

    serializer = JsonPlusSerializer()

    # 1. Authorized class serialization/deserialization
    geo = Geometry(lat=18.92, lon=72.83)
    type_str, payload = serializer.dumps_typed(geo)
    assert type_str == "msgpack"
    loaded_geo = serializer.loads_typed((type_str, payload))
    assert isinstance(loaded_geo, Geometry)
    assert loaded_geo.lat == 18.92 and loaded_geo.lon == 72.83

    # 2. Unauthorized arbitrary class must NOT be deserialized to class instance
    class MaliciousPayload(BaseModel):
        payload: str = "arbitrary_code"

    type_str_mal, payload_mal = serializer.dumps_typed(MaliciousPayload())
    loaded_mal = serializer.loads_typed((type_str_mal, payload_mal))
    # In strict mode, serializer blocks instantiation of classes outside safe allowlist
    assert not isinstance(loaded_mal, MaliciousPayload)
    assert isinstance(loaded_mal, dict)


# ===========================================================================
# 3. Thread State Persistence & Isolation
# ===========================================================================
@pytest.mark.asyncio
async def test_thread_state_persistence_and_isolation():
    """Verify thread persistence across turns and strict isolation between threads."""
    mgr = OrcaPersistenceManager()
    pts = _make_mumbai_pfz_points()
    src = MockTieredPFZSource(tier=PFZAccessTier.WEBGIS_LAYER, points=pts)

    async with mgr.get_checkpointer() as cp:
        graph = create_orca_graph(
            pfz_sources=[src],
            sst_adapter=MockSSTAdapter(val=29.0),
            chl_adapter=MockCHLAdapter(val=0.45),
            checkpointer=cp,
        )

        thread_a = f"th_iso_a_{utc_now().strftime('%Y%m%d%H%M%S%f')}"
        thread_b = f"th_iso_b_{utc_now().strftime('%Y%m%d%H%M%S%f')}"

        # Run Turn 1 on Thread A (Mumbai)
        res_a = await mgr.execute_thread_turn(
            graph,
            query="What are conditions near Mumbai?",
            thread_id=thread_a,
            coordinates=Geometry(lat=18.92, lon=72.83),
        )
        assert res_a["selected_pfz"].pfz_id == "pfz_mumbai_near"

        # Run Turn 1 on Thread B (Empty/Goa)
        res_b = await mgr.execute_thread_turn(
            graph,
            query="Where is the nearest PFZ for Goa coast?",
            thread_id=thread_b,
            coordinates=Geometry(lat=15.45, lon=73.80),
        )

        # Verify checkpoints for Thread A and Thread B are strictly isolated
        cps_a = await mgr.list_thread_checkpoints(thread_a)
        cps_b = await mgr.list_thread_checkpoints(thread_b)
        assert len(cps_a) > 0
        assert len(cps_b) > 0

        # State inspection on Thread A shows Mumbai sector
        inspect_a = await mgr.inspect_thread_state(thread_a)
        assert inspect_a is not None
        assert inspect_a["channel_values"]["selected_pfz"].sector == "MAHARASHTRA"


# ===========================================================================
# 4. Durable Application Memory (AsyncPostgresStore)
# ===========================================================================
@pytest.mark.asyncio
async def test_store_namespace_validation_and_crud():
    """Verify AsyncPostgresStore namespace prefix validation and cross-thread operations."""
    mgr = OrcaPersistenceManager()

    # 1. Invalid namespace validation checks
    with pytest.raises(ValueError, match="at least 2 components"):
        validate_store_namespace(("users",))

    with pytest.raises(ValueError, match="Invalid store namespace prefix"):
        validate_store_namespace(("malicious_prefix", "user_1"))

    with pytest.raises(ValueError, match="must be alphanumeric/slug"):
        validate_store_namespace(("users", "invalid space", "prefs"))

    # 2. Valid namespace operations
    user_ns = ("users", "fisherman_mumbai_01", "vessel_profile")
    profile = {"vessel_name": "Sagar Kanya", "draft_m": 2.2, "home_port": "Mumbai"}

    await mgr.put_memory(user_ns, "specs", profile)
    retrieved = await mgr.get_memory(user_ns, "specs")
    assert retrieved == profile

    # 3. Search memory within approved prefix
    search_res = await mgr.search_memory(("users", "fisherman_mumbai_01"), limit=5)
    assert len(search_res) >= 1
    assert any(item["key"] == "specs" for item in search_res)


# ===========================================================================
# 5. Process Restart & Crash Recovery Simulation
# ===========================================================================
@pytest.mark.asyncio
async def test_process_restart_crash_recovery():
    """Verify that discarding graph instance simulates restart without recomputing work."""
    mgr = OrcaPersistenceManager()
    pts = _make_mumbai_pfz_points()
    counting_src = CountingPFZSource(tier=PFZAccessTier.WEBGIS_LAYER, points=pts)

    thread_id = f"th_crash_{utc_now().strftime('%Y%m%d%H%M%S%f')}"

    async with mgr.get_checkpointer() as cp:
        # Instance 1: Executes Turn 1
        g1 = create_orca_graph(
            pfz_sources=[counting_src],
            sst_adapter=MockSSTAdapter(val=29.1),
            chl_adapter=MockCHLAdapter(val=0.48),
            checkpointer=cp,
        )
        r1 = await mgr.execute_thread_turn(
            g1,
            query="Fishing conditions near Mumbai",
            thread_id=thread_id,
            coordinates=Geometry(lat=18.92, lon=72.83),
        )
        assert r1["selected_pfz"].pfz_id == "pfz_mumbai_near"
        assert counting_src.call_count == 1

        # Simulate process termination / crash: Delete instance 1
        del g1

        # Instance 2: Brand new graph instance connecting to same PostgreSQL checkpointer
        g2 = create_orca_graph(
            pfz_sources=[counting_src],
            sst_adapter=MockSSTAdapter(val=29.1),
            chl_adapter=MockCHLAdapter(val=0.48),
            checkpointer=cp,
        )

        # Execute Turn 2 on instance 2
        r2 = await mgr.execute_thread_turn(
            g2,
            query="Focus only on PFZ candidates within 50 km",
            thread_id=thread_id,
        )
        assert r2["selected_pfz"].pfz_id == "pfz_mumbai_near"
        # Zero additional calls to external source
        assert counting_src.call_count == 1
        assert "Refined Assessment (within 50 km)" in r2["final_answer"].answer_text


# ===========================================================================
# 6. Deliberate Graph Interruption & Resume
# ===========================================================================
@pytest.mark.asyncio
async def test_graph_interruption_and_resume():
    """Verify LangGraph pause before SynthesizerNode and subsequent resumption."""
    mgr = OrcaPersistenceManager()
    pts = _make_mumbai_pfz_points()
    src = MockTieredPFZSource(tier=PFZAccessTier.WEBGIS_LAYER, points=pts)

    thread_id = f"th_interrupt_{utc_now().strftime('%Y%m%d%H%M%S%f')}"
    cfg = {"configurable": {"thread_id": thread_id}}

    async with mgr.get_checkpointer() as cp:
        graph = create_orca_graph(
            pfz_sources=[src],
            sst_adapter=MockSSTAdapter(),
            chl_adapter=MockCHLAdapter(),
            checkpointer=cp,
            interrupt_before=["SynthesizerNode"],
        )

        # Run until interruption
        await graph.ainvoke(
            {
                "user_query": "Mumbai fishing inquiry",
                "coordinates": Geometry(lat=18.92, lon=72.83),
                "thread_id": thread_id,
            },
            config=cfg,
        )

        # Verify state is paused at SynthesizerNode
        state_snap = await graph.aget_state(cfg)
        assert state_snap.next == ("SynthesizerNode",)
        assert state_snap.values.get("selected_pfz") is not None
        assert state_snap.values.get("final_answer") is None

        # Resume execution
        resumed = await mgr.resume_thread(graph, thread_id=thread_id)
        state_snap_after = await graph.aget_state(cfg)
        assert state_snap_after.next == ()
        assert resumed.get("final_answer") is not None
        assert resumed["final_answer"].response_type == ResponseType.FACTUAL


# ===========================================================================
# 7. Complete 5-Turn Continuity & Zero Recomputation
# ===========================================================================
@pytest.mark.asyncio
async def test_multi_turn_5_turn_sequence_and_no_recomputation():
    """Verify full 5-turn sequence: Mumbai conditions -> 50km focus -> Evidence audit

    -> Active warnings -> Wave scenario, with exactly 1 external source fetch.
    """
    mgr = OrcaPersistenceManager()
    pts = _make_mumbai_pfz_points()
    counting_src = CountingPFZSource(tier=PFZAccessTier.WEBGIS_LAYER, points=pts)

    thread_id = f"th_5turn_{utc_now().strftime('%Y%m%d%H%M%S%f')}"

    async with mgr.get_checkpointer() as cp:
        graph = create_orca_graph(
            pfz_sources=[counting_src],
            sst_adapter=MockSSTAdapter(val=29.2),
            chl_adapter=MockCHLAdapter(val=0.52),
            weather_adapter=MockWeatherAdapter(),
            checkpointer=cp,
        )

        # Turn 1: Mumbai conditions
        t1 = await mgr.execute_thread_turn(
            graph,
            query="What are the fishing conditions near Mumbai?",
            thread_id=thread_id,
            coordinates=Geometry(lat=18.92, lon=72.83),
        )
        assert t1["selected_pfz"].pfz_id == "pfz_mumbai_near"
        assert counting_src.call_count == 1
        assert "pfz_mumbai_near" in t1["final_answer"].answer_text

        # Turn 2: Focus within 50 km
        t2 = await mgr.execute_thread_turn(
            graph,
            query="Focus only on PFZ candidates within 50 km",
            thread_id=thread_id,
        )
        assert t2["selected_pfz"].pfz_id == "pfz_mumbai_near"
        assert counting_src.call_count == 1
        assert "Refined Assessment (within 50 km)" in t2["final_answer"].answer_text

        # Turn 3: Evidence audit
        t3 = await mgr.execute_thread_turn(
            graph,
            query="What evidence supported that?",
            thread_id=thread_id,
        )
        assert counting_src.call_count == 1
        assert "Evidence Audit" in t3["final_answer"].answer_text
        assert "pfz_point" in t3["final_answer"].answer_text

        # Turn 4: Active warnings
        t4 = await mgr.execute_thread_turn(
            graph,
            query="Were any warnings active?",
            thread_id=thread_id,
        )
        assert counting_src.call_count == 1
        assert "Warnings Status" in t4["final_answer"].answer_text

        # Turn 5: Wave scenario
        t5 = await mgr.execute_thread_turn(
            graph,
            query="What changes if wave height becomes 3 metres?",
            thread_id=thread_id,
        )
        assert counting_src.call_count == 1
        ans5 = t5["final_answer"]
        assert ans5.response_type == ResponseType.ADVISORY
        assert ans5.safety is not None
        assert ans5.safety.status == SafetyStatus.HIGH_RISK
        assert "Scenario Impact Analysis" in ans5.answer_text
        assert "Rough Sea State" in ans5.answer_text

        # Invariant: Exactly 1 external fetch for all 5 turns
        assert counting_src.call_count == 1


# ===========================================================================
# 8. Bounded State Invariants
# ===========================================================================
@pytest.mark.asyncio
async def test_bounded_state_invariants():
    """Verify that user_history is bounded to max 5 turns across extended interactions."""
    mgr = OrcaPersistenceManager()
    pts = _make_mumbai_pfz_points()
    src = MockTieredPFZSource(tier=PFZAccessTier.WEBGIS_LAYER, points=pts)

    thread_id = f"th_bounded_{utc_now().strftime('%Y%m%d%H%M%S%f')}"

    async with mgr.get_checkpointer() as cp:
        graph = create_orca_graph(
            pfz_sources=[src],
            sst_adapter=MockSSTAdapter(),
            chl_adapter=MockCHLAdapter(),
            checkpointer=cp,
        )

        for i in range(7):
            res = await mgr.execute_thread_turn(
                graph,
                query=f"Turn query {i} for Mumbai fishing",
                thread_id=thread_id,
                coordinates=Geometry(lat=18.92, lon=72.83),
            )
            assert len(res.get("user_history", [])) <= 5


# ===========================================================================
# 9. Checkpoint Retention & Pruning
# ===========================================================================
@pytest.mark.asyncio
async def test_safe_checkpoint_pruning():
    """Verify safe maintenance pruning keeps last N checkpoints and preserves latest."""
    mgr = OrcaPersistenceManager()
    pts = _make_mumbai_pfz_points()
    src = MockTieredPFZSource(tier=PFZAccessTier.WEBGIS_LAYER, points=pts)

    thread_id = f"th_prune_{utc_now().strftime('%Y%m%d%H%M%S%f')}"

    async with mgr.get_checkpointer() as cp:
        graph = create_orca_graph(
            pfz_sources=[src],
            sst_adapter=MockSSTAdapter(),
            chl_adapter=MockCHLAdapter(),
            checkpointer=cp,
        )

        # Run 3 distinct turns to produce multiple checkpoints
        await mgr.execute_thread_turn(graph, query="Turn 1", thread_id=thread_id, coordinates=Geometry(lat=18.92, lon=72.83))
        await mgr.execute_thread_turn(graph, query="Turn 2", thread_id=thread_id)
        await mgr.execute_thread_turn(graph, query="Turn 3", thread_id=thread_id)

    cps_before = await mgr.list_thread_checkpoints(thread_id)
    assert len(cps_before) > 3

    # Prune keeping last 3
    pruned = await mgr.prune_thread_checkpoints(thread_id, keep_last_n=3)
    assert pruned > 0

    cps_after = await mgr.list_thread_checkpoints(thread_id)
    assert len(cps_after) <= 3

    # State can still be inspected and valid
    inspect_res = await mgr.inspect_thread_state(thread_id)
    assert inspect_res is not None
    assert inspect_res["checkpoint_id"] == cps_after[0]["checkpoint_id"]


@pytest.mark.asyncio
async def test_prune_invariants_and_error_handling():
    """Verify pruning parameter validation and retention guarantees."""
    mgr = OrcaPersistenceManager()

    # Invalid keep_last_n
    with pytest.raises(ValueError, match="keep_last_n must be at least 1"):
        await mgr.prune_thread_checkpoints("dummy_thread", keep_last_n=0)

    # Empty thread returns 0
    non_existent = f"th_empty_{utc_now().strftime('%Y%m%d%H%M%S%f')}"
    pruned = await mgr.prune_thread_checkpoints(non_existent, keep_last_n=5)
    assert pruned == 0


@pytest.mark.asyncio
async def test_telemetry_correlation_in_checkpoints():
    """Verify telemetry correlation metadata (thread_id, turn_index, provenance) is captured."""
    mgr = OrcaPersistenceManager()
    pts = _make_mumbai_pfz_points()
    src = MockTieredPFZSource(tier=PFZAccessTier.WEBGIS_LAYER, points=pts)

    thread_id = f"th_telem_{utc_now().strftime('%Y%m%d%H%M%S%f')}"

    async with mgr.get_checkpointer() as cp:
        graph = create_orca_graph(
            pfz_sources=[src],
            sst_adapter=MockSSTAdapter(),
            chl_adapter=MockCHLAdapter(),
            checkpointer=cp,
        )

        res = await mgr.execute_thread_turn(
            graph,
            query="Telemetry verification for Mumbai",
            thread_id=thread_id,
            coordinates=Geometry(lat=18.92, lon=72.83),
        )

        assert res.get("thread_id") == thread_id
        assert res.get("turn_index") == 1
        traces = res.get("provenance_traces", [])
        assert len(traces) >= 3
        node_names = [t.get("node") for t in traces]
        assert "SupervisorNode" in node_names
        assert "PFZAgentNode" in node_names
        assert "SynthesizerNode" in node_names

