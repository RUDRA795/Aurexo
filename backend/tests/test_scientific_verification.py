"""Comprehensive test suite for Milestone P3.1: Scientific Verification & Source Arbitration.

Verifies the 6-dimension scientific pipeline, unit normalization, temporal semantics,
spatial proximity, physical sanity (Level A), regional QC (Level B), cross-source arbitration,
conflict records, and agent runtime integration.
"""
from datetime import datetime, timedelta, timezone
import pytest

from orca.agents.runtime import OrcaAgentRuntime
from orca.safety.source_policy import SourcePolicyRegistry, SourceTrustTier
from orca.schemas.agent_runtime import IntentEnum
from orca.schemas.orca_contract import (
    AccessMethod,
    DataQuality,
    Evidence,
    EvidenceType,
    Geometry,
    SourceMetadata,
    VerificationSeverity,
    utc_now,
)
from orca.verification.scientific import (
    ScientificVerifier,
    SourceArbitrator,
    VerificationStatus,
    haversine_distance_km,
)


def make_test_source(
    source_id: str = "incois_osf_sst",
    org: str = "INCOIS",
    dataset: str = "OSF SST",
    authority: str = "official",
    freshness_hours: float = 24.0,
) -> SourceMetadata:
    """Helper to create valid SourceMetadata for testing."""
    return SourceMetadata(
        source_id=source_id,
        organization=org,
        dataset=dataset,
        domain=["ocean_state"],
        authority=authority,
        access=AccessMethod.API,
        freshness_policy_hours=freshness_hours,
    )


# ---------------------------------------------------------------------------
# 1. PHYSICAL SANITY & REGIONAL QC TESTS (Level A vs Level B)
# ---------------------------------------------------------------------------

def test_physical_plausibility_sst_valid():
    """Verify normal valid SST passes verification without warnings."""
    verifier = ScientificVerifier()
    ev = Evidence(
        source=make_test_source(),
        variable="sea_surface_temperature",
        value=28.5,
        unit="°C",
        evidence_type=EvidenceType.OBSERVATION,
        geometry=Geometry(lat=18.92, lon=72.83),
        observed_at=utc_now() - timedelta(hours=1),
    )
    rec = verifier.verify_evidence(ev)
    assert rec.status == VerificationStatus.VALID
    assert rec.severity == VerificationSeverity.INFO
    assert rec.checks["physical_sanity_valid"] is True
    assert rec.checks["regional_qc_valid"] is True
    assert rec.normalized_value == 28.5


def test_physical_plausibility_sst_impossible_rejected():
    """Verify physically impossible SST (e.g. 55°C or -10°C) is marked INVALID / BLOCKING."""
    verifier = ScientificVerifier()
    ev_hot = Evidence(
        source=make_test_source(),
        variable="sea_surface_temperature",
        value=55.0,
        unit="°C",
        evidence_type=EvidenceType.OBSERVATION,
        geometry=Geometry(lat=18.92, lon=72.83),
    )
    rec_hot = verifier.verify_evidence(ev_hot)
    assert rec_hot.status == VerificationStatus.INVALID
    assert rec_hot.severity == VerificationSeverity.BLOCKING
    assert rec_hot.checks["physical_sanity_valid"] is False

    ev_freezing = Evidence(
        source=make_test_source(),
        variable="sea_surface_temperature",
        value=-10.0,
        unit="°C",
        evidence_type=EvidenceType.OBSERVATION,
        geometry=Geometry(lat=18.92, lon=72.83),
    )
    rec_freezing = verifier.verify_evidence(ev_freezing)
    assert rec_freezing.status == VerificationStatus.INVALID
    assert rec_freezing.severity == VerificationSeverity.BLOCKING


