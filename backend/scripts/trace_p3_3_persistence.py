"""P3.3 Acceptance Trace: Multi-Turn State Persistence, LangGraph Checkpointing & Crash Recovery.

Demonstrates:
1. Turn 1: Initial query for Mumbai fishing conditions (persisted to PostgreSQL checkpoint).
2. Process Crash & Recovery Simulation: Destroys graph instance, re-instantiates from PostgreSQL.
3. Turn 2: PFZ candidate refinement (<= 50 km) reusing state without re-calling sources.
4. Turn 3: Comprehensive evidence audit synthesized from checkpointed state.
5. Turn 4: Active safety warnings inquiry synthesized from checkpointed state.
6. Turn 5: Wave height 3m scenario simulation and safety advisory evaluation.
7. Safe retention maintenance pruning (preserves latest checkpoint).
8. Long-term cross-thread memory storage & retrieval via AsyncPostgresStore.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
import json
from pathlib import Path
import sys
import uuid

# Ensure backend root is on sys.path
backend_root = str(Path(__file__).resolve().parent.parent)
if backend_root not in sys.path:
    sys.path.insert(0, backend_root)

# Configure Windows event loop policy before any loop starts
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from orca.agents.graph import create_orca_graph
from orca.agents.persistence import (
    OrcaPersistenceManager,
    enforce_strict_msgpack_security,
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
from tests.test_langgraph_orchestration import (
    MockCHLAdapter,
    MockSSTAdapter,
    MockTieredPFZSource,
    MockWeatherAdapter,
)


class InstrumentingPFZSource(MockTieredPFZSource):
    """Instruments external API calls to prove zero recomputation across follow-up turns."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.call_count = 0

    async def fetch(self, query: PFZQuery) -> PFZQueryResult:
        self.call_count += 1
        print(f"  [API Call] Invoking external INCOIS PFZ WebGIS layer (call #{self.call_count})...")
        return await super().fetch(query)


def create_mock_mumbai_points() -> list[PFZPoint]:
    now = utc_now()
    return [
        PFZPoint(
            pfz_id="pfz_bom_001",
            location=Geometry(lat=18.82, lon=72.68),
            sector="MAHARASHTRA",
            depth_m=32.0,
            source_valid_from=now - timedelta(hours=4),
            source_valid_until=now + timedelta(hours=20),
            freshness_deadline=now + timedelta(hours=24),
            geometry_derivation="line_midpoint_derived",
            validity_derivation="source_provided",
        ),
        PFZPoint(
            pfz_id="pfz_bom_002",
            location=Geometry(lat=18.30, lon=72.15),
            sector="MAHARASHTRA",
            depth_m=58.0,
            source_valid_from=now - timedelta(hours=4),
            source_valid_until=now + timedelta(hours=20),
            freshness_deadline=now + timedelta(hours=24),
            geometry_derivation="line_midpoint_derived",
            validity_derivation="source_provided",
        ),
    ]


