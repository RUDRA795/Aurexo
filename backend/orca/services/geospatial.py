from __future__ import annotations

import asyncpg

from orca.database.session import get_raw_database_url
from orca.schemas.pfz_contract import DistanceRequest, DistanceResult


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

    return DistanceResult(
        distances_km=[float(row["distance_km"]) for row in rows],
        bearings_deg=[float(row["bearing_deg"]) % 360.0 for row in rows],
        method="postgis_geography",
    )
