from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from pydantic import BaseModel, Field

from orca.schemas.orca_contract import DataQuality, Evidence, FinalResponse, Geometry, utc_now


class EvidenceRequirement(BaseModel):
    """Explicit requirement for a specific evidence variable under an intent."""
    variable: str
    mandatory: bool = True
    min_quality: DataQuality = DataQuality.DEGRADED
    max_age_hours: float | None = None
    geographic_required: bool = True
    temporal_required: bool = True
    description: str = ""


class SufficiencyEvaluationResult(BaseModel):
    """Separated evaluation metrics for evidence sufficiency."""
    is_sufficient: bool
    evidence_quality: DataQuality
    evidence_completeness: float = Field(..., ge=0.0, le=1.0)
    answer_confidence: float = Field(..., ge=0.0, le=1.0)
    missing_mandatory: list[str] = Field(default_factory=list)
    missing_optional: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class IntentEnum(str, Enum):
    PFZ_SEEKING = "PFZ_SEEKING"
    FISHING_SUITABILITY = "FISHING_SUITABILITY"
    WEATHER_FORECAST = "WEATHER_FORECAST"
    OCEAN_METRICS = "OCEAN_METRICS"
    ADVISORY_SEARCH = "ADVISORY_SEARCH"
    SPATIAL_QUERY = "SPATIAL_QUERY"
    TRANSLATION = "TRANSLATION"
    SCENARIO_SIMULATION = "SCENARIO_SIMULATION"
    GENERAL_MARINE_QUERY = "GENERAL_MARINE_QUERY"
    UNSUPPORTED_INTENT = "UNSUPPORTED_INTENT"


class PlanStep(BaseModel):
    step_id: str
    tool_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 2
    status: Literal["pending", "running", "completed", "failed", "fallback_applied"] = "pending"
    error: str | None = None


class TaskPlan(BaseModel):
    plan_id: str
    intent: IntentEnum
    query: str
    steps: list[PlanStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=utc_now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClaimGrounding(BaseModel):
    claim_text: str
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    grounding_status: Literal["grounded", "inference", "unsupported"] = "grounded"
    confidence_penalty: float = 0.0


class AgentRuntimeResult(BaseModel):
    run_id: str
    trace_id: str
    session_id: str
    thread_id: str
    intent: IntentEnum
    plan: TaskPlan
    final_response: FinalResponse
    all_evidence: list[Evidence] = Field(default_factory=list)
    claims: list[ClaimGrounding] = Field(default_factory=list)
    execution_metadata: dict[str, Any] = Field(default_factory=dict)
