from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import os
from typing import Any

import httpx
from shapely.geometry import shape

from orca.agents.pfz_pipeline import PFZDataSource, PFZSourceUnavailable
from orca.data.adapters.base import BaseMarineAdapter
from orca.schemas.orca_contract import AccessMethod, Geometry, SourceMetadata, utc_now
from orca.schemas.pfz_contract import PFZAccessTier, PFZPoint, PFZQuery, PFZQueryResult

DEFAULT_INCOIS_WFS_URL = "https://incois.gov.in/geoserver/PFZ_Automation/ows"

SECTOR_NAME_MAP = {
    "GOA": "GOA",
    "MAHARASHTRA": "MAHARASHTRA",
    "KERALA": "KERALA",
    "KARNATAKA": "KARNATAKA",
    "TAMIL NADU": "SOUTH TAMILNADU",
    "TAMILNADU": "SOUTH TAMILNADU",
    "SOUTH TAMILNADU": "SOUTH TAMILNADU",
    "NORTH TAMILNADU": "NORTH TAMILNADU",
    "ANDHRA PRADESH": "SOUTH ANDHRAPRADESH",
    "ANDHRAPRADESH": "SOUTH ANDHRAPRADESH",
    "SOUTH ANDHRAPRADESH": "SOUTH ANDHRAPRADESH",
    "NORTH ANDHRAPRADESH": "NORTH ANDHRAPRADESH",
    "ORISSA": "ORISSA",
    "ODISHA": "ORISSA",
    "WEST BENGAL": "WEST BENGAL",
    "WESTBENGAL": "WEST BENGAL",
    "LAKSHADWEEP": "LAKSHADWEEP",
}


