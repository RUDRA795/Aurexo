"""ORCA Milestone P3.5: Evaluation Metrics and Scorecard Models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

from orca.evaluation.dataset import EvaluationCategory
from orca.schemas.agent_runtime import IntentEnum
from orca.schemas.orca_contract import ResponseType, utc_now


class CaseEvaluationResult(BaseModel):
    """Evaluation result for an individual benchmark case."""
    case_id: str
    category: EvaluationCategory
    query: str
    passed: bool
    intent_passed: bool
    actual_intent: IntentEnum
    expected_intent: IntentEnum
    tool_precision: float = 1.0
    tool_recall: float = 1.0
    selected_tools: list[str] = Field(default_factory=list)
    required_tools: list[str] = Field(default_factory=list)
    evidence_completeness: float = 1.0
    groundedness_passed: bool = True
    forbidden_claims_found: list[str] = Field(default_factory=list)
    response_type_passed: bool = True
    actual_response_type: ResponseType
    expected_response_type: ResponseType
    duration_ms: float = 0.0
    failure_reasons: list[str] = Field(default_factory=list)


class CategoryScore(BaseModel):
    """Aggregated evaluation score for a single evaluation category."""
    category: EvaluationCategory
    total_cases: int
    passed_cases: int
    pass_rate: float
    avg_duration_ms: float
    intent_accuracy: float
    tool_recall: float


class BenchmarkReport(BaseModel):
    """Complete quantitative scorecard across the entire golden benchmark dataset."""
    timestamp: datetime = Field(default_factory=utc_now)
    total_cases: int
    passed_cases: int
    failed_cases: int
    overall_pass_rate: float
    intent_accuracy: float
    tool_precision: float
    tool_recall: float
    groundedness_rate: float
    insufficiency_accuracy: float
    adversarial_pass_rate: float
    p50_latency_ms: float
    p95_latency_ms: float
    category_scores: dict[str, CategoryScore] = Field(default_factory=dict)
    case_results: list[CaseEvaluationResult] = Field(default_factory=list)
