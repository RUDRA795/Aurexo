from __future__ import annotations

from datetime import datetime
from typing import Any

from geoalchemy2 import Geography
from geoalchemy2.shape import to_shape
from shapely.geometry import Point as ShapelyPoint
from sqlalchemy import BigInteger, DateTime, Float, Index, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from orca.database.models.base import Base, TimestampMixin
from orca.schemas.orca_contract import Geometry
from orca.schemas.pfz_contract import PFZPoint


class PFZPointModel(Base, TimestampMixin):
    __tablename__ = "pfz_points"
    __table_args__ = (
        Index("ix_pfz_points_sector_valid", "sector", "valid_from", "valid_until"),
        UniqueConstraint("pfz_id", "forecast_date", name="uq_pfz_points_id_forecast"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    pfz_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    geom = mapped_column(
        Geography(geometry_type="POINT", srid=4326, spatial_index=True),
        nullable=False,
    )
    sector: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    depth_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    landing_center: Mapped[str | None] = mapped_column(String(128), nullable=True)
    distance_from_landing_center_km: Mapped[float | None] = mapped_column(Float, nullable=True)
    bearing_from_landing_center_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    forecast_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    wind_speed_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_direction_deg: Mapped[float | None] = mapped_column(Float, nullable=True)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False, default="incois")
    access_tier: Mapped[str] = mapped_column(String(64), nullable=False, default="text_advisory")
    raw_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    def to_pydantic(self) -> PFZPoint:
        """Convert database record to typed contract PFZPoint."""
        # Extract lat/lon from geom (handles both WKBElement from DB and WKT string before flush)
        if isinstance(self.geom, str):
            import shapely.wkt
            wkt_str = self.geom.split(";", 1)[1] if ";" in self.geom else self.geom
            shape = shapely.wkt.loads(wkt_str)
        else:
            shape = to_shape(self.geom)
        lon = float(shape.x)
        lat = float(shape.y)
        meta = self.raw_metadata or {}
        return PFZPoint(
            pfz_id=self.pfz_id,
            location=Geometry(lat=lat, lon=lon),
            sector=self.sector,
            depth_m=self.depth_m,
            landing_center=self.landing_center,
            distance_from_landing_center_km=self.distance_from_landing_center_km,
            bearing_from_landing_center_deg=self.bearing_from_landing_center_deg,
            forecast_date=self.forecast_date,
            valid_from=self.valid_from,
            valid_until=self.valid_until,
            freshness_deadline=meta.get("freshness_deadline"),
            wind_speed_ms=self.wind_speed_ms,
            wind_direction_deg=self.wind_direction_deg,
            raw_geometry=meta.get("raw_geometry"),
            geometry_derivation=meta.get("geometry_derivation", "unknown"),
            source_valid_from=meta.get("source_valid_from"),
            source_valid_until=meta.get("source_valid_until"),
            validity_derivation=meta.get("validity_derivation", "unknown"),
        )

    @classmethod
    def from_pydantic(
        cls,
        p: PFZPoint,
        *,
        source_id: str = "incois",
        access_tier: str = "text_advisory",
        raw_metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> PFZPointModel:
        """Factory creating model instance from typed contract PFZPoint."""
        from orca.schemas.orca_contract import utc_now
        now = utc_now()
        wkt_geom = f"SRID=4326;POINT({p.location.lon} {p.location.lat})"
        combined_metadata = dict(raw_metadata or {})
        if p.raw_geometry:
            combined_metadata["raw_geometry"] = p.raw_geometry
        if p.geometry_derivation:
            combined_metadata["geometry_derivation"] = p.geometry_derivation
        if p.source_valid_from:
            combined_metadata["source_valid_from"] = p.source_valid_from.isoformat()
        if p.source_valid_until:
            combined_metadata["source_valid_until"] = p.source_valid_until.isoformat()
        if p.freshness_deadline:
            combined_metadata["freshness_deadline"] = p.freshness_deadline.isoformat()
        if p.validity_derivation:
            combined_metadata["validity_derivation"] = p.validity_derivation

        return cls(
            pfz_id=p.pfz_id,
            geom=wkt_geom,
            sector=p.sector,
            depth_m=p.depth_m,
            landing_center=p.landing_center,
            distance_from_landing_center_km=p.distance_from_landing_center_km,
            bearing_from_landing_center_deg=p.bearing_from_landing_center_deg,
            forecast_date=p.forecast_date,
            valid_from=p.valid_from,
            valid_until=p.valid_until,
            wind_speed_ms=p.wind_speed_ms,
            wind_direction_deg=p.wind_direction_deg,
            source_id=source_id,
            access_tier=access_tier,
            raw_metadata=combined_metadata or None,
            created_at=created_at or now,
            updated_at=updated_at or now,
        )
