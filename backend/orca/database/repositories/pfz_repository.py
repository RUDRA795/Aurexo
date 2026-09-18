from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from orca.database.models.pfz import PFZPointModel
from orca.schemas.orca_contract import Geometry
from orca.schemas.pfz_contract import PFZPoint


class PFZRepository:
    """Production PostGIS repository for PFZ points."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_points(
        self,
        points: list[PFZPoint],
        *,
        source_id: str = "incois",
        access_tier: str = "text_advisory",
    ) -> int:
        """Upsert a batch of PFZ points."""
        if not points:
            return 0

        count = 0
        for p in points:
            model = PFZPointModel.from_pydantic(
                p,
                source_id=source_id,
                access_tier=access_tier,
            )
            stmt = insert(PFZPointModel).values(
                pfz_id=model.pfz_id,
                geom=model.geom,
                sector=model.sector,
                depth_m=model.depth_m,
                landing_center=model.landing_center,
                distance_from_landing_center_km=model.distance_from_landing_center_km,
                bearing_from_landing_center_deg=model.bearing_from_landing_center_deg,
                forecast_date=model.forecast_date,
                valid_from=model.valid_from,
                valid_until=model.valid_until,
                wind_speed_ms=model.wind_speed_ms,
                wind_direction_deg=model.wind_direction_deg,
                source_id=model.source_id,
                access_tier=model.access_tier,
                raw_metadata=model.raw_metadata,
                created_at=model.created_at,
                updated_at=model.updated_at,
            )
            # Update on conflict of (pfz_id, forecast_date)
            update_dict = {
                "geom": stmt.excluded.geom,
                "sector": stmt.excluded.sector,
                "depth_m": stmt.excluded.depth_m,
                "landing_center": stmt.excluded.landing_center,
                "distance_from_landing_center_km": stmt.excluded.distance_from_landing_center_km,
                "bearing_from_landing_center_deg": stmt.excluded.bearing_from_landing_center_deg,
                "valid_from": stmt.excluded.valid_from,
                "valid_until": stmt.excluded.valid_until,
                "wind_speed_ms": stmt.excluded.wind_speed_ms,
                "wind_direction_deg": stmt.excluded.wind_direction_deg,
                "updated_at": model.updated_at,
            }
            stmt = stmt.on_conflict_do_update(
                constraint="uq_pfz_points_id_forecast",
                set_=update_dict,
            )
            await self.session.execute(stmt)
            count += 1

        await self.session.commit()
        return count

    async def query_nearest(
        self,
        origin: Geometry,
        valid_at: datetime,
        radius_km: float,
        sector: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Query nearest PFZ points within radius_km applying PostGIS geography operations."""
        radius_m = radius_km * 1000.0
        normalized_sector = sector.strip().upper() if sector else None

        sql = text(
            """
            SELECT
                id,
                pfz_id,
                sector,
                depth_m,
                landing_center,
                distance_from_landing_center_km,
                bearing_from_landing_center_deg,
                forecast_date,
                valid_from,
                valid_until,
                wind_speed_ms,
                wind_direction_deg,
                source_id,
                access_tier,
                ST_X(geom::geometry) AS lon,
                ST_Y(geom::geometry) AS lat,
                ST_Distance(
                    geom,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography
                ) / 1000.0 AS distance_km,
                COALESCE(
                    DEGREES(
                        ST_Azimuth(
                            ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                            geom
                        )
                    ),
                    0.0
                ) AS bearing_deg
            FROM pfz_points
            WHERE (valid_from IS NULL OR valid_from <= cast(:valid_at as timestamptz))
              AND (valid_until IS NULL OR valid_until >= cast(:valid_at as timestamptz))
              AND (cast(:sector as varchar) IS NULL OR sector = cast(:sector as varchar))
              AND ST_DWithin(
                    geom,
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography,
                    :radius_m
                  )
            ORDER BY distance_km ASC
            LIMIT :limit;
            """
        )

        params = {
            "lon": float(origin.lon),
            "lat": float(origin.lat),
            "valid_at": valid_at,
            "sector": normalized_sector,
            "radius_m": float(radius_m),
            "limit": int(limit),
        }

        result = await self.session.execute(sql, params)
        rows = result.mappings().all()

        candidates: list[dict[str, Any]] = []
        for r in rows:
            point = PFZPoint(
                pfz_id=r["pfz_id"],
                location=Geometry(lat=float(r["lat"]), lon=float(r["lon"])),
                sector=r["sector"],
                depth_m=r["depth_m"],
                landing_center=r["landing_center"],
                distance_from_landing_center_km=r["distance_from_landing_center_km"],
                bearing_from_landing_center_deg=r["bearing_from_landing_center_deg"],
                forecast_date=r["forecast_date"],
                valid_from=r["valid_from"],
                valid_until=r["valid_until"],
                wind_speed_ms=r["wind_speed_ms"],
                wind_direction_deg=r["wind_direction_deg"],
            )
            candidates.append(
                {
                    "point": point,
                    "distance_km": float(r["distance_km"]),
                    "bearing_deg": float(r["bearing_deg"]) % 360.0,
                    "source_id": r["source_id"],
                    "access_tier": r["access_tier"],
                }
            )

        return candidates

    async def count(self) -> int:
        result = await self.session.execute(select(PFZPointModel.id))
        return len(result.all())
