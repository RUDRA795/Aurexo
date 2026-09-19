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
    """LangGraph execution state for ORCA multi-agent intelligence pipelines."""

    # User input and spatial intent
    user_query: str
    coordinates: Geometry | None
    sector: str | None
    landing_center: str | None

    # PFZ retrieval artifacts
    candidate_pfz_points: list[PFZPoint]
    selected_pfz: PFZPoint | None
    pfz_tier_used: str | None
    pfz_unavailable: bool

    # Environmental and meteorological evidence
    sst_evidence: Evidence | None
    chlorophyll_evidence: Evidence | None
    weather_evidence: Evidence | None
    evidence_list: list[Evidence]

    # Verification and provenance
    verification_results: list[VerificationResult]
    provenance_traces: list[dict[str, Any]]

    # Final synthesized output and pipeline control
    final_answer: FinalResponse | None
    error: str | None
    next_node: str | None