class INCOISPFZWebGISAdapter(PFZDataSource, BaseMarineAdapter):
    """Production adapter fetching official PFZ lines from INCOIS GeoServer WFS."""

    tier = PFZAccessTier.WEBGIS_LAYER

    def __init__(
        self,
        endpoint_url: str | None = None,
        *,
        timeout_seconds: float = 12.0,
        verify_ssl: bool = True,
    ):
        BaseMarineAdapter.__init__(
            self,
            timeout_seconds=timeout_seconds,
            verify_ssl=verify_ssl,
        )
        self.endpoint_url = endpoint_url or os.getenv("INCOIS_PFZ_WFS_URL", DEFAULT_INCOIS_WFS_URL)

    @classmethod
    def get_source_metadata(cls) -> SourceMetadata:
        return SourceMetadata(
            source_id="incois_pfz_webgis",
            organization="INCOIS",
            dataset="PFZ Advisory (GeoServer WFS)",
            domain=["pfz", "fisheries", "thermal_fronts"],
            coverage="indian_coast",
            latency="daily",
            authority="official",
            access=AccessMethod.WEBGIS,
            freshness_policy_hours=36.0,
            fallbacks=["incois_text_advisory", "incois_pfz_cached"],
        )

    async def fetch(self, query: PFZQuery) -> PFZQueryResult:
        params: dict[str, str] = {
            "service": "WFS",
            "version": "1.0.0",
            "request": "GetFeature",
            "typeName": "pfzlines",
            "outputFormat": "application/json",
        }

        # If sector is requested, filter via CQL when recognized
        if query.sector:
            normalized_query_sector = query.sector.strip().upper()
            target_state = SECTOR_NAME_MAP.get(normalized_query_sector, normalized_query_sector)
            params["cql_filter"] = f"State_Name='{target_state}'"

        try:
            async with self.create_client() as client:
                response = await client.get(self.endpoint_url, params=params)
                if response.status_code != 200:
                    raise PFZSourceUnavailable(
                        f"INCOIS WFS returned HTTP {response.status_code}: {response.text[:200]}"
                    )
                try:
                    payload = response.json()
                except Exception as json_err:
                    raise PFZSourceUnavailable(f"INCOIS WFS returned invalid JSON: {json_err}")
        except httpx.TimeoutException as exc:
            raise PFZSourceUnavailable(f"INCOIS WFS timed out after {self.timeout_seconds}s: {exc}")
        except httpx.RequestError as exc:
            raise PFZSourceUnavailable(f"INCOIS WFS request error: {exc}")

        points = self.parse_geojson(payload, query=query)

        return PFZQueryResult(
            points=points,
            source=self.get_source_metadata(),
            access_tier=self.tier,
            retrieved_at=utc_now(),
            limitations=["Official operational INCOIS GeoServer WFS frontal feature retrieval."],
        )

    @staticmethod
    def _all_coords_valid(coords: Any) -> bool:
        if not coords:
            return False
        if isinstance(coords, (list, tuple)):
            if len(coords) >= 2 and isinstance(coords[0], (int, float)) and isinstance(coords[1], (int, float)):
                c0, c1 = float(coords[0]), float(coords[1])
                return (
                    math.isfinite(c0)
                    and math.isfinite(c1)
                    and -180.0 <= c0 <= 180.0
                    and -90.0 <= c1 <= 90.0
                )
            return all(INCOISPFZWebGISAdapter._all_coords_valid(sub) for sub in coords)
        return False

    def parse_geojson(self, payload: dict[str, Any], query: PFZQuery | None = None) -> list[PFZPoint]:
        if not isinstance(payload, dict) or "features" not in payload:
            raise PFZSourceUnavailable("Payload missing required 'features' array")

        raw_features = payload.get("features")
        if not isinstance(raw_features, list):
            raise PFZSourceUnavailable("'features' must be a list")

        points: list[PFZPoint] = []
        seen_ids: set[str] = set()

        for idx, feat in enumerate(raw_features):
            if not isinstance(feat, dict):
                continue

            properties = feat.get("properties") or {}
            geometry_raw = feat.get("geometry")
            if not geometry_raw or not isinstance(geometry_raw, dict):
                continue

            coords = geometry_raw.get("coordinates")
            if not coords or not self._all_coords_valid(coords):
                continue

            try:
                geom_shape = shape(geometry_raw)
                if geom_shape.is_empty:
                    continue
                midpoint = geom_shape.interpolate(0.5, normalized=True)
                lon = float(midpoint.x)
                lat = float(midpoint.y)
            except Exception:
                # Malformed geometry coordinates
                continue

            if not (math.isfinite(lat) and math.isfinite(lon)):
                continue
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
                continue

            uid = str(properties.get("UID") or properties.get("Sno") or f"feat_{idx}")
            pfz_id = f"incois_{uid}"

            # Deduplication
            if pfz_id in seen_ids:
                continue
            seen_ids.add(pfz_id)

            state_name = str(properties.get("State_Name") or "INDIAN_OCEAN").strip().upper()

            # Date calculation from Julian Day & Year
            year_val = properties.get("Year")
            julian_val = properties.get("Julian_day")

            forecast_date: datetime | None = None
            valid_from: datetime | None = None
            valid_until: datetime | None = None
            freshness_deadline: datetime | None = None
            source_valid_from: datetime | None = None
            source_valid_until: datetime | None = None
            validity_derivation = "unknown"

            if year_val is not None and julian_val is not None:
                try:
                    y = int(year_val)
                    jd = int(julian_val)
                    base_date = datetime(y, 1, 1, tzinfo=timezone.utc)
                    forecast_date = base_date + timedelta(days=jd - 1)
                    source_valid_from = forecast_date
                    source_valid_until = None  # WFS layer provides no expiration/valid_until field
                    freshness_deadline = forecast_date + timedelta(hours=36)
                    valid_from = forecast_date
                    valid_until = freshness_deadline
                    validity_derivation = "orca_freshness_policy"
                except (ValueError, TypeError):
                    pass

            # Strict Stale Data Check
            if query and query.valid_at:
                check_deadline = freshness_deadline or valid_until
                if check_deadline and query.valid_at > check_deadline:
                    # Stale observation relative to request validity time
                    continue

            length_km = None
            if properties.get("Length") is not None:
                try:
                    length_km = float(properties["Length"])
                except (ValueError, TypeError):
                    pass

            point = PFZPoint(
                pfz_id=pfz_id,
                location=Geometry(lat=lat, lon=lon),
                sector=state_name,
                distance_from_landing_center_km=length_km,
                forecast_date=forecast_date,
                valid_from=valid_from,
                valid_until=valid_until,
                freshness_deadline=freshness_deadline,
                raw_geometry=geometry_raw,
                geometry_derivation="line_midpoint_derived",
                source_valid_from=source_valid_from,
                source_valid_until=source_valid_until,
                validity_derivation=validity_derivation,
            )
            points.append(point)

        return points
