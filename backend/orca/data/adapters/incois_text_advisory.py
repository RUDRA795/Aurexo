from __future__ import annotations

from datetime import datetime, timedelta
import math
import os
import re
from typing import Any

from orca.agents.pfz_pipeline import PFZDataSource, PFZSourceUnavailable
from orca.data.adapters.base import BaseMarineAdapter
from orca.schemas.orca_contract import AccessMethod, Geometry, SourceMetadata, utc_now
from orca.schemas.pfz_contract import PFZAccessTier, PFZPoint, PFZQuery, PFZQueryResult

# Coordinates of principal coastal landing centers for spatial resolution of text advisories
LANDING_CENTER_COORDINATES: dict[str, tuple[float, float]] = {
    # Goa
    "MALIM": (15.503, 73.829),
    "PANJIM": (15.498, 73.827),
    "PANAJI": (15.498, 73.827),
    "BETUL": (15.148, 73.955),
    "VASCO": (15.398, 73.811),
    "CHAPORA": (15.605, 73.738),
    # Maharashtra
    "SASSOON DOCK": (18.917, 72.825),
    "VERSOVA": (19.135, 72.812),
    "RATNAGIRI": (16.985, 73.284),
    "MALVAN": (16.061, 73.468),
    # Kerala
    "KOCHI": (9.967, 76.242),
    "MUNAMBAM": (10.183, 76.175),
    "VIZHINJAM": (8.378, 76.993),
    # Karnataka
    "MALPE": (13.351, 74.702),
    "KARWAR": (14.808, 74.126),
    "MANGALORE": (12.853, 74.838),
}