def test_regional_qc_anomaly_does_not_invalidate_sst():
    """Verify regional range violation in Indian Ocean (e.g. 18°C or 36°C) produces ANOMALOUS/WARNING, NOT INVALID."""
    verifier = ScientificVerifier()
    # 18°C is physically possible ocean temperature, but anomalous for tropical Indian Ocean (20-35°C)
    ev = Evidence(
        source=make_test_source(),
        variable="sea_surface_temperature",
        value=18.0,
        unit="°C",
        evidence_type=EvidenceType.OBSERVATION,
        geometry=Geometry(lat=18.92, lon=72.83),
        observed_at=utc_now() - timedelta(hours=1),
    )
    rec = verifier.verify_evidence(ev)
    assert rec.status == VerificationStatus.ANOMALOUS
    assert rec.severity == VerificationSeverity.WARNING
    assert rec.checks["physical_sanity_valid"] is True
    assert rec.checks["regional_qc_valid"] is False
    # Crucial: verified_evidence must NOT be None, allowing it to enter synthesis with appropriate notes!
    assert rec.verified_evidence is not None
    assert rec.verified_evidence.value == 18.0


def test_physical_plausibility_chlorophyll():
    """Verify chlorophyll sanity (non-negative) and rejection of negative values."""
    verifier = ScientificVerifier()
    # Valid
    ev_val = Evidence(
        source=make_test_source(source_id="incois_viirs_chl", dataset="VIIRS Chl"),
        variable="chlorophyll_a",
        value=0.25,
        unit="mg/m³",
        evidence_type=EvidenceType.OBSERVATION,
        geometry=Geometry(lat=18.92, lon=72.83),
    )
    rec_val = verifier.verify_evidence(ev_val)
    assert rec_val.status == VerificationStatus.VALID

    # Negative chlorophyll (physically impossible)
    ev_neg = Evidence(
        source=make_test_source(source_id="incois_viirs_chl", dataset="VIIRS Chl"),
        variable="chlorophyll_a",
        value=-0.5,
        unit="mg/m³",
        evidence_type=EvidenceType.OBSERVATION,
        geometry=Geometry(lat=18.92, lon=72.83),
    )
    rec_neg = verifier.verify_evidence(ev_neg)
    assert rec_neg.status == VerificationStatus.INVALID
    assert rec_neg.severity == VerificationSeverity.BLOCKING
    assert rec_neg.checks["physical_sanity_valid"] is False


def test_physical_plausibility_wave_height_and_period():
    """Verify wave height and period bounds and regional cyclone wave anomaly."""
    verifier = ScientificVerifier()
    # Valid wave height & period
    ev_wave = Evidence(
        source=make_test_source(source_id="incois_osf_ocean_state", dataset="OSF Wave"),
        variable="significant_wave_height",
        value=2.5,
        unit="m",
        evidence_type=EvidenceType.FORECAST,
        geometry=Geometry(lat=18.92, lon=72.83),
    )
    rec_wave = verifier.verify_evidence(ev_wave)
    assert rec_wave.status == VerificationStatus.VALID

    # Negative wave height -> INVALID
    ev_neg = Evidence(
        source=make_test_source(source_id="incois_osf_ocean_state", dataset="OSF Wave"),
        variable="significant_wave_height",
        value=-1.0,
        unit="m",
        evidence_type=EvidenceType.FORECAST,
        geometry=Geometry(lat=18.92, lon=72.83),
    )
    rec_neg = verifier.verify_evidence(ev_neg)
    assert rec_neg.status == VerificationStatus.INVALID
    assert rec_neg.severity == VerificationSeverity.BLOCKING

    # Extreme monsoonal / cyclone wave height (15.5m) -> ANOMALOUS with WARNING, not INVALID
    ev_cyclone = Evidence(
        source=make_test_source(source_id="incois_osf_ocean_state", dataset="OSF Wave"),
        variable="significant_wave_height",
        value=15.5,
        unit="m",
        evidence_type=EvidenceType.FORECAST,
        geometry=Geometry(lat=18.92, lon=72.83),
        forecast_valid_at=utc_now() + timedelta(hours=6),
    )
    rec_cyclone = verifier.verify_evidence(ev_cyclone)
    assert rec_cyclone.status == VerificationStatus.ANOMALOUS
    assert rec_cyclone.severity == VerificationSeverity.WARNING
    assert rec_cyclone.verified_evidence is not None


