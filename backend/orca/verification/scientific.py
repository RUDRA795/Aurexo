"""ORCA Scientific Verification and Source Arbitration Pipeline.

Provides 6-dimension deterministic verification and cross-source conflict arbitration
in strict compliance with the ORCA Engineering Integrity Protocol:
Truth > Verification > Correctness > Scientific Validity > Safety > Reproducibility.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
import math
from typing import Any, Mapping
from pydantic import BaseModel, Field

from orca.safety.geographic_policy import is_within_operational_region
from orca.safety.source_policy import SourcePolicyRegistry, SourceTrustTier
from orca.schemas.orca_contract import (
    ConflictRecord,
    DataQuality,
    Evidence,
    EvidenceType,
    Geometry,
    SourceMetadata,
    VerificationCheck,
    VerificationResult,
    VerificationSeverity,
    utc_now,
)


class VerificationStatus(str, Enum):
    """Detailed scientific verification status for an individual evidence item."""
    VALID = "VALID"
    VALID_WITH_WARNING = "VALID_WITH_WARNING"
    ANOMALOUS = "ANOMALOUS"
    UNRELIABLE = "UNRELIABLE"
    INVALID = "INVALID"


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points in kilometers using Haversine formula."""
    r = 6371.0  # Earth's radius in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 2)


# Level A: Absolute Physical Sanity Bounds (Hard Scientific Limits)
# Values violating these bounds are physically impossible and marked INVALID / BLOCKING.
ABSOLUTE_SANITY_BOUNDS: Mapping[str, tuple[float, float]] = {
    "sea_surface_temperature": (-2.0, 45.0),    # Freezing point of seawater to extreme shallow enclosed seas
    "chlorophyll_a": (0.0, 150.0),             # Ocean color concentration in mg/m3
    "significant_wave_height": (0.0, 30.0),     # Max physically possible wave height in metres
    "wave_period": (0.5, 40.0),                # Wave period in seconds
    "swell_height": (0.0, 25.0),               # Swell height in metres
    "swell_period": (0.5, 40.0),               # Swell period in seconds
    "wind_speed": (0.0, 200.0),                # Wind speed in knots (covers Super Typhoons)
    "surface_current": (0.0, 8.0),             # Surface current velocity in m/s
}

# Level B: Regional Climatological & Product QC Bounds (Indian Ocean Maritime Domain)
# Values outside these bounds are NOT automatically invalid; they are flagged as ANOMALOUS with WARNING.
INDIAN_OCEAN_REGIONAL_QC_BOUNDS: Mapping[str, tuple[float, float]] = {
    "sea_surface_temperature": (20.0, 35.0),   # Typical tropical Indian Ocean SST range in °C
    "chlorophyll_a": (0.01, 35.0),             # Typical coastal to pelagic chlorophyll-a range in mg/m3
    "significant_wave_height": (0.0, 14.0),    # Monsoonal and cyclone wave height envelope in metres
    "wave_period": (2.0, 25.0),                # Typical wave period in seconds
    "swell_height": (0.0, 10.0),               # Typical swell height in metres
    "swell_period": (4.0, 25.0),               # Typical swell period in seconds
    "wind_speed": (0.0, 120.0),                # Typical Indian Ocean marine wind speed envelope in knots
    "surface_current": (0.0, 3.5),             # Boundary currents (Somali Current, West India Current) in m/s
}

# Variable-Specific Conflict Thresholds for Cross-Source Arbitration
VARIABLE_CONFLICT_THRESHOLDS: Mapping[str, dict[str, float]] = {
    "sea_surface_temperature": {"tolerance": 1.0, "conflict": 1.5},         # in °C
    "chlorophyll_a": {"rel_tolerance": 0.35, "rel_conflict": 0.50, "abs_min": 0.1},
    "significant_wave_height": {"tolerance": 0.5, "conflict": 1.0},        # in metres
    "wave_period": {"tolerance": 2.0, "conflict": 4.0},                     # in seconds
    "wind_speed": {"tolerance": 5.0, "conflict": 10.0},                     # in knots
    "surface_current": {"tolerance": 0.2, "conflict": 0.5},                 # in m/s
}


class EvidenceVerificationRecord(BaseModel):
    """Detailed verification audit record for a single evidence item."""
    evidence_id: str
    variable: str
    evidence_type: EvidenceType
    status: VerificationStatus
    severity: VerificationSeverity
    raw_value: Any
    raw_unit: str | None
    normalized_value: Any
    normalized_unit: str | None
    source_policy_status: str
    freshness_status: str
    spatial_status: str
    temporal_status: str
    quality: DataQuality
    checks: dict[str, bool] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    verified_evidence: Evidence | None = None


