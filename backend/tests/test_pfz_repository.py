from datetime import timedelta
import pytest
from sqlalchemy import text

from orca.database.repositories.pfz_repository import PFZRepository
from orca.database.session import get_session_factory
from orca.schemas.orca_contract import Geometry, utc_now
from orca.schemas.pfz_contract import PFZPoint


@pytest.mark.asyncio
async def test_pfz_repository_lifecycle_and_spatial_query():
    factory = get_session_factory()
    now = utc_now()

    async with factory() as session:
        # Clean up any leftover test records
        await session.execute(text("DELETE FROM pfz_points WHERE pfz_id LIKE 'repo_test_%'"))
        await session.commit()

        repo = PFZRepository(session)

        # 1. Prepare deterministic test points
        p1 = PFZPoint(
            pfz_id="repo_test_goa_near",
            location=Geometry(lat=15.50, lon=73.80),
            sector="GOA",
            depth_m=40.0,
            landing_center="Panaji",
            forecast_date=now,
            valid_from=now - timedelta(hours=1),
            valid_until=now + timedelta(hours=24),
            wind_speed_ms=5.0,
            wind_direction_deg=180.0,
        )
        p2 = PFZPoint(
            pfz_id="repo_test_goa_far",
            location=Geometry(lat=16.50, lon=73.20),
            sector="GOA",
            depth_m=90.0,
            landing_center="Malvan",
            forecast_date=now,
            valid_from=now - timedelta(hours=1),
            valid_until=now + timedelta(hours=24),
            wind_speed_ms=8.0,
            wind_direction_deg=220.0,
        )
        p3_expired = PFZPoint(
            pfz_id="repo_test_goa_expired",
            location=Geometry(lat=15.52, lon=73.82),
            sector="GOA",
            depth_m=35.0,
            landing_center="Panaji",
            forecast_date=now - timedelta(days=2),
            valid_from=now - timedelta(days=2),
            valid_until=now - timedelta(hours=1),
            wind_speed_ms=4.0,
            wind_direction_deg=190.0,
        )
        p4_other_sector = PFZPoint(
            pfz_id="repo_test_kerala_near",
            location=Geometry(lat=15.51, lon=73.79),
            sector="KERALA",
            depth_m=50.0,
            landing_center="Kochi",
            forecast_date=now,
            valid_from=now - timedelta(hours=1),
            valid_until=now + timedelta(hours=24),
            wind_speed_ms=6.0,
            wind_direction_deg=210.0,
        )

        # 2. Upsert points
        count = await repo.upsert_points([p1, p2, p3_expired, p4_other_sector])
        assert count == 4

        # 3. Test nearest search from origin (lat 15.49, lon 73.83)
        origin = Geometry(lat=15.49, lon=73.83)

        # Query small radius (10 km)
        near_results = await repo.query_nearest(
            origin=origin,
            valid_at=now,
            radius_km=10.0,
            sector="GOA",
        )
        assert len(near_results) >= 1
        assert near_results[0]["point"].pfz_id == "repo_test_goa_near"
        assert near_results[0]["distance_km"] < 10.0
        assert 0 <= near_results[0]["bearing_deg"] < 360.0

        # Expired point must not appear
        assert all(r["point"].pfz_id != "repo_test_goa_expired" for r in near_results)

        # Other sector point must not appear when filtered by GOA
        assert all(r["point"].sector == "GOA" for r in near_results)

        # Query with large radius (200 km)
        broad_results = await repo.query_nearest(
            origin=origin,
            valid_at=now,
            radius_km=200.0,
            sector="GOA",
        )
        found_ids = [r["point"].pfz_id for r in broad_results]
        assert "repo_test_goa_near" in found_ids
        assert "repo_test_goa_far" in found_ids

        # Verify ordering: nearest first
        distances = [r["distance_km"] for r in broad_results]
        assert distances == sorted(distances)

        # 4. Test Upsert conflict update
        p1_updated = PFZPoint(
            pfz_id="repo_test_goa_near",
            location=Geometry(lat=15.50, lon=73.80),
            sector="GOA",
            depth_m=42.5,  # updated depth
            landing_center="Panaji",
            forecast_date=now,
            valid_from=now - timedelta(hours=1),
            valid_until=now + timedelta(hours=24),
            wind_speed_ms=11.2,  # updated wind speed
            wind_direction_deg=180.0,
        )
        await repo.upsert_points([p1_updated])

        updated_results = await repo.query_nearest(
            origin=origin,
            valid_at=now,
            radius_km=10.0,
            sector="GOA",
        )
        updated_p1 = next(r for r in updated_results if r["point"].pfz_id == "repo_test_goa_near")
        assert updated_p1["point"].depth_m == 42.5
        assert updated_p1["point"].wind_speed_ms == 11.2