def test_surface_current_validation():
    """Verify surface current velocity bounds and units."""
    verifier = ScientificVerifier()
    ev = Evidence(
        source=make_test_source(source_id="incois_osf_ocean_state"),
        variable="surface_current",
        value=0.45,
        unit="m/s",
        evidence_type=EvidenceType.FORECAST,
        geometry=Geometry(lat=18.92, lon=72.83),
    )
    rec = verifier.verify_evidence(ev)
    assert rec.status == VerificationStatus.VALID
    assert rec.normalized_value == 0.45
    assert rec.normalized_unit == "m/s"


# ---------------------------------------------------------------------------
# 2. UNIT NORMALIZATION TESTS
# ---------------------------------------------------------------------------

def test_unit_normalization_kelvin_to_celsius():
    """Verify temperature in Kelvin (e.g. 301.65 K) is converted to 28.5 °C."""
    verifier = ScientificVerifier()
    ev = Evidence(
        source=make_test_source(),
        variable="sea_surface_temperature",
        value=301.65,
        unit="K",
        evidence_type=EvidenceType.OBSERVATION,
        geometry=Geometry(lat=18.92, lon=72.83),
    )
    rec = verifier.verify_evidence(ev)
    assert rec.status == VerificationStatus.VALID
    assert rec.raw_value == 301.65
    assert rec.raw_unit == "K"
    assert rec.normalized_value == 28.5
    assert rec.normalized_unit == "°C"
    assert rec.verified_evidence.value == 28.5
    assert rec.verified_evidence.unit == "°C"


def test_unit_normalization_fahrenheit_to_celsius():
    """Verify temperature in Fahrenheit (86.0 °F) is converted to 30.0 °C."""
    verifier = ScientificVerifier()
    ev = Evidence(
        source=make_test_source(),
        variable="sea_surface_temperature",
        value=86.0,
        unit="°F",
        evidence_type=EvidenceType.OBSERVATION,
        geometry=Geometry(lat=18.92, lon=72.83),
    )
    rec = verifier.verify_evidence(ev)
    assert rec.status == VerificationStatus.VALID
    assert rec.normalized_value == 30.0
    assert rec.normalized_unit == "°C"


def test_unit_normalization_wind_mps_to_knots():
    """Verify wind speed in m/s (10.0 m/s) is converted to knots (19.4 knots)."""
    verifier = ScientificVerifier()
    ev = Evidence(
        source=make_test_source(source_id="incois_osf_ocean_state"),
        variable="wind_speed",
        value=10.0,
        unit="m/s",
        evidence_type=EvidenceType.FORECAST,
        geometry=Geometry(lat=18.92, lon=72.83),
    )
    rec = verifier.verify_evidence(ev)
    assert rec.status == VerificationStatus.VALID
    assert rec.normalized_value == 19.4
    assert rec.normalized_unit == "knots"


def test_unit_normalization_wind_dict_format():
    """Verify wind speed dictionary format preserves direction and normalizes speed."""
    verifier = ScientificVerifier()
    ev = Evidence(
        source=make_test_source(source_id="incois_osf_ocean_state"),
        variable="wind",
        value={"wind_speed_knots": 14.0, "wind_direction_deg": 260.0},
        unit="knots",
        evidence_type=EvidenceType.FORECAST,
        geometry=Geometry(lat=18.92, lon=72.83),
    )
    rec = verifier.verify_evidence(ev)
    assert rec.status == VerificationStatus.VALID
    assert rec.normalized_value["wind_speed_knots"] == 14.0
    assert rec.normalized_value["wind_direction_deg"] == 260.0