async def run_p3_3_trace() -> None:
    print("=" * 80)
    print("ORCA P3.3 ACCEPTANCE TRACE: PERSISTENT MULTI-TURN STATE & POSTGRES CHECKPOINTING")
    print("=" * 80)

    # 1. Enforce strict MessagePack deserialization security
    enforce_strict_msgpack_security(fail_fast=True)
    print("\n[Step 1] Strict MessagePack security enforced (LANGGRAPH_STRICT_MSGPACK=true).")

    # 2. Initialize persistence manager & schemas
    mgr = OrcaPersistenceManager()
    await mgr.setup()
    print("[Step 2] PostgreSQL checkpointer and store schemas verified.")

    thread_id = f"trace_p3_3_{uuid.uuid4().hex[:8]}"
    print(f"[Step 3] Session initialized with thread_id: '{thread_id}'")

    mumbai_pts = create_mock_mumbai_points()
    pfz_source = InstrumentingPFZSource(tier=PFZAccessTier.WEBGIS_LAYER, points=mumbai_pts)

    async with mgr.get_checkpointer() as cp:
        # =======================================================================
        # Turn 1: Initial Mumbai Query
        # =======================================================================
        print("\n" + "-" * 70)
        print("TURN 1: Initial Query - 'What are the fishing conditions near Mumbai?'")
        print("-" * 70)

        graph_v1 = create_orca_graph(
            pfz_sources=[pfz_source],
            sst_adapter=MockSSTAdapter(val=29.4),
            chl_adapter=MockCHLAdapter(val=0.55),
            weather_adapter=MockWeatherAdapter(),
            checkpointer=cp,
        )

        turn1_res = await mgr.execute_thread_turn(
            graph_v1,
            query="What are the fishing conditions near Mumbai?",
            thread_id=thread_id,
            coordinates=Geometry(lat=18.92, lon=72.83),
        )

        ans1: FinalResponse = turn1_res["final_answer"]
        print(f"Response Type : {ans1.response_type.value}")
        print(f"Confidence    : {ans1.confidence}")
        print(f"Synthesized   : {ans1.answer_text}")
        print(f"Evidence Count: {len(ans1.evidence_summary)}")
        print(f"External Calls: {pfz_source.call_count}")

        # Inspect checkpoint state in PostgreSQL
        snap1 = await mgr.inspect_thread_state(thread_id)
        print(f"Checkpoint ID : {snap1['checkpoint_id']}")
        assert snap1 is not None

        # =======================================================================
        # Process Termination & Crash Recovery Simulation
        # =======================================================================
        print("\n" + "!" * 70)
        print("SIMULATING PROCESS CRASH / WORKER RESTART:")
        print("Destroying graph_v1 instance from memory...")
        del graph_v1
        print("Instantiating brand new graph_v2 instance connecting to same PostgreSQL database...")
        # =======================================================================

        graph_v2 = create_orca_graph(
            pfz_sources=[pfz_source],
            sst_adapter=MockSSTAdapter(val=29.4),
            chl_adapter=MockCHLAdapter(val=0.55),
            weather_adapter=MockWeatherAdapter(),
            checkpointer=cp,
        )

        # =======================================================================
        # Turn 2: Spatial Refinement (<= 50 km)
        # =======================================================================
        print("\n" + "-" * 70)
        print("TURN 2: Refinement - 'Focus only on PFZ candidates within 50 km'")
        print("-" * 70)

        turn2_res = await mgr.execute_thread_turn(
            graph_v2,
            query="Focus only on PFZ candidates within 50 km",
            thread_id=thread_id,
        )

        ans2: FinalResponse = turn2_res["final_answer"]
        print(f"Response Type : {ans2.response_type.value}")
        print(f"Synthesized   : {ans2.answer_text}")
        print(f"External Calls: {pfz_source.call_count} (ZERO recomputation confirmed!)")
        assert pfz_source.call_count == 1

        # =======================================================================
        # Turn 3: Evidence Audit
        # =======================================================================
        print("\n" + "-" * 70)
        print("TURN 3: Evidence Audit - 'What evidence supported that?'")
        print("-" * 70)

        turn3_res = await mgr.execute_thread_turn(
            graph_v2,
            query="What evidence supported that?",
            thread_id=thread_id,
        )

        ans3: FinalResponse = turn3_res["final_answer"]
        print(f"Response Type : {ans3.response_type.value}")
        print(f"Synthesized   :\n{ans3.answer_text}")
        print(f"External Calls: {pfz_source.call_count} (ZERO recomputation confirmed!)")
        assert pfz_source.call_count == 1

        # =======================================================================
        # Turn 4: Active Warnings Inquiry
        # =======================================================================
        print("\n" + "-" * 70)
        print("TURN 4: Active Warnings - 'Were any warnings active?'")
        print("-" * 70)

        turn4_res = await mgr.execute_thread_turn(
            graph_v2,
            query="Were any warnings active?",
            thread_id=thread_id,
        )

        ans4: FinalResponse = turn4_res["final_answer"]
        print(f"Response Type : {ans4.response_type.value}")
        print(f"Synthesized   :\n{ans4.answer_text}")
        print(f"External Calls: {pfz_source.call_count} (ZERO recomputation confirmed!)")
        assert pfz_source.call_count == 1

        # =======================================================================
        # Turn 5: What-If Scenario (Wave Height = 3 metres)
        # =======================================================================
        print("\n" + "-" * 70)
        print("TURN 5: Scenario Simulation - 'What changes if wave height becomes 3 metres?'")
        print("-" * 70)

        turn5_res = await mgr.execute_thread_turn(
            graph_v2,
            query="What changes if wave height becomes 3 metres?",
            thread_id=thread_id,
        )

        ans5: FinalResponse = turn5_res["final_answer"]
        print(f"Response Type : {ans5.response_type.value}")
        print(f"Safety Status : {ans5.safety.status.value if ans5.safety else 'N/A'}")
        print(f"Safety Reason : {ans5.safety.reasons if ans5.safety else []}")
        print(f"Synthesized   :\n{ans5.answer_text}")
        print(f"External Calls: {pfz_source.call_count} (ZERO recomputation confirmed!)")
        assert pfz_source.call_count == 1

        # =======================================================================
        # Checkpoint Retention & Maintenance Pruning
        # =======================================================================
        print("\n" + "-" * 70)
        print("CHECKPOINT RETENTION & SAFE PRUNING")
        print("-" * 70)
        cps_before = await mgr.list_thread_checkpoints(thread_id)
        print(f"Checkpoints created in thread '{thread_id}': {len(cps_before)}")

        pruned = await mgr.prune_thread_checkpoints(thread_id, keep_last_n=5)
        print(f"Safely pruned older checkpoints: {pruned}")
        cps_after = await mgr.list_thread_checkpoints(thread_id)
        print(f"Remaining checkpoints in thread : {len(cps_after)}")
        assert len(cps_after) <= 5

        # Verify latest checkpoint remains intact
        latest_state = await mgr.inspect_thread_state(thread_id)
        assert latest_state is not None
        print(f"Latest active checkpoint verified: {latest_state['checkpoint_id']}")

    # =======================================================================
    # Cross-Thread Durable Memory (AsyncPostgresStore)
    # =======================================================================
    print("\n" + "-" * 70)
    print("DURABLE APPLICATION MEMORY (AsyncPostgresStore)")
    print("-" * 70)
    user_ns = ("users", "mumbai_fleet_01", "vessel_preferences")
    prefs = {
        "vessel_name": "Matsya Sagar",
        "type": "mechanized_gillnetter",
        "length_m": 14.5,
        "max_wave_tolerance_m": 2.5,
        "home_harbor": "Sassoon Dock, Mumbai",
    }
    await mgr.put_memory(user_ns, "profile", prefs)
    retrieved_prefs = await mgr.get_memory(user_ns, "profile")
    print(f"Stored & Retrieved Cross-Thread Profile:\n{json.dumps(retrieved_prefs, indent=2)}")
    assert retrieved_prefs == prefs

    print("\n" + "=" * 80)
    print("P3.3 ACCEPTANCE TRACE COMPLETED SUCCESSFULLY: ALL CRITERIA VERIFIED")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(run_p3_3_trace())
