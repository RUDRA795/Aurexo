"""Typed PFZ contracts built on ORCA Agent Contract v2."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .orca_contract import ContractBase, Geometry, SourceMetadata, _require_aware


class PFZQuery(ContractBase):
    location: Geometry
    valid_at: datetime
    radius_km: float = Field(default=300.0, gt=0, le=2000)
    sector: str | None = None
    source_preference: list[str] = Field(default_factory=list)

    @field_validator("valid_at")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        return _require_aware(v)

    @field_validator("sector")
    @classmethod
    def normalize_sector(cls, v: str | None) -> str | None:
        return v.strip().upper() if v else v


class PFZPoint(ContractBase):
    pfz_id: str
    location: Geometry
    sector: str
    depth_m: float | None = None
    landing_center: str | None = None
    distance_from_landing_center_km: float | None = None
    bearing_from_landing_center_deg: float | None = None
    forecast_date: datetime | None = None
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    freshness_deadline: datetime | None = None
    wind_speed_ms: float | None = None
    wind_direction_deg: float | None = None
    raw_geometry: dict[str, Any] | None = None
    geometry_derivation: Literal["original_point", "line_midpoint_derived", "landing_center_bearing_derived", "unknown"] = "unknown"
    source_valid_from: datetime | None = None
    source_valid_until: datetime | None = None
    validity_derivation: Literal["source_provided", "orca_freshness_policy", "unknown"] = "unknown"

    @field_validator("forecast_date", "valid_from", "valid_until", "freshness_deadline", "source_valid_from", "source_valid_until")
    @classmethod
    def aware(cls, v: datetime | None) -> datetime | None:
        return None if v is None else _require_aware(v)

    @field_validator("sector")
    @classmethod
    def normalize_sector(cls, v: str) -> str:
        return v.strip().upper()

    def is_valid_at(self, t: datetime) -> bool:
        t = _require_aware(t)
        if self.source_valid_from and t < self.source_valid_from:
            return False
        if self.source_valid_until and t > self.source_valid_until:
            return False
        if self.freshness_deadline and t > self.freshness_deadline:
            return False
        if self.valid_from and t < self.valid_from:
            return False
        if self.valid_until and t > self.valid_until:
            return False
        return True


class PFZAccessTier(str, Enum):
    STRUCTURED_SPATIAL = "structured_spatial"
    WEBGIS_LAYER = "webgis_layer"
    TEXT_ADVISORY = "text_advisory"
    ERDDAP_DERIVED = "erddap_derived"
    CACHED = "cached"
    UNAVAILABLE = "unavailable"


class PFZQueryResult(ContractBase):
    points: list[PFZPoint]
    source: SourceMetadata
    access_tier: PFZAccessTier
    retrieved_at: datetime
    limitations: list[str] = Field(default_factory=list)

    @field_validator("retrieved_at")
    @classmethod
    def aware(cls, v: datetime) -> datetime:
        return _require_aware(v)


class DistanceRequest(ContractBase):
    origin: Geometry
    destinations: list[Geometry] = Field(..., min_length=1)


class DistanceResult(ContractBase):
    distances_km: list[float]
    bearings_deg: list[float]
    method: Literal["postgis_geography", "haversine_fallback"]

    @field_validator("distances_km", "bearings_deg")
    @classmethod
    def finite(cls, v: list[float]) -> list[float]:
        import math
        if any(not math.isfinite(x) for x in v):
            raise ValueError("distance/bearing values must be finite")
        return v
