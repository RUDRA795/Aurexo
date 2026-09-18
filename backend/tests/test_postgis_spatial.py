import pytest

from orca.agents.pfz_pipeline import calculate_distance
from orca.schemas.orca_contract import Geometry
from orca.schemas.pfz_contract import DistanceRequest
from orca.services.geospatial import calculate_distance_postgis

GOA_ORIGIN = Geometry(lat=15.49, lon=73.83)
DESTINATIONS = [
    Geometry(lat=15.62, lon=73.55),  # Malim sector
    Geometry(lat=15.20, lon=73.70),  # Betul sector
    Geometry(lat=18.92, lon=72.83),  # Mumbai
]


@pytest.mark.asyncio
async def test_postgis_distance_returns_geography_method():
    request = DistanceRequest(origin=GOA_ORIGIN, destinations=DESTINATIONS)
    result = await calculate_distance_postgis(request)

    assert result.method == "postgis_geography"
    assert len(result.distances_km) == len(DESTINATIONS)
    assert len(result.bearings_deg) == len(DESTINATIONS)
    assert all(d > 0 for d in result.distances_km)
    assert all(0 <= b < 360 for b in result.bearings_deg)


@pytest.mark.asyncio
async def test_postgis_distance_compares_with_haversine():
    request = DistanceRequest(origin=GOA_ORIGIN, destinations=DESTINATIONS)
    postgis_result = await calculate_distance_postgis(request)
    haversine_result = calculate_distance(request)

    # PostGIS WGS84 geography uses WGS-84 spheroid, while Haversine uses spherical Earth.
    # Discrepancy is typically < 0.5% for mid/low latitudes.
    for pg_dist, hav_dist in zip(postgis_result.distances_km, haversine_result.distances_km):
        pct_diff = abs(pg_dist - hav_dist) / hav_dist
        assert pct_diff < 0.005, f"PostGIS {pg_dist}km vs Haversine {hav_dist}km diff {pct_diff:.4%}"

    for pg_brg, hav_brg in zip(postgis_result.bearings_deg, haversine_result.bearings_deg):
        diff = abs(pg_brg - hav_brg)
        # Azimuth comparison within 1 degree
        assert diff < 1.0 or abs(diff - 360.0) < 1.0


@pytest.mark.asyncio
async def test_postgis_empty_destinations():
    # Constructing without Pydantic min_length error by bypassing validation or directly testing helper
    request = DistanceRequest.__new__(DistanceRequest)
    object.__setattr__(request, "origin", GOA_ORIGIN)
    object.__setattr__(request, "destinations", [])

    result = await calculate_distance_postgis(request)
    assert result.distances_km == []
    assert result.bearings_deg == []
    assert result.method == "postgis_geography"