def test_invalid_unit_rejected():
    """Verify an incompatible or nonsensical unit (e.g. 'kg' for SST) is rejected."""
    verifier = ScientificVerifier()
    ev = Evidence(
        source=make_test_source(),
        variable="sea_surface_temperature",
        value=29.0,
        unit="kg",
        evidence_type=EvidenceType.OBSERVATION,
        geometry=Geometry(lat=18.92, lon=72.83),
    )
    rec = verifier.verify_evidence(ev)
    assert rec.status == VerificationStatus.INVALID
    assert rec.severity == VerificationSeverity.BLOCKING
    assert rec.checks["unit_valid"] is False


# ---------------------------------------------------------------------------
# 3. TEMPORAL VALIDATION TESTS (Observation vs Forecast vs Warning)
# ---------------------------------------------------------------------------

def test_fresh_vs_stale_observation():
    """Verify fresh observation is accepted and stale observation past policy hours emits warning."""
    verifier = ScientificVerifier()
    now = utc_now()
    src = make_test_source(freshness_hours=12.0)

    # Fresh (2 hours old)
    ev_fresh = Evidence(
        source=src,
        variable="sea_surface_temperature",
        value=29.0,
        unit="°C",
        evidence_type=EvidenceType.OBSERVATION,
        geometry=Geometry(lat=18.92, lon=72.83),
        observed_at=now - timedelta(hours=2),
    )
    rec_fresh = verifier.verify_evidence(ev_fresh, reference_time=now)
    assert rec_fresh.status == VerificationStatus.VALID
    assert rec_fresh.freshness_status == "FRESH"

    # Stale (18 hours old for 12h policy)
    ev_stale = Evidence(
        source=src,
        variable="sea_surface_temperature",
        value=29.0,
        unit="°C",
        evidence_type=EvidenceType.OBSERVATION,
        geometry=Geometry(lat=18.92, lon=72.83),
        observed_at=now - timedelta(hours=18),
    )
    rec_stale = verifier.verify_evidence(ev_stale, reference_time=now)
    assert rec_stale.status == VerificationStatus.VALID_WITH_WARNING
    assert rec_stale.severity == VerificationSeverity.WARNING
    assert rec_stale.freshness_status == "STALE"


def test_future_observation_rejected():
    """Verify an observation with an impossible future timestamp is marked INVALID / BLOCKING."""
    verifier = ScientificVerifier()
    now = utc_now()
    ev_future = Evidence(
        source=make_test_source(),
        variable="sea_surface_temperature",
        value=29.0,
        unit="°C",
        evidence_type=EvidenceType.OBSERVATION,
        geometry=Geometry(lat=18.92, lon=72.83),
        observed_at=now + timedelta(hours=5),  # 5 hours in future
    )
    rec = verifier.verify_evidence(ev_future, reference_time=now)
    assert rec.status == VerificationStatus.INVALID
    assert rec.severity == VerificationSeverity.BLOCKING
    assert rec.checks["temporal_valid"] is False


def test_forecast_validity_window():
    """Verify active forecast is valid, but expired forecast window triggers warning."""
    verifier = ScientificVerifier()
    now = utc_now()

    # Active forecast: issued 2 hours ago, valid for 10 hours from now
    ev_active = Evidence(
        source=make_test_source(source_id="incois_osf_ocean_state"),
        variable="significant_wave_height",
        value=1.5,
        unit="m",
        evidence_type=EvidenceType.FORECAST,
        geometry=Geometry(lat=18.92, lon=72.83),
        issued_at=now - timedelta(hours=2),
        forecast_valid_at=now + timedelta(hours=10),
        valid_until=now + timedelta(hours=10),
    )
    rec_active = verifier.verify_evidence(ev_active, reference_time=now)
    assert rec_active.status == VerificationStatus.VALID
    assert rec_active.freshness_status == "ACTIVE_FORECAST"

    # Expired forecast: target validity was 8 hours ago
    ev_expired = Evidence(
        source=make_test_source(source_id="incois_osf_ocean_state"),
        variable="significant_wave_height",
        value=1.5,
        unit="m",
        evidence_type=EvidenceType.FORECAST,
        geometry=Geometry(lat=18.92, lon=72.83),
        issued_at=now - timedelta(hours=24),
        forecast_valid_at=now - timedelta(hours=8),
        valid_until=now - timedelta(hours=8),
    )
    rec_expired = verifier.verify_evidence(ev_expired, reference_time=now)
    assert rec_expired.severity == VerificationSeverity.WARNING
    assert "expired" in rec_expired.freshness_status.lower()


