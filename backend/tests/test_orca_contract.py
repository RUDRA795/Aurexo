import pytest
from pydantic import ValidationError

from orca.schemas.orca_contract import (
    AgentResult,
    AgentStatus,
    Evidence,
    Geometry,
    Intent,
    OrcaState,
    Plan,
    PlanStep,
    ResponseType,
    SafetyDecision,
    SafetyStatus,
    SourceMetadata,
    TimeWindow,
    ToolCall,
    ToolName,
    VerificationCheck,
    VerificationResult,
    VerificationSeverity,
    utc_now,
)


def test_safety_route_permission_is_derived_and_not_constructor_settable():
    with pytest.raises(ValidationError):
        SafetyDecision(status=SafetyStatus.HIGH_RISK, route_recommendation_allowed=True)


def test_safety_route_permission_cannot_be_mutated():
    decision = SafetyDecision(status=SafetyStatus.HIGH_RISK)
    assert decision.route_recommendation_allowed is False
    with pytest.raises(AttributeError):
        decision.route_recommendation_allowed = True


def test_unknown_safety_is_conservative():
    decision = SafetyDecision(status=SafetyStatus.UNKNOWN)
    assert decision.route_recommendation_allowed is False
    assert decision.normal_operational_advice_allowed is False


def _evidence():
    return Evidence(
        source=SourceMetadata(source_id="test", organization="Test", dataset="fixture"),
        variable="wave_height",
        value=2.1,
        unit="m",
        geometry=Geometry(lat=15.5, lon=73.8),
        observed_at=utc_now(),
    )


def test_successful_factual_result_without_evidence_is_rejected():
    with pytest.raises(ValidationError):
        AgentResult(
            agent="weather_agent",
            status=AgentStatus.SUCCESS,
            result={"wave_height_m": 2.1},
            confidence=0,
        )


def test_confidence_without_evidence_is_rejected():
    with pytest.raises(ValidationError):
        AgentResult(
            agent="weather_agent",
            status=AgentStatus.FAILED,
            confidence=0.5,
        )


def test_partial_factual_result_without_evidence_is_rejected():
    with pytest.raises(ValidationError):
        AgentResult(
            agent="weather_agent",
            status=AgentStatus.PARTIAL,
            result={"wave_height_m": 2.1},
        )


def test_failure_can_have_no_evidence_and_zero_confidence():
    result = AgentResult(
        agent="weather_agent",
        status=AgentStatus.FAILED,
        limitations=["timeout"],
    )
    assert result.confidence == 0


def test_time_window_requires_aware_datetimes():
    from datetime import datetime
    with pytest.raises(ValidationError):
        TimeWindow(start=datetime(2026, 9, 18), end=datetime(2026, 9, 19))


def test_time_window_is_normalized_to_utc_and_ordered():
    from datetime import datetime, timezone, timedelta
    start = datetime(2026, 9, 18, 10, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    end = datetime(2026, 9, 18, 11, tzinfo=timezone(timedelta(hours=5, minutes=30)))
    window = TimeWindow(start=start, end=end)
    assert window.start.tzinfo == timezone.utc
    assert window.end > window.start


def test_plan_rejects_duplicate_ids():
    with pytest.raises(ValidationError):
        Plan(steps=[
            PlanStep(step_id="x", agent="a", goal="one"),
            PlanStep(step_id="x", agent="b", goal="two"),
        ])


def test_plan_rejects_missing_dependency():
    with pytest.raises(ValidationError):
        Plan(steps=[PlanStep(step_id="x", agent="a", goal="x", depends_on=["missing"])])


def test_plan_rejects_cycle():
    with pytest.raises(ValidationError):
        Plan(steps=[
            PlanStep(step_id="a", agent="a", goal="a", depends_on=["b"]),
            PlanStep(step_id="b", agent="b", goal="b", depends_on=["a"]),
        ])


def test_blocking_verification_cannot_pass():
    with pytest.raises(ValidationError):
        VerificationResult(
            passed=True,
            severity=VerificationSeverity.BLOCKING,
            checks={VerificationCheck.EVIDENCE_PRESENT: True},
        )


def test_replan_is_hard_capped():
    state = OrcaState(query="test", intent=Intent.PFZ_LOOKUP)
    assert state.can_replan()
    state.register_replan()
    assert not state.can_replan()
    with pytest.raises(RuntimeError):
        state.register_replan()


def test_serialization_is_json_safe():
    evidence = _evidence()
    result = AgentResult(
        agent="test",
        status=AgentStatus.SUCCESS,
        result={"value": 2.1},
        evidence=[evidence],
        confidence=0.5,
    )
    payload = result.model_dump(mode="json")
    assert payload["agent"] == "test"
    assert payload["evidence"][0]["source"]["source_id"] == "test"
