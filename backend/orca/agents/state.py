from __future__ import annotations

from typing import Any, TypedDict

from orca.schemas.orca_contract import (
    Evidence,
    FinalResponse,
    Geometry,
    VerificationResult,
)
from orca.schemas.pfz_contract import PFZPoint


class OrcaGraphState(TypedDict, total=False):
    """LangGraph execution state for ORCA multi-agent intelligence pipelines.

    State field classification:
    - CHECKPOINTED: Persistent run state, execution progress, bounded conversation context,
      normalized evidence references, verification, conflicts, and final synthesis.
    - TRANSIENT: Ephemeral buffers and large raw network arrays (not persisted).
    - LONG-TERM STORE: Cross-thread memories, user preferences, and saved investigation notes.
    """

    # -----------------------------------------------------------------------
    # 1. Thread, Run, and Turn Tracking (CHECKPOINTED)
    # -----------------------------------------------------------------------
    thread_id: str | None
    run_id: str | None
    turn_index: int | None
    intent: str | None
    resumed_from_checkpoint: str | None

    # -----------------------------------------------------------------------
    # 2. User Input and Spatial Scope (CHECKPOINTED)
    # -----------------------------------------------------------------------
    user_query: str
    coordinates: Geometry | None
    sector: str | None
    landing_center: str | None

    # -----------------------------------------------------------------------
    # 3. Plan & Step Execution Progress (CHECKPOINTED)
    # -----------------------------------------------------------------------
    task_plan: dict[str, Any] | None
    completed_steps: list[str]
    failed_steps: list[str]
    retry_counters: dict[str, int]
    progress_metadata: dict[str, Any]

    # -----------------------------------------------------------------------
    # 4. PFZ Retrieval Artifacts (CHECKPOINTED)
    # -----------------------------------------------------------------------
    candidate_pfz_points: list[PFZPoint]
    selected_pfz: PFZPoint | None
    pfz_tier_used: str | None
    pfz_unavailable: bool

    # -----------------------------------------------------------------------
    # 5. Environmental & Advisory Evidence (CHECKPOINTED)
    # -----------------------------------------------------------------------
    sst_evidence: Evidence | None
    chlorophyll_evidence: Evidence | None
    weather_evidence: Evidence | None
    evidence_list: list[Evidence]

    # -----------------------------------------------------------------------
    # 6. Verification, Conflicts, and Sufficiency (CHECKPOINTED)
    # -----------------------------------------------------------------------
    verification_results: list[VerificationResult]
    conflict_records: list[dict[str, Any]]
    sufficiency_result: dict[str, Any] | None
    provenance_traces: list[dict[str, Any]]

    # -----------------------------------------------------------------------
    # 7. Multi-Turn Conversation Memory (CHECKPOINTED - Bounded to recent turns)
    # -----------------------------------------------------------------------
    user_history: list[dict[str, Any]]

    # -----------------------------------------------------------------------
    # 8. Final Synthesized Output and Pipeline Control (CHECKPOINTED)
    # -----------------------------------------------------------------------
    final_answer: FinalResponse | None
    error: str | None
    next_node: str | None