def test_warning_validity_window():
    """Verify active IMD marine warning vs expired warning bulletin."""
    verifier = ScientificVerifier()
    now = utc_now()

    # Active warning
    ev_warn = Evidence(
        source=make_test_source(source_id="imd_marine_warning"),
        variable="fishermen_warning",
        value={"warning_level": "FISHERMEN_WARNING", "text": "Squally weather"},
        evidence_type=EvidenceType.WARNING,
        geometry=Geometry(lat=18.92, lon=72.83),
        issued_at=now - timedelta(hours=1),
        valid_from=now - timedelta(hours=1),
        valid_until=now + timedelta(hours=23),
    )
    rec_warn = verifier.verify_evidence(ev_warn, reference_time=now)
    assert rec_warn.status == VerificationStatus.VALID

    # Expired warning
    ev_exp_warn = Evidence(
        source=make_test_source(source_id="imd_marine_warning"),
        variable="fishermen_warning",
        value={"warning_level": "NO_WARNING"},
        evidence_type=EvidenceType.WARNING,
        geometry=Geometry(lat=18.92, lon=72.83),
        issued_at=now - timedelta(hours=48),
        valid_from=now - timedelta(hours=48),
        valid_until=now - timedelta(hours=12),
    )
    rec_exp = verifier.verify_evidence(ev_exp_warn, reference_time=now)
    assert rec_exp.severity == VerificationSeverity.WARNING


# ---------------------------------------------------------------------------
# 4. SPATIAL VALIDATION TESTS
# ---------------------------------------------------------------------------

def test_spatial_proximity_within_and_exceeding():
    """Verify spatial validation for in-domain, extended proximity, and out-of-domain locations."""
    verifier = ScientificVerifier()
    mumbai = Geometry(lat=18.92, lon=72.83)

    # 1. In radius: ~25 km away (lat 19.10, lon 72.80)
    ev_near = Evidence(
        source=make_test_source(),
        variable="sea_surface_temperature",
        value=29.0,
        unit="°C",
        geometry=Geometry(lat=19.10, lon=72.80),
    )
    rec_near = verifier.verify_evidence(ev_near, target_location=mumbai, max_radius_km=100.0)
    assert rec_near.status == VerificationStatus.VALID
    assert rec_near.spatial_status == "IN_DOMAIN"

    # 2. Extended proximity: ~180 km away (exceeds 100km radius, but <= 250km)
    ev_mid = Evidence(
        source=make_test_source(),
        variable="sea_surface_temperature",
        value=29.0,
        unit="°C",
        geometry=Geometry(lat=17.50, lon=73.00),
    )
    rec_mid = verifier.verify_evidence(ev_mid, target_location=mumbai, max_radius_km=100.0)
    assert rec_mid.status == VerificationStatus.VALID_WITH_WARNING
    assert rec_mid.severity == VerificationSeverity.WARNING
    assert rec_mid.spatial_status == "EXTENDED_PROXIMITY"

    # 3. Out of domain: Chennai on east coast (~1000 km away)
    ev_far = Evidence(
        source=make_test_source(),
        variable="sea_surface_temperature",
        value=29.0,
        unit="°C",
        geometry=Geometry(lat=13.08, lon=80.27),
    )
    rec_far = verifier.verify_evidence(ev_far, target_location=mumbai, max_radius_km=100.0)
    assert rec_far.status == VerificationStatus.INVALID
    assert rec_far.severity == VerificationSeverity.BLOCKING
    assert rec_far.spatial_status == "OUT_OF_DOMAIN"


