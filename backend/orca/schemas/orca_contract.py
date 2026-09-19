"""ORCA Agent Contract v2.

Single source of truth for data crossing ORCA runtime boundaries.
Pydantic v2 models; deterministic/safety invariants are encoded here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _require_aware(v: datetime) -> datetime:
    if v.tzinfo is None or v.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return v.astimezone(timezone.utc)


class ContractBase(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, use_enum_values=False)


class Geometry(ContractBase):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


class TimeWindow(ContractBase):
    start: datetime
    end: datetime

    @field_validator("start", "end")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        return _require_aware(v)

    @model_validator(mode="after")
    def order(self) -> "TimeWindow":
        if self.end < self.start:
            raise ValueError("time_window.end must be >= time_window.start")
        return self


class DataQuality(str, Enum):
    GOOD = "good"
    DEGRADED = "degraded"
    UNRELIABLE = "unreliable"


class AgentStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    NO_DATA = "no_data"
    FAILED = "failed"
    SKIPPED = "skipped"


class ToolStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class AccessMethod(str, Enum):
    API = "api"
    SCRAPE = "scrape"
    FILE_DOWNLOAD = "file_download"
    SEARCH = "search"
    WEBGIS = "webgis"
    ERDDAP = "erddap"
    INTERNAL = "internal"


class SourceMetadata(ContractBase):
    source_id: str
    organization: str
    dataset: str
    domain: list[str] = Field(default_factory=list)
    coverage: str = "global"
    latency: str | None = None
    resolution: str | None = None
    authority: Literal["official", "scientific", "commercial", "community", "internal"] = "official"
    access: AccessMethod = AccessMethod.API
    freshness_policy_hours: float = Field(default=24.0, gt=0)
    fallbacks: list[str] = Field(default_factory=list)


class SourceScore(ContractBase):
    source_id: str
    authority: float = Field(..., ge=0, le=1)
    freshness: float = Field(..., ge=0, le=1)
    spatial_relevance: float = Field(..., ge=0, le=1)
    temporal_relevance: float = Field(..., ge=0, le=1)
    completeness: float = Field(..., ge=0, le=1)

    @computed_field
    @property
    def usable_for_decision(self) -> bool:
        return min(
            self.authority,
            self.freshness,
            self.spatial_relevance,
            self.temporal_relevance,
            self.completeness,
        ) >= 0.5


class Evidence(ContractBase):
    id: str = Field(default_factory=lambda: f"ev_{uuid4().hex[:10]}")
    source: SourceMetadata
    variable: str
    value: float | int | str | dict[str, Any] | list[Any]
    unit: str | None = None
    geometry: Geometry | None = None
    observed_at: datetime | None = None
    reference_time: datetime | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    retrieved_at: datetime = Field(default_factory=utc_now)
    method: str = "point_query"
    quality: DataQuality = DataQuality.GOOD
    derived: bool = False
    estimated: bool = False
    derivation_details: str | None = None

    @field_validator("observed_at", "reference_time", "valid_from", "valid_until", "retrieved_at")
    @classmethod
    def aware(cls, v: datetime | None) -> datetime | None:
        return None if v is None else _require_aware(v)

    @model_validator(mode="after")
    def valid_interval(self) -> "Evidence":
        if self.valid_from and self.valid_until and self.valid_until < self.valid_from:
            raise ValueError("valid_until must be >= valid_from")
        return self

    def is_fresh(self, now: datetime | None = None) -> bool:
        now = now or utc_now()
        age_hours = (now - self.retrieved_at).total_seconds() / 3600
        return age_hours <= self.source.freshness_policy_hours

    def is_valid_at(self, t: datetime) -> bool:
        t = _require_aware(t)
        if self.valid_from and t < self.valid_from:
            return False
        if self.valid_until and t > self.valid_until:
            return False
        return True


class ToolName(str, Enum):
    GET_SST = "get_sst"
    GET_CHLOROPHYLL = "get_chlorophyll"
    GET_PFZ = "get_pfz"
    GET_WAVE_FORECAST = "get_wave_forecast"
    GET_WIND = "get_wind"
    GET_TIDE = "get_tide"
    GET_CYCLONE_ALERTS = "get_cyclone_alerts"
    GET_LIGHTNING = "get_lightning"
    GET_EEZ = "get_eez"
    GET_PROTECTED_AREAS = "get_protected_areas"
    CALCULATE_DISTANCE = "calculate_distance"
    CALCULATE_BEARING = "calculate_bearing"
    CALCULATE_ROUTE = "calculate_route"
    QUERY_POSTGIS = "query_postgis"
    RETRIEVE_RASTER = "retrieve_raster"
    SEARCH_MARINE_SOURCES = "search_marine_sources"
    FETCH_ADVISORY = "fetch_advisory"


class ToolCall(ContractBase):
    call_id: str = Field(default_factory=lambda: f"tc_{uuid4().hex[:10]}")
    tool: ToolName
    input: dict[str, Any]
    started_at: datetime = Field(default_factory=utc_now)
    finished_at: datetime | None = None
    duration_ms: float | None = Field(default=None, ge=0)
    status: ToolStatus = ToolStatus.PLANNED
    output: dict[str, Any] | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    error: str | None = None

    @field_validator("started_at", "finished_at")
    @classmethod
    def aware(cls, v: datetime | None) -> datetime | None:
        return None if v is None else _require_aware(v)

    @model_validator(mode="after")
    def timing(self) -> "ToolCall":
        if self.finished_at and self.finished_at < self.started_at:
            raise ValueError("finished_at must be >= started_at")
        return self


class ToolDefinition(ContractBase):
    name: ToolName
    description: str
    domains: list[str] = Field(default_factory=list)
    deterministic: bool = True
    requires_location: bool = False
    requires_time_window: bool = False
    produces_evidence: bool = True
    timeout_seconds: float = Field(default=10.0, gt=0)
    retry_count: int = Field(default=0, ge=0, le=5)


class PlanStep(ContractBase):
    step_id: str = Field(default_factory=lambda: f"step_{uuid4().hex[:8]}")
    agent: str
    goal: str
    depends_on: list[str] = Field(default_factory=list)
    parallel_group: str | None = None
    required: bool = True


class Plan(ContractBase):
    plan_id: str = Field(default_factory=lambda: f"plan_{uuid4().hex[:8]}")
    steps: list[PlanStep]
    created_at: datetime = Field(default_factory=utc_now)
    rationale: str | None = None

    @field_validator("created_at")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        return _require_aware(v)

    @model_validator(mode="after")
    def validate_dag(self) -> "Plan":
        ids = [s.step_id for s in self.steps]
        if len(ids) != len(set(ids)):
            raise ValueError("plan step_id values must be unique")
        all_ids = set(ids)
        for step in self.steps:
            if step.step_id in step.depends_on:
                raise ValueError(f"step {step.step_id} cannot depend on itself")
            missing = set(step.depends_on) - all_ids
            if missing:
                raise ValueError(f"step {step.step_id} has missing dependencies: {sorted(missing)}")

        graph = {s.step_id: set(s.depends_on) for s in self.steps}
        visiting: set[str] = set()
        visited: set[str] = set()

        def dfs(node: str) -> None:
            if node in visiting:
                raise ValueError("plan contains a dependency cycle")
            if node in visited:
                return
            visiting.add(node)
            for dep in graph[node]:
                dfs(dep)
            visiting.remove(node)
            visited.add(node)

        for node in graph:
            dfs(node)
        return self


class AgentResult(ContractBase):
    agent: str
    status: AgentStatus
    result: dict[str, Any] = Field(default_factory=dict)
    evidence: list[Evidence] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0, le=1)
    limitations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    duration_ms: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def grounding(self) -> "AgentResult":
        factual_status = self.status in {AgentStatus.SUCCESS, AgentStatus.PARTIAL}
        if factual_status and self.result and not self.evidence:
            raise ValueError("factual AgentResult requires at least one Evidence object")
        if self.confidence > 0 and not self.evidence:
            raise ValueError("confidence > 0 requires at least one Evidence object")
        return self


class ConflictRecord(ContractBase):
    variable: str
    values: list[Evidence]
    spread_summary: str
    resolution: Literal["report_spread", "prefer_observation", "prefer_freshest"] = "report_spread"


class FusionResult(ContractBase):
    evidence: list[Evidence]
    conflicts: list[ConflictRecord] = Field(default_factory=list)
    source_scores: list[SourceScore] = Field(default_factory=list)


class VerificationCheck(str, Enum):
    EVIDENCE_PRESENT = "evidence_present"
    FRESHNESS = "freshness"
    SPATIAL_RELEVANCE = "spatial_relevance"
    TEMPORAL_RELEVANCE = "temporal_relevance"
    SCIENTIFIC_CONSISTENCY = "scientific_consistency"
    CITATION_VALID = "citation_valid"


class VerificationSeverity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class VerificationResult(ContractBase):
    passed: bool
    severity: VerificationSeverity
    checks: dict[VerificationCheck, bool]
    missing: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def blocking_implies_failed(self) -> "VerificationResult":
        if self.severity == VerificationSeverity.BLOCKING and self.passed:
            raise ValueError("blocking verification cannot be marked passed")
        return self


class SafetyStatus(str, Enum):
    SAFE = "SAFE"
    CAUTION = "CAUTION"
    HIGH_RISK = "HIGH_RISK"
    UNKNOWN = "UNKNOWN"


class SafetyDecision(ContractBase):
    status: SafetyStatus
    reasons: list[str] = Field(default_factory=list)
    evaluated_at: datetime = Field(default_factory=utc_now)

    @field_validator("evaluated_at")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        return _require_aware(v)

    @computed_field
    @property
    def route_recommendation_allowed(self) -> bool:
        return self.status in {SafetyStatus.SAFE, SafetyStatus.CAUTION}

    @computed_field
    @property
    def normal_operational_advice_allowed(self) -> bool:
        return self.status in {SafetyStatus.SAFE, SafetyStatus.CAUTION}


class Intent(str, Enum):
    PFZ_LOOKUP = "pfz_lookup"
    MARINE_SAFETY = "marine_safety"
    ROUTE_PLANNING = "route_planning"
    RESEARCH = "research"
    GENERAL_CONDITIONS = "general_conditions"
    ALERTS = "alerts"
    GEOFENCE = "geofence"
    UNKNOWN = "unknown"


class UserContext(ContractBase):
    user_id: str | None = None
    device: Literal["web", "android"] | None = None
    preferred_language: str | None = None
    timezone: str | None = None
    vessel_type: str | None = None


class ResponseType(str, Enum):
    CONVERSATIONAL = "conversational"
    FACTUAL = "factual"
    ADVISORY = "advisory"
    ERROR = "error"


class MapOverlay(ContractBase):
    kind: Literal["geojson", "raster_tile"] = "geojson"
    layer_id: str
    data: dict[str, Any]
    style_hint: str | None = None


class ChartSpec(ContractBase):
    kind: Literal["line", "bar", "scatter"]
    title: str
    series: list[dict[str, Any]]


class TraceStep(ContractBase):
    node: str
    duration_ms: float = Field(..., ge=0)
    status: str = "success"


class FinalResponse(ContractBase):
    session_id: str
    response_type: ResponseType
    answer_text: str
    language: str = "en"
    safety: SafetyDecision | None = None
    evidence_summary: list[Evidence] = Field(default_factory=list)
    conflicts: list[ConflictRecord] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0, le=1)
    map_overlays: list[MapOverlay] = Field(default_factory=list)
    charts: list[ChartSpec] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    trace: list[TraceStep] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=utc_now)

    @field_validator("generated_at")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        return _require_aware(v)

    @model_validator(mode="after")
    def grounding(self) -> "FinalResponse":
        grounded_type = self.response_type in {ResponseType.FACTUAL, ResponseType.ADVISORY}
        if grounded_type and not self.evidence_summary:
            raise ValueError("factual/advisory FinalResponse requires evidence")
        if self.confidence > 0 and not self.evidence_summary:
            raise ValueError("confidence > 0 requires evidence")
        if self.response_type == ResponseType.ADVISORY and self.safety is None:
            raise ValueError("advisory FinalResponse requires a SafetyDecision")
        return self


class OrcaState(ContractBase):
    session_id: str = Field(default_factory=lambda: f"sess_{uuid4().hex[:10]}")
    query: str
    language: str = "en"
    location: Geometry | None = None
    time_window: TimeWindow | None = None
    user_context: UserContext = Field(default_factory=UserContext)
    intent: Intent = Intent.UNKNOWN
    plan: Plan | None = None
    agent_results: list[AgentResult] = Field(default_factory=list)
    fusion: FusionResult | None = None
    verification: VerificationResult | None = None
    safety: SafetyDecision | None = None
    replan_count: int = Field(default=0, ge=0)
    max_replans: int = Field(default=1, ge=0)
    final_answer: FinalResponse | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("created_at", "updated_at")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        return _require_aware(v)

    @model_validator(mode="after")
    def replan_bound(self) -> "OrcaState":
        if self.replan_count > self.max_replans:
            raise ValueError("replan_count cannot exceed max_replans")
        return self

    def can_replan(self) -> bool:
        return self.replan_count < self.max_replans

    def register_replan(self) -> None:
        if not self.can_replan():
            raise RuntimeError("ORCA replan limit reached")
        object.__setattr__(self, "replan_count", self.replan_count + 1)
        object.__setattr__(self, "updated_at", utc_now())
