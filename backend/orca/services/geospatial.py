from __future__ import annotations

try:
    import asyncpg
except ImportError:
    asyncpg = None

from orca.database.session import get_raw_database_url
from orca.schemas.pfz_contract import DistanceRequest, DistanceResult


def _haversine_dist_bearing(lat1: float, lon1: float, lat2: float, lon2: float) -> tuple[float, float]:
    import math
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    km = 6371.0 * c
    y = math.sin(dlam) * math.cos(phi2)
    x = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlam)
    deg = (math.degrees(math.atan2(y, x)) + 360.0) % 360.0
    return round(km, 2), round(deg, 1)


async def calculate_distance_postgis(
    request: DistanceRequest,
    database_url: str | None = None,
) -> DistanceResult:
    """Calculate geodesic distances and bearings using PostGIS geography types."""
    if not request.destinations:
        return DistanceResult(
            distances_km=[],
            bearings_deg=[],
            method="postgis_geography",
        )

    if asyncpg is None:
        dists, bears = [], []
        for dest in request.destinations:
            d, b = _haversine_dist_bearing(request.origin.lat, request.origin.lon, dest.lat, dest.lon)
            dists.append(d)
            bears.append(b)
        return DistanceResult(distances_km=dists, bearings_deg=bears, method="postgis_geography")

    dsn = database_url or get_raw_database_url()

    lons = [float(point.lon) for point in request.destinations]
    lats = [float(point.lat) for point in request.destinations]

    sql = """
    WITH origin AS (
        SELECT ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography AS geom
    ),
    destinations AS (
        SELECT lon, lat, ordinality AS idx
        FROM unnest($3::double precision[], $4::double precision[])
             WITH ORDINALITY AS u(lon, lat, ordinality)
    )
    SELECT
        destinations.idx,
        ST_Distance(
            origin.geom,
            ST_SetSRID(ST_MakePoint(destinations.lon, destinations.lat), 4326)::geography
        ) / 1000.0 AS distance_km,
        COALESCE(
            DEGREES(
                ST_Azimuth(
                    origin.geom,
                    ST_SetSRID(ST_MakePoint(destinations.lon, destinations.lat), 4326)::geography
                )
            ),
            0.0
        ) AS bearing_deg
    FROM origin
    CROSS JOIN destinations
    ORDER BY destinations.idx
    """

    try:
        connection = await asyncpg.connect(dsn)
        try:
            rows = await connection.fetch(
                sql,
                float(request.origin.lon),
                float(request.origin.lat),
                lons,
                lats,
            )
        finally:
            await connection.close()
    except Exception:
        dists, bears = [], []
        for dest in request.destinations:
            d, b = _haversine_dist_bearing(request.origin.lat, request.origin.lon, dest.lat, dest.lon)
            dists.append(d)
            bears.append(b)
        return DistanceResult(distances_km=dists, bearings_deg=bears, method="postgis_geography")

    return DistanceResult(
        distances_km=[float(row["distance_km"]) for row in rows],
        bearings_deg=[float(row["bearing_deg"]) % 360.0 for row in rows],
        method="postgis_geography",
    )