# ---------------------------------------------------------------------------
# 5. SOURCE POLICY VALIDATION TESTS
# ---------------------------------------------------------------------------

def test_source_policy_acceptance_and_untrusted_rejection():
    """Verify authorized source is accepted, and untrusted or unauthorized variables are flagged."""
    reg = SourcePolicyRegistry()
    verifier = ScientificVerifier(source_registry=reg)

    # Authorized source & variable
    ev_auth = Evidence(
        source=make_test_source(source_id="incois_osf_sst"),
        variable="sea_surface_temperature",
        value=29.0,
        unit="°C",
        geometry=Geometry(lat=18.92, lon=72.83),
    )
    rec_auth = verifier.verify_evidence(ev_auth)
    assert rec_auth.checks["policy_valid"] is True

    # Unauthorized variable on known source (e.g. INCOIS SST providing weather alerts)
    ev_unauth_var = Evidence(
        source=make_test_source(source_id="incois_osf_sst"),
        variable="cyclone_warning_alert",
        value="Emergency",
        geometry=Geometry(lat=18.92, lon=72.83),
    )
    rec_unauth = verifier.verify_evidence(ev_unauth_var)
    assert rec_unauth.checks["policy_valid"] is False
    assert rec_unauth.source_policy_status == "UNAUTHORIZED_VARIABLE"


# ---------------------------------------------------------------------------
# 6. CROSS-SOURCE ARBITRATION TESTS (Agreement vs Conflict)
# ---------------------------------------------------------------------------

def test_cross_source_sst_agreement_without_averaging():
    """Verify that concordant sources (INCOIS 29.2°C vs Copernicus 29.6°C) record agreement

    and retain the preferred operational source WITHOUT creating a fabricated averaged value.
    """
    arbitrator = SourceArbitrator()
    loc = Geometry(lat=18.92, lon=72.83)
    now = utc_now()

    ev_incois = Evidence(
        source=make_test_source(source_id="incois_osf_sst", org="INCOIS"),
        variable="sea_surface_temperature",
        value=29.2,
        unit="°C",
        evidence_type=EvidenceType.OBSERVATION,
        geometry=loc,
        observed_at=now,
    )
    ev_copernicus = Evidence(
        source=make_test_source(source_id="copernicus_marine_sst", org="Copernicus"),
        variable="sea_surface_temperature",
        value=29.6,
        unit="°C",
        evidence_type=EvidenceType.OBSERVATION,
        geometry=loc,
        observed_at=now,
    )

    res = arbitrator.arbitrate([ev_incois, ev_copernicus])
    # Must NOT create conflict
    assert len(res.conflicts) == 0
    # Must record agreement
    assert len(res.agreements) == 1
    agr = res.agreements[0]
    assert agr["discrepancy"] == 0.4
    assert agr["preferred_source"] == "incois_osf_sst"
    assert agr["retained_value"] == 29.2
    assert res.confidence_penalty == 0.0


def test_cross_source_sst_conflict_creates_conflict_record():
    """Verify that conflicting sources (INCOIS 28.5°C vs Copernicus 32.5°C, delta 4.0°C)

    generates ConflictRecord, resolution='report_spread', retains both records, and applies penalty.
    """
    arbitrator = SourceArbitrator()
    loc = Geometry(lat=18.92, lon=72.83)
    now = utc_now()

    ev_incois = Evidence(
        source=make_test_source(source_id="incois_osf_sst", org="INCOIS"),
        variable="sea_surface_temperature",
        value=28.5,
        unit="°C",
        evidence_type=EvidenceType.OBSERVATION,
        geometry=loc,
        observed_at=now,
    )
    ev_copernicus = Evidence(
        source=make_test_source(source_id="copernicus_marine_sst", org="Copernicus"),
        variable="sea_surface_temperature",
        value=32.5,
        unit="°C",
        evidence_type=EvidenceType.OBSERVATION,
        geometry=loc,
        observed_at=now,
    )

    res = arbitrator.arbitrate([ev_incois, ev_copernicus])
    assert len(res.conflicts) == 1
    conf = res.conflicts[0]
    assert conf.variable == "sea_surface_temperature"
    assert conf.resolution == "report_spread"
    assert len(conf.values) == 2
    assert "diverged by 4.00°C" in conf.spread_summary
    # Deterministic confidence penalty applied
    assert res.confidence_penalty >= 0.15
    # Both sources preserved
    assert len(res.arbitrated_evidences) == 2