class PipelineVerificationResult(BaseModel):
    """Aggregated output of the complete 6-dimension verification pipeline."""
    records: list[EvidenceVerificationRecord] = Field(default_factory=list)
    passed: bool = True
    highest_severity: VerificationSeverity = VerificationSeverity.INFO
    valid_evidences: list[Evidence] = Field(default_factory=list)
    rejected_evidences: list[Evidence] = Field(default_factory=list)
    anomalies: list[EvidenceVerificationRecord] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class ArbitrationResult(BaseModel):
    """Cross-source comparison and arbitration output."""
    conflicts: list[ConflictRecord] = Field(default_factory=list)
    agreements: list[dict[str, Any]] = Field(default_factory=list)
    confidence_penalty: float = 0.0
    arbitrated_evidences: list[Evidence] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ScientificVerifier:
    """Deterministic six-dimension scientific verification engine for marine evidence.

    1. Schema validation
    2. Unit normalization
    3. Temporal validation
    4. Spatial validation
    5. Source policy validation
    6. Physical & product QC validation
    """

    def __init__(self, source_registry: SourcePolicyRegistry | None = None) -> None:
        self.source_registry = source_registry or SourcePolicyRegistry()

    def verify_evidence(
        self,
        evidence: Evidence,
        target_location: Geometry | None = None,
        max_radius_km: float = 200.0,
        reference_time: datetime | None = None,
    ) -> EvidenceVerificationRecord:
        """Execute full six-dimension scientific verification on a single evidence item."""
        now = reference_time or utc_now()
        notes: list[str] = []
        checks: dict[str, bool] = {
            "schema_valid": True,
            "unit_valid": True,
            "temporal_valid": True,
            "spatial_valid": True,
            "policy_valid": True,
            "physical_sanity_valid": True,
            "regional_qc_valid": True,
        }

        # Status tracking
        current_status = VerificationStatus.VALID
        current_severity = VerificationSeverity.INFO
        source_policy_status = "AUTHORIZED"
        freshness_status = "FRESH"
        spatial_status = "IN_DOMAIN"
        temporal_status = "VALID"

        raw_val = evidence.value
        raw_u = evidence.unit

        # ------------------------------------------------------------------
        # 1. SCHEMA VALIDATION
        # ------------------------------------------------------------------
        if not evidence.variable or evidence.source is None or evidence.retrieved_at is None:
            checks["schema_valid"] = False
            notes.append("Evidence schema validation failed: missing mandatory variable, source, or timestamp.")
            return EvidenceVerificationRecord(
                evidence_id=evidence.id,
                variable=evidence.variable or "unknown",
                evidence_type=evidence.evidence_type,
                status=VerificationStatus.INVALID,
                severity=VerificationSeverity.BLOCKING,
                raw_value=raw_val,
                raw_unit=raw_u,
                normalized_value=None,
                normalized_unit=None,
                source_policy_status="REJECTED_SCHEMA",
                freshness_status="UNKNOWN",
                spatial_status="UNKNOWN",
                temporal_status="INVALID",
                quality=DataQuality.UNRELIABLE,
                checks=checks,
                notes=notes,
                verified_evidence=None,
            )

        if evidence.geometry is not None:
            if not (-90.0 <= evidence.geometry.lat <= 90.0) or not (-180.0 <= evidence.geometry.lon <= 180.0):
                checks["schema_valid"] = False
                notes.append(f"Invalid coordinate geometry: ({evidence.geometry.lat}, {evidence.geometry.lon}).")
                current_status = VerificationStatus.INVALID
                current_severity = VerificationSeverity.BLOCKING

        # ------------------------------------------------------------------
        # 2. UNIT NORMALIZATION
        # ------------------------------------------------------------------
        norm_val, norm_u, unit_ok, unit_notes = self._normalize_units(evidence.variable, raw_val, raw_u)
        if not unit_ok:
            checks["unit_valid"] = False
            notes.extend(unit_notes)
            current_status = VerificationStatus.INVALID
            current_severity = VerificationSeverity.BLOCKING
        else:
            notes.extend(unit_notes)

        # ------------------------------------------------------------------
        # 3. TEMPORAL VALIDATION
        # ------------------------------------------------------------------
        temp_ok, t_status, f_status, t_notes, t_sev = self._verify_temporal(evidence, now)
        temporal_status = t_status
        freshness_status = f_status
        notes.extend(t_notes)
        if not temp_ok:
            checks["temporal_valid"] = False
            if t_sev == VerificationSeverity.BLOCKING:
                current_status = VerificationStatus.INVALID
                current_severity = VerificationSeverity.BLOCKING
            elif t_sev == VerificationSeverity.WARNING and current_severity != VerificationSeverity.BLOCKING:
                current_status = VerificationStatus.VALID_WITH_WARNING
                current_severity = VerificationSeverity.WARNING
        elif t_sev == VerificationSeverity.WARNING and current_severity != VerificationSeverity.BLOCKING:
            current_status = VerificationStatus.VALID_WITH_WARNING
            current_severity = VerificationSeverity.WARNING

        # ------------------------------------------------------------------
        # 4. SPATIAL VALIDATION
        # ------------------------------------------------------------------
        spat_ok, s_status, s_notes, s_sev = self._verify_spatial(evidence, target_location, max_radius_km)
        spatial_status = s_status
        notes.extend(s_notes)
        if not spat_ok:
            checks["spatial_valid"] = False
            if s_sev == VerificationSeverity.BLOCKING:
                current_status = VerificationStatus.INVALID
                current_severity = VerificationSeverity.BLOCKING
            elif s_sev == VerificationSeverity.WARNING and current_severity != VerificationSeverity.BLOCKING:
                current_status = VerificationStatus.VALID_WITH_WARNING
                current_severity = VerificationSeverity.WARNING
        elif s_sev == VerificationSeverity.WARNING and current_severity != VerificationSeverity.BLOCKING:
            current_status = VerificationStatus.VALID_WITH_WARNING
            current_severity = VerificationSeverity.WARNING

        # ------------------------------------------------------------------
        # 5. SOURCE POLICY VALIDATION
        # ------------------------------------------------------------------
        pol_ok, p_status, p_notes, p_sev = self._verify_source_policy(evidence)
        source_policy_status = p_status
        notes.extend(p_notes)
        if not pol_ok:
            checks["policy_valid"] = False
            if p_sev == VerificationSeverity.BLOCKING:
                current_status = VerificationStatus.UNRELIABLE
                current_severity = VerificationSeverity.BLOCKING
            elif p_sev == VerificationSeverity.WARNING and current_severity != VerificationSeverity.BLOCKING:
                current_status = VerificationStatus.VALID_WITH_WARNING
                current_severity = VerificationSeverity.WARNING
        elif p_sev == VerificationSeverity.WARNING and current_severity != VerificationSeverity.BLOCKING:
            current_status = VerificationStatus.VALID_WITH_WARNING
            current_severity = VerificationSeverity.WARNING

        # ------------------------------------------------------------------
        # 6. PHYSICAL & PRODUCT QC VALIDATION
        # ------------------------------------------------------------------
        if checks["schema_valid"] and checks["unit_valid"]:
            phys_ok, qc_ok, p_stat, p_sev, phys_notes = self._verify_physical_qc(
                evidence.variable, norm_val, norm_u, evidence.geometry
            )
            checks["physical_sanity_valid"] = phys_ok
            checks["regional_qc_valid"] = qc_ok
            notes.extend(phys_notes)

            if not phys_ok:
                current_status = VerificationStatus.INVALID
                current_severity = VerificationSeverity.BLOCKING
            elif not qc_ok:
                # Regional QC violation is ANOMALOUS with WARNING, NEVER INVALID or BLOCKING!
                if current_status == VerificationStatus.VALID:
                    current_status = VerificationStatus.ANOMALOUS
                if current_severity != VerificationSeverity.BLOCKING:
                    current_severity = VerificationSeverity.WARNING

        # Create updated/normalized Evidence instance if valid or warning/anomalous
        verified_ev: Evidence | None = None
        final_quality = evidence.quality
        if current_status in {VerificationStatus.INVALID, VerificationStatus.UNRELIABLE}:
            final_quality = DataQuality.UNRELIABLE
        elif current_status in {VerificationStatus.VALID_WITH_WARNING, VerificationStatus.ANOMALOUS}:
            if evidence.quality == DataQuality.GOOD:
                final_quality = DataQuality.GOOD  # Keep good with explicit notes, or preserve existing quality

        if current_status not in {VerificationStatus.INVALID, VerificationStatus.UNRELIABLE}:
            verified_ev = evidence.model_copy(
                update={
                    "value": norm_val if norm_val is not None else raw_val,
                    "unit": norm_u if norm_u is not None else raw_u,
                    "raw_value": raw_val,
                    "raw_unit": raw_u,
                    "normalized_value": norm_val,
                    "normalized_unit": norm_u,
                    "quality": final_quality,
                    "metadata": {
                        **evidence.metadata,
                        "verification_status": current_status.value,
                        "verification_severity": current_severity.value,
                        "freshness_status": freshness_status,
                        "spatial_status": spatial_status,
                    },
                }
            )

        return EvidenceVerificationRecord(
            evidence_id=evidence.id,
            variable=evidence.variable,
            evidence_type=evidence.evidence_type,
            status=current_status,
            severity=current_severity,
            raw_value=raw_val,
            raw_unit=raw_u,
            normalized_value=norm_val,
            normalized_unit=norm_u,
            source_policy_status=source_policy_status,
            freshness_status=freshness_status,
            spatial_status=spatial_status,
            temporal_status=temporal_status,
            quality=final_quality,
            checks=checks,
            notes=notes,
            verified_evidence=verified_ev,
        )

    def verify_pipeline(
        self,
        evidences: list[Evidence],
        target_location: Geometry | None = None,
        max_radius_km: float = 200.0,
        reference_time: datetime | None = None,
    ) -> PipelineVerificationResult:
        """Run complete six-dimension verification across a list of evidences."""
        records: list[EvidenceVerificationRecord] = []
        valid_evidences: list[Evidence] = []
        rejected_evidences: list[Evidence] = []
        anomalies: list[EvidenceVerificationRecord] = []

        highest_sev = VerificationSeverity.INFO

        for ev in evidences:
            rec = self.verify_evidence(
                ev, target_location=target_location, max_radius_km=max_radius_km, reference_time=reference_time
            )
            records.append(rec)

            if rec.severity == VerificationSeverity.BLOCKING:
                highest_sev = VerificationSeverity.BLOCKING
            elif rec.severity == VerificationSeverity.WARNING and highest_sev != VerificationSeverity.BLOCKING:
                highest_sev = VerificationSeverity.WARNING

            if rec.status in {VerificationStatus.INVALID, VerificationStatus.UNRELIABLE}:
                rejected_evidences.append(ev)
            else:
                if rec.verified_evidence:
                    valid_evidences.append(rec.verified_evidence)
                else:
                    valid_evidences.append(ev)

            if rec.status == VerificationStatus.ANOMALOUS:
                anomalies.append(rec)

        passed = highest_sev != VerificationSeverity.BLOCKING

        return PipelineVerificationResult(
            records=records,
            passed=passed,
            highest_severity=highest_sev,
            valid_evidences=valid_evidences,
            rejected_evidences=rejected_evidences,
            anomalies=anomalies,
            summary={
                "total": len(evidences),
                "valid": len(valid_evidences),
                "rejected": len(rejected_evidences),
                "anomalous": len(anomalies),
                "highest_severity": highest_sev.value,
            },
        )

    def _normalize_units(
        self, variable: str, value: Any, unit: str | None
    ) -> tuple[Any, str | None, bool, list[str]]:
        """Normalize units into canonical representations while preserving measurement integrity."""
        notes: list[str] = []
        u_str = (unit or "").strip().lower()

        # 1. Sea Surface Temperature -> canonical °C
        if variable in {"sea_surface_temperature", "sst", "temperature"}:
            if isinstance(value, (int, float)):
                # Kelvin -> Celsius
                if u_str in {"k", "kelvin"} or value > 200.0:
                    norm_c = round(float(value) - 273.15, 2)
                    notes.append(f"Normalized SST from {value} K to {norm_c} °C.")
                    return norm_c, "°C", True, notes
                # Fahrenheit -> Celsius
                if u_str in {"f", "°f", "fahrenheit", "degf"}:
                    norm_c = round((float(value) - 32.0) * 5.0 / 9.0, 2)
                    notes.append(f"Normalized SST from {value} °F to {norm_c} °C.")
                    return norm_c, "°C", True, notes
                # Already Celsius
                if u_str in {"°c", "c", "celsius", "degc", ""}:
                    return round(float(value), 2), "°C", True, notes
                # Unrecognized or physically impossible unit
                notes.append(f"Unrecognized or invalid temperature unit: '{unit}'.")
                return value, unit, False, notes

        # 2. Wind -> canonical knots (speed) and degrees (direction)
        if variable in {"wind", "wind_speed", "marine_wind"}:
            if isinstance(value, dict):
                norm_dict = dict(value)
                # Check for speed key in dict
                speed_val = norm_dict.get("wind_speed_knots") or norm_dict.get("wind_speed") or norm_dict.get("speed")
                if isinstance(speed_val, (int, float)):
                    if u_str in {"m/s", "mps", "ms"}:
                        norm_knots = round(float(speed_val) * 1.94384, 1)
                        norm_dict["wind_speed_knots"] = norm_knots
                        notes.append(f"Normalized wind speed from {speed_val} m/s to {norm_knots} knots.")
                        return norm_dict, "knots", True, notes
                    if u_str in {"km/h", "kmph", "kmh"}:
                        norm_knots = round(float(speed_val) * 0.539957, 1)
                        norm_dict["wind_speed_knots"] = norm_knots
                        notes.append(f"Normalized wind speed from {speed_val} km/h to {norm_knots} knots.")
                        return norm_dict, "knots", True, notes
                    norm_dict["wind_speed_knots"] = round(float(speed_val), 1)
                    return norm_dict, "knots", True, notes
                return value, "knots", True, notes

            if isinstance(value, (int, float)):
                if u_str in {"m/s", "mps", "ms"}:
                    norm_knots = round(float(value) * 1.94384, 1)
                    notes.append(f"Normalized wind speed from {value} m/s to {norm_knots} knots.")
                    return norm_knots, "knots", True, notes
                if u_str in {"km/h", "kmph", "kmh"}:
                    norm_knots = round(float(value) * 0.539957, 1)
                    notes.append(f"Normalized wind speed from {value} km/h to {norm_knots} knots.")
                    return norm_knots, "knots", True, notes
                if u_str in {"knots", "knot", "kt", ""}:
                    return round(float(value), 1), "knots", True, notes
                notes.append(f"Unrecognized wind unit: '{unit}'.")
                return value, unit, False, notes

        # 3. Chlorophyll-a -> canonical mg/m³
        if variable in {"chlorophyll_a", "chlorophyll", "chl"}:
            if isinstance(value, (int, float)):
                if u_str in {"mg/m³", "mg/m3", "mg/m^3", "mg m-3", "mg_m3", ""}:
                    return round(float(value), 4), "mg/m³", True, notes
                notes.append(f"Unrecognized chlorophyll unit: '{unit}'.")
                return value, unit, False, notes

        # 4. Significant Wave Height & Swell Height -> canonical metres
        if variable in {"significant_wave_height", "wave_height", "swell_height"}:
            if isinstance(value, (int, float)):
                if u_str in {"ft", "feet", "foot"}:
                    norm_m = round(float(value) * 0.3048, 2)
                    notes.append(f"Normalized wave/swell height from {value} ft to {norm_m} m.")
                    return norm_m, "m", True, notes
                if u_str in {"m", "meter", "meters", "metres", ""}:
                    return round(float(value), 2), "m", True, notes
                notes.append(f"Unrecognized wave height unit: '{unit}'.")
                return value, unit, False, notes

        # 5. Wave Period & Swell Period -> canonical seconds
        if variable in {"wave_period", "swell_period"}:
            if isinstance(value, (int, float)):
                if u_str in {"s", "sec", "seconds", ""}:
                    return round(float(value), 1), "s", True, notes
                notes.append(f"Unrecognized wave period unit: '{unit}'.")
                return value, unit, False, notes

        # 6. Surface Current -> canonical m/s
        if variable in {"surface_current", "current", "current_speed"}:
            if isinstance(value, (int, float)):
                if u_str in {"m/s", "mps", "ms", ""}:
                    return round(float(value), 2), "m/s", True, notes
                if u_str in {"knots", "kt"}:
                    norm_ms = round(float(value) * 0.514444, 2)
                    notes.append(f"Normalized current speed from {value} knots to {norm_ms} m/s.")
                    return norm_ms, "m/s", True, notes
                notes.append(f"Unrecognized current unit: '{unit}'.")
                return value, unit, False, notes

        # Generic / Other variables
        return value, unit, True, notes

    def _verify_temporal(
        self, evidence: Evidence, now: datetime
    ) -> tuple[bool, str, str, list[str], VerificationSeverity]:
        """Validate timestamps according to evidence classification."""
        notes: list[str] = []
        sev = VerificationSeverity.INFO
        t_status = "VALID"
        f_status = "FRESH"

        # Check for impossible future observation
        if evidence.evidence_type == EvidenceType.OBSERVATION and evidence.observed_at is not None:
            if evidence.observed_at > now + timedelta(minutes=15):
                notes.append(
                    f"Observation timestamp ({evidence.observed_at.isoformat()}) is in the future relative to {now.isoformat()}."
                )
                return False, "FUTURE_TIMESTAMP", "INVALID", notes, VerificationSeverity.BLOCKING

        # Evaluate freshness based on evidence classification
        if evidence.evidence_type == EvidenceType.OBSERVATION:
            ref_dt = evidence.observed_at or evidence.retrieved_at
            age_hours = (now - ref_dt).total_seconds() / 3600.0
            policy_hours = evidence.source.freshness_policy_hours
            if age_hours > policy_hours:
                f_status = "STALE"
                if age_hours > policy_hours * 3.0:
                    notes.append(f"Observation is severely stale (age: {age_hours:.1f}h, policy: {policy_hours:.1f}h).")
                    return False, "STALE_OBSERVATION", f_status, notes, VerificationSeverity.WARNING
                else:
                    notes.append(f"Observation exceeds freshness policy (age: {age_hours:.1f}h, policy: {policy_hours:.1f}h).")
                    return True, "AGED_OBSERVATION", f_status, notes, VerificationSeverity.WARNING

        elif evidence.evidence_type == EvidenceType.FORECAST:
            # Check forecast validity window
            valid_time = evidence.forecast_valid_at or evidence.valid_until
            if valid_time is not None:
                if now > valid_time + timedelta(hours=6):
                    notes.append(
                        f"Forecast validity window expired at {valid_time.isoformat()} (current time {now.isoformat()})."
                    )
                    return False, "EXPIRED_FORECAST", "EXPIRED", notes, VerificationSeverity.WARNING
                elif now <= valid_time:
                    f_status = "ACTIVE_FORECAST"
                    t_status = "VALID_FORECAST"

        elif evidence.evidence_type == EvidenceType.WARNING:
            # Check warning validity window
            if evidence.valid_until is not None and now > evidence.valid_until:
                notes.append(f"Marine warning bulletin expired at {evidence.valid_until.isoformat()}.")
                return False, "EXPIRED_WARNING", "EXPIRED", notes, VerificationSeverity.WARNING
            if evidence.valid_from is not None and now < evidence.valid_from - timedelta(hours=24):
                notes.append(f"Marine warning bulletin validity starts in the distant future ({evidence.valid_from.isoformat()}).")
                return False, "FUTURE_WARNING", "PENDING", notes, VerificationSeverity.WARNING

        return True, t_status, f_status, notes, sev

    def _verify_spatial(
        self, evidence: Evidence, target_location: Geometry | None, max_radius_km: float
    ) -> tuple[bool, str, list[str], VerificationSeverity]:
        """Validate geographic proximity and domain coverage."""
        notes: list[str] = []

        if target_location is None or evidence.geometry is None:
            # Geometry absent: check if regional metadata exists
            return True, "REGIONAL_COVERAGE", notes, VerificationSeverity.INFO

        dist_km = haversine_distance_km(
            target_location.lat, target_location.lon, evidence.geometry.lat, evidence.geometry.lon
        )

        if dist_km <= max_radius_km:
            return True, "IN_DOMAIN", notes, VerificationSeverity.INFO

        if dist_km <= max_radius_km * 2.5:
            notes.append(
                f"Evidence location ({evidence.geometry.lat}, {evidence.geometry.lon}) is at {dist_km:.1f} km from target, "
                f"exceeding nominal radius {max_radius_km:.1f} km."
            )
            return True, "EXTENDED_PROXIMITY", notes, VerificationSeverity.WARNING

        # Spatially irrelevant (> 2.5x radius)
        notes.append(
            f"Evidence location ({evidence.geometry.lat}, {evidence.geometry.lon}) is at {dist_km:.1f} km from target, "
            f"outside operational radius ({max_radius_km:.1f} km)."
        )
        return False, "OUT_OF_DOMAIN", notes, VerificationSeverity.BLOCKING

    def _verify_source_policy(self, evidence: Evidence) -> tuple[bool, str, list[str], VerificationSeverity]:
        """Validate source against authoritative SourcePolicyRegistry."""
        notes: list[str] = []
        source_id = evidence.source.source_id

        policy = self.source_registry.get_policy(source_id)
        if policy.trust_tier == SourceTrustTier.UNTRUSTED:
            if evidence.source.authority in {"official", "scientific"}:
                notes.append(f"Source '{source_id}' is unindexed in policy registry; permitted with WARNING based on declared {evidence.source.authority} authority.")
                return True, "UNINDEXED_OFFICIAL_SOURCE", notes, VerificationSeverity.WARNING
            notes.append(f"Source '{source_id}' is UNTRUSTED under current source policy.")
            return False, "UNTRUSTED_SOURCE", notes, VerificationSeverity.BLOCKING

        is_valid, msg = self.source_registry.validate_evidence(evidence)
        if not is_valid:
            notes.append(msg)
            return False, "UNAUTHORIZED_VARIABLE", notes, VerificationSeverity.WARNING

        return True, "AUTHORIZED", notes, VerificationSeverity.INFO

    def _verify_physical_qc(
        self, variable: str, value: Any, unit: str | None, geometry: Geometry | None
    ) -> tuple[bool, bool, VerificationStatus, VerificationSeverity, list[str]]:
        """Validate physical sanity (Level A) and regional plausibility (Level B)."""
        notes: list[str] = []

        # Extract numeric magnitude for scalar validation
        scalar_val: float | None = None
        if isinstance(value, (int, float)):
            scalar_val = float(value)
        elif isinstance(value, dict):
            if variable in {"wind", "wind_speed"}:
                scalar_val = float(value.get("wind_speed_knots") or value.get("wind_speed") or 0.0)
            elif variable == "significant_wave_height":
                scalar_val = float(value.get("significant_wave_height_m") or 0.0)

        if scalar_val is None:
            return True, True, VerificationStatus.VALID, VerificationSeverity.INFO, notes

        # Level A: Check Absolute Sanity Bounds (Hard Scientific Limits)
        if variable in ABSOLUTE_SANITY_BOUNDS:
            min_val, max_val = ABSOLUTE_SANITY_BOUNDS[variable]
            if scalar_val < min_val or scalar_val > max_val:
                notes.append(
                    f"Physical sanity check failed for {variable}: {scalar_val} {unit} is outside "
                    f"absolute physical bounds [{min_val}, {max_val}]."
                )
                return False, False, VerificationStatus.INVALID, VerificationSeverity.BLOCKING, notes

        # Level B: Check Regional Climatological Bounds (Indian Ocean)
        is_indian = True
        if geometry is not None:
            is_indian = is_within_operational_region(geometry.lat, geometry.lon)

        if is_indian and variable in INDIAN_OCEAN_REGIONAL_QC_BOUNDS:
            reg_min, reg_max = INDIAN_OCEAN_REGIONAL_QC_BOUNDS[variable]
            if scalar_val < reg_min or scalar_val > reg_max:
                notes.append(
                    f"Regional QC notice for {variable}: {scalar_val} {unit} is outside typical "
                    f"Indian Ocean climatological range [{reg_min}, {reg_max}], flagged as anomalous."
                )
                # Regional ranges must be warnings/QC, NEVER automatic invalidation!
                return True, False, VerificationStatus.ANOMALOUS, VerificationSeverity.WARNING, notes

        return True, True, VerificationStatus.VALID, VerificationSeverity.INFO, notes