class INCOISTextAdvisoryAdapter(PFZDataSource, BaseMarineAdapter):
    """Fallback adapter parsing official INCOIS multilingual text advisories."""

    tier = PFZAccessTier.TEXT_ADVISORY

    def __init__(
        self,
        endpoint_url: str | None = None,
        bulletins: list[dict[str, Any]] | None = None,
        *,
        timeout_seconds: float = 10.0,
        verify_ssl: bool = True,
    ):
        BaseMarineAdapter.__init__(
            self,
            timeout_seconds=timeout_seconds,
            verify_ssl=verify_ssl,
        )
        self.endpoint_url = endpoint_url or os.getenv("INCOIS_TEXT_ADVISORY_URL")
        self._bulletins = bulletins

    @classmethod
    def get_source_metadata(cls) -> SourceMetadata:
        return SourceMetadata(
            source_id="incois_text_advisory",
            organization="INCOIS",
            dataset="PFZ Multilingual Text Advisory",
            domain=["pfz", "fisheries", "text_bulletin"],
            coverage="indian_coast",
            latency="daily",
            authority="official",
            access=AccessMethod.SCRAPE,
            freshness_policy_hours=36.0,
            fallbacks=["incois_pfz_cached"],
        )

    async def fetch(self, query: PFZQuery) -> PFZQueryResult:
        # If static/captured bulletins provided in deployment config, use them
        if self._bulletins is not None:
            points = self.parse_bulletin_records(self._bulletins, query=query)
            if not points:
                raise PFZSourceUnavailable("No valid points found in configured text bulletins")
            return PFZQueryResult(
                points=points,
                source=self.get_source_metadata(),
                access_tier=self.tier,
                retrieved_at=utc_now(),
                limitations=["Official operational INCOIS text advisory bulletin extraction."],
            )

        if not self.endpoint_url:
            raise PFZSourceUnavailable(
                "INCOIS text advisory endpoint not configured and no bulletin feed supplied."
            )

        try:
            async with self.create_client() as client:
                response = await client.get(self.endpoint_url)
                if response.status_code != 200:
                    raise PFZSourceUnavailable(
                        f"INCOIS text advisory returned HTTP {response.status_code}"
                    )
                raw_text = response.text
        except Exception as exc:
            raise PFZSourceUnavailable(f"INCOIS text advisory network error: {exc}")

        points = self.parse_text_bulletin(raw_text, query=query)
        if not points:
            raise PFZSourceUnavailable("No matching valid PFZ entries parsed from text bulletin.")

        return PFZQueryResult(
            points=points,
            source=self.get_source_metadata(),
            access_tier=self.tier,
            retrieved_at=utc_now(),
            limitations=["Official operational INCOIS text advisory bulletin extraction."],
        )

    def parse_bulletin_records(
        self, records: list[dict[str, Any]], query: PFZQuery | None = None
    ) -> list[PFZPoint]:
        points: list[PFZPoint] = []
        for r in records:
            point = self._record_to_point(r)
            if point is None:
                continue
            if query and query.sector and point.sector != query.sector:
                continue
            if query and query.valid_at and not point.is_valid_at(query.valid_at):
                continue
            points.append(point)
        return points

    def _record_to_point(self, r: dict[str, Any]) -> PFZPoint | None:
        sector = str(r.get("sector", "")).strip().upper()
        center = str(r.get("landing_center", "")).strip().upper()
        lat = r.get("lat")
        lon = r.get("lon")
        geom_derivation = "original_point"

        # Derive lat/lon from known landing center if offset given
        if (lat is None or lon is None) and center in LANDING_CENTER_COORDINATES:
            base_lat, base_lon = LANDING_CENTER_COORDINATES[center]
            dist_km = float(r.get("distance_km", 0.0))
            bearing_deg = float(r.get("bearing_deg", 0.0))
            # Rough geographic shift for text advisory point
            dlat = (dist_km / 111.0) * math.cos(math.radians(bearing_deg))
            dlon = (dist_km / (111.0 * math.cos(math.radians(base_lat)))) * math.sin(math.radians(bearing_deg))
            lat = round(base_lat + dlat, 4)
            lon = round(base_lon + dlon, 4)
            geom_derivation = "landing_center_bearing_derived"

        if lat is None or lon is None:
            return None

        pfz_id = str(r.get("pfz_id") or f"txt_{sector}_{center}_{len(r)}")
        now = utc_now()
        source_valid_from = r.get("valid_from")
        source_valid_until = r.get("valid_until")

        if source_valid_from is not None:
            valid_from = source_valid_from
        else:
            valid_from = now - timedelta(hours=1)

        if source_valid_until is not None:
            valid_until = source_valid_until
            validity_derivation = "source_provided"
        else:
            valid_until = valid_from + timedelta(hours=36)
            validity_derivation = "orca_freshness_policy"

        return PFZPoint(
            pfz_id=pfz_id,
            location=Geometry(lat=float(lat), lon=float(lon)),
            sector=sector,
            depth_m=r.get("depth_m"),
            landing_center=center or None,
            distance_from_landing_center_km=r.get("distance_km"),
            bearing_from_landing_center_deg=r.get("bearing_deg"),
            forecast_date=r.get("forecast_date") or valid_from,
            valid_from=valid_from,
            valid_until=valid_until,
            wind_speed_ms=r.get("wind_speed_ms"),
            wind_direction_deg=r.get("wind_direction_deg"),
            geometry_derivation=geom_derivation,
            source_valid_from=source_valid_from,
            source_valid_until=source_valid_until,
            validity_derivation=validity_derivation,
        )

    def parse_text_bulletin(self, text: str, query: PFZQuery | None = None) -> list[PFZPoint]:
        # Regex parser for standard INCOIS bulletin lines:
        # e.g.: "Sector: GOA, Landing Center: Malim, Bearing: 270 deg, Distance: 35 km, Depth: 45 m"
        pattern = re.compile(
            r"Sector:\s*([A-Za-z\s]+?),\s*Landing Center:\s*([A-Za-z\s]+?),\s*Bearing:\s*(\d+)\s*deg,\s*Distance:\s*(\d+(?:\.\d+)?)\s*km(?:,\s*Depth:\s*(\d+(?:\.\d+)?)\s*m)?",
            re.IGNORECASE,
        )
        records = []
        for match in pattern.finditer(text):
            sec, center, bearing, dist, depth = match.groups()
            records.append({
                "sector": sec.strip(),
                "landing_center": center.strip(),
                "bearing_deg": float(bearing),
                "distance_km": float(dist),
                "depth_m": float(depth) if depth else None,
            })
        return self.parse_bulletin_records(records, query=query)