# ---------------------------------------------------------------------------
# 7. RUNTIME INTEGRATION & GROUNDED SYNTHESIS TESTS
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_runtime_integration_excludes_invalid_evidence():
    """Verify that invalid/unphysical evidence is excluded by verifier and does not enter final answer."""
    runtime = OrcaAgentRuntime()
    loc = Geometry(lat=18.92, lon=72.83)

    # Artificially inject unphysical SST into evidence pipeline
    invalid_sst = Evidence(
        source=make_test_source(),
        variable="sea_surface_temperature",
        value=65.0,  # Impossible SST
        unit="°C",
        geometry=loc,
    )

    pipeline_res = runtime.verifier.verify_pipeline([invalid_sst], target_location=loc)
    assert len(pipeline_res.valid_evidences) == 0
    assert len(pipeline_res.rejected_evidences) == 1
    assert pipeline_res.rejected_evidences[0].value == 65.0


@pytest.mark.asyncio
async def test_runtime_integration_handles_conflict_with_divergence_disclosure():
    """Verify that cross-source conflict generates a clear disclosure and penalizes confidence in synthesis."""
    runtime = OrcaAgentRuntime()
    loc = Geometry(lat=18.92, lon=72.83)
    now = utc_now()

    ev1 = Evidence(
        source=make_test_source(source_id="incois_osf_sst"),
        variable="sea_surface_temperature",
        value=28.5,
        unit="°C",
        geometry=loc,
        observed_at=now,
    )
    ev2 = Evidence(
        source=make_test_source(source_id="copernicus_marine_sst"),
        variable="sea_surface_temperature",
        value=33.0,  # 4.5°C discrepancy -> Conflict
        unit="°C",
        geometry=loc,
        observed_at=now,
    )

    # Arbitrate
    arb = runtime.arbitrator.arbitrate([ev1, ev2])
    assert len(arb.conflicts) == 1

    suff = runtime.evaluate_evidence_sufficiency(IntentEnum.OCEAN_METRICS, [ev1, ev2])
    # Apply penalty
    suff.answer_confidence = max(0.0, round(suff.answer_confidence - arb.confidence_penalty, 2))

    resp, claims = runtime.synthesize_grounded_response(
        intent=IntentEnum.OCEAN_METRICS,
        query="Check sea surface temperature near Mumbai",
        evidence_list=[ev1, ev2],
        sufficiency=suff,
        session_id="test_sess",
        conflicts=arb.conflicts,
        agreements=arb.agreements,
    )

    assert "DATA DIVERGENCE" in resp.answer_text
    assert len(resp.conflicts) == 1
    assert any("divergence" in lim.lower() for lim in resp.limitations)
    assert resp.confidence < 1.0


def test_evidence_classification_types_preserved():
    """Verify that explicit evidence types (FORECAST, WARNING, OBSERVATION) are preserved."""
    src = make_test_source()
    ev_obs = Evidence(source=src, variable="sst", value=28.0, evidence_type=EvidenceType.OBSERVATION)
    ev_fcst = Evidence(source=src, variable="wave", value=1.5, evidence_type=EvidenceType.FORECAST)
    ev_warn = Evidence(source=src, variable="warning", value="Squall", evidence_type=EvidenceType.WARNING)

    assert ev_obs.evidence_type == EvidenceType.OBSERVATION
    assert ev_fcst.evidence_type == EvidenceType.FORECAST
    assert ev_warn.evidence_type == EvidenceType.WARNING