class SourceArbitrator:
    """Cross-source comparison, agreement recording, and conflict detection engine.

    Enforces:
    - No automatic weighted averaging of agreeing sources (retains preferred operational source).
    - Variable-specific conflict tolerances.
    - Deterministic ConflictRecord generation and confidence penalties on significant conflicts.
    - Sourcing preservation for both conflicting parties.
    """

    def __init__(self) -> None:
        self.tolerances = VARIABLE_CONFLICT_THRESHOLDS

    def arbitrate(self, evidences: list[Evidence]) -> ArbitrationResult:
        """Analyze evidence items for cross-source agreement or conflict."""
        conflicts: list[ConflictRecord] = []
        agreements: list[dict[str, Any]] = []
        notes: list[str] = []
        confidence_penalty = 0.0

        # Group by (normalized_variable, evidence_type)
        grouped: dict[tuple[str, EvidenceType], list[Evidence]] = {}
        for ev in evidences:
            key = (ev.variable, ev.evidence_type)
            grouped.setdefault(key, []).append(ev)

        arbitrated_evidences: list[Evidence] = list(evidences)

        for (var, ev_type), items in grouped.items():
            if len(items) < 2:
                continue

            # Compare pairs of different sources
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    ev1, ev2 = items[i], items[j]
                    if ev1.source.source_id == ev2.source.source_id:
                        continue

                    # Check spatiotemporal compatibility
                    if not self._are_spatiotemporally_comparable(ev1, ev2):
                        continue

                    # Extract values for comparison
                    val1 = self._extract_scalar(ev1)
                    val2 = self._extract_scalar(ev2)
                    if val1 is None or val2 is None:
                        continue

                    diff = abs(val1 - val2)
                    is_conflict, is_agreement, summary = self._evaluate_discrepancy(var, val1, val2, ev1, ev2)

                    if is_conflict:
                        conf_rec = ConflictRecord(
                            variable=var,
                            values=[ev1, ev2],
                            spread_summary=summary,
                            resolution="report_spread",
                        )
                        conflicts.append(conf_rec)
                        confidence_penalty += 0.15
                        notes.append(f"Conflict detected for {var}: {summary}")
                    elif is_agreement:
                        pref_source = self._determine_preferred_source(ev1, ev2)
                        agreements.append(
                            {
                                "variable": var,
                                "source_1": ev1.source.source_id,
                                "value_1": val1,
                                "source_2": ev2.source.source_id,
                                "value_2": val2,
                                "discrepancy": round(diff, 3),
                                "preferred_source": pref_source.source.source_id,
                                "retained_value": self._extract_scalar(pref_source),
                                "notes": summary,
                            }
                        )
                        notes.append(f"Cross-source agreement confirmed for {var}: {summary}")

        # Cap confidence penalty at 0.40
        confidence_penalty = min(0.40, confidence_penalty)

        return ArbitrationResult(
            conflicts=conflicts,
            agreements=agreements,
            confidence_penalty=confidence_penalty,
            arbitrated_evidences=arbitrated_evidences,
            notes=notes,
        )

    def _are_spatiotemporally_comparable(self, ev1: Evidence, ev2: Evidence) -> bool:
        """Check if two evidence items refer to overlapping space and time."""
        # Spatial check
        if ev1.geometry and ev2.geometry:
            dist = haversine_distance_km(
                ev1.geometry.lat, ev1.geometry.lon, ev2.geometry.lat, ev2.geometry.lon
            )
            if dist > 100.0:
                return False

        # Temporal check
        t1 = ev1.observed_at or ev1.forecast_valid_at or ev1.retrieved_at
        t2 = ev2.observed_at or ev2.forecast_valid_at or ev2.retrieved_at
        if t1 and t2:
            delta_hours = abs((t1 - t2).total_seconds()) / 3600.0
            if delta_hours > 6.0:
                return False

        return True

    def _extract_scalar(self, ev: Evidence) -> float | None:
        """Extract primary numeric value for discrepancy analysis."""
        v = ev.normalized_value if ev.normalized_value is not None else ev.value
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, dict):
            if "wind_speed_knots" in v:
                return float(v["wind_speed_knots"])
            if "significant_wave_height_m" in v:
                return float(v["significant_wave_height_m"])
            if "temperature_c" in v and v["temperature_c"] is not None:
                return float(v["temperature_c"])
        return None

    def _evaluate_discrepancy(
        self, variable: str, val1: float, val2: float, ev1: Evidence, ev2: Evidence
    ) -> tuple[bool, bool, str]:
        """Evaluate whether numerical discrepancy constitutes agreement or conflict."""
        diff = abs(val1 - val2)
        s1 = ev1.source.source_id
        s2 = ev2.source.source_id

        # 1. SST
        if variable in {"sea_surface_temperature", "sst"}:
            thresh = self.tolerances["sea_surface_temperature"]
            if diff > thresh["conflict"]:
                summary = f"{s1} ({val1:.2f}°C) vs {s2} ({val2:.2f}°C) diverged by {diff:.2f}°C (threshold: {thresh['conflict']}°C)."
                return True, False, summary
            elif diff <= thresh["tolerance"]:
                summary = f"{s1} ({val1:.2f}°C) and {s2} ({val2:.2f}°C) are in agreement within {diff:.2f}°C."
                return False, True, summary

        # 2. Chlorophyll-a
        if variable in {"chlorophyll_a", "chlorophyll"}:
            thresh = self.tolerances["chlorophyll_a"]
            max_val = max(val1, val2, 0.001)
            rel_diff = diff / max_val
            if rel_diff > thresh["rel_conflict"] and diff > thresh["abs_min"]:
                summary = f"{s1} ({val1:.3f} mg/m³) vs {s2} ({val2:.3f} mg/m³) diverged by {diff:.3f} mg/m³ ({rel_diff*100:.1f}%)."
                return True, False, summary
            elif rel_diff <= thresh["rel_tolerance"] or diff <= thresh["abs_min"]:
                summary = f"{s1} ({val1:.3f} mg/m³) and {s2} ({val2:.3f} mg/m³) are in agreement."
                return False, True, summary

        # 3. Wave Height
        if variable in {"significant_wave_height", "wave_height"}:
            thresh = self.tolerances["significant_wave_height"]
            if diff > thresh["conflict"]:
                summary = f"{s1} ({val1:.2f} m) vs {s2} ({val2:.2f} m) diverged by {diff:.2f} m."
                return True, False, summary
            elif diff <= thresh["tolerance"]:
                summary = f"{s1} ({val1:.2f} m) and {s2} ({val2:.2f} m) are in agreement."
                return False, True, summary

        # 4. Wind Speed
        if variable in {"wind", "wind_speed"}:
            thresh = self.tolerances["wind_speed"]
            if diff > thresh["conflict"]:
                summary = f"{s1} ({val1:.1f} kt) vs {s2} ({val2:.1f} kt) diverged by {diff:.1f} knots."
                return True, False, summary
            elif diff <= thresh["tolerance"]:
                summary = f"{s1} ({val1:.1f} kt) and {s2} ({val2:.1f} kt) are in agreement."
                return False, True, summary

        # Default: relative 30% difference
        mean_val = (val1 + val2) / 2.0 if (val1 + val2) != 0 else 1.0
        rel_diff = diff / abs(mean_val)
        if rel_diff > 0.40:
            return True, False, f"{s1} ({val1}) vs {s2} ({val2}) divergence exceeds 40% ({rel_diff*100:.1f}%)."
        return False, True, f"{s1} ({val1}) and {s2} ({val2}) within acceptable variance."

    def _determine_preferred_source(self, ev1: Evidence, ev2: Evidence) -> Evidence:
        """Select primary operational source without fabricating artificial averages."""
        # Operational regional authority preference: INCOIS in Indian waters, NOAA in US waters
        s1 = ev1.source.source_id.lower()
        s2 = ev2.source.source_id.lower()

        if "incois" in s1 and "incois" not in s2:
            return ev1
        if "incois" in s2 and "incois" not in s1:
            return ev2

        if "noaa" in s1 and "noaa" not in s2:
            return ev1
        if "noaa" in s2 and "noaa" not in s1:
            return ev2

        # Preference by authority metadata
        if ev1.source.authority == "official" and ev2.source.authority != "official":
            return ev1
        if ev2.source.authority == "official" and ev1.source.authority != "official":
            return ev2

        # Retain freshest
        t1 = ev1.retrieved_at
        t2 = ev2.retrieved_at
        return ev1 if t1 >= t2 else ev2
