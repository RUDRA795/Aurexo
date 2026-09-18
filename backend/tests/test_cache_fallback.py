from datetime import timedelta
import pytest
from sqlalchemy import text

from orca.agents.pfz_pipeline import PFZDataSource, PFZSourceUnavailable, run_pfz_query
from orca.data.adapters.cached_pfz import CachedPFZAdapter
from orca.data.registry import TieredPFZProvider
from orca.database.repositories.pfz_repository import PFZRepository
from orca.database.session import get_session_factory
from orca.schemas.orca_contract import AgentStatus, Geometry, ResponseType, utc_now
from orca.schemas.pfz_contract import PFZAccessTier, PFZPoint, PFZQuery, PFZQueryResult


class AlwaysFailingAdapter(PFZDataSource):
    tier = PFZAccessTier.WEBGIS_LAYER

    async def fetch(self, query: PFZQuery) -> PFZQueryResult:
        raise PFZSourceUnavailable("Simulated upstream network outage")


@pytest.mark.asyncio
async def test_tiered_failover_to_cache():
    factory = get_session_factory()
    now = utc_now()

    # Pre-populate PostGIS cache with a valid point
    async with factory() as session:
        repo = PFZRepository(session)
        cached_point = PFZPoint(
            pfz_id="cache_fallback_valid_01",
            location=Geometry(lat=15.45, lon=73.75),
            sector="GOA",
            forecast_date=now,
            valid_from=now - timedelta(hours=1),
            valid_until=now + timedelta(hours=24),
        )
        await repo.upsert_points([cached_point], source_id="incois_pfz_cached", access_tier="cached")

    cached_adapter = CachedPFZAdapter(session_factory=factory)
    provider = TieredPFZProvider(
        sources=[AlwaysFailingAdapter(), AlwaysFailingAdapter(), cached_adapter],
        auto_cache=False,
    )

    query = PFZQuery(
        location=Geometry(lat=15.49, lon=73.83),
        valid_at=now,
        sector="GOA",
        radius_km=100.0,
    )
    result = await provider.fetch(query)

    assert result.access_tier == PFZAccessTier.CACHED
    assert result.source.source_id == "incois_pfz_cached"
    assert len(result.points) >= 1
    assert any(p.pfz_id == "cache_fallback_valid_01" for p in result.points)


@pytest.mark.asyncio
async def test_stale_cache_is_strictly_rejected():
    factory = get_session_factory()
    now = utc_now()
    stale_valid_at = now + timedelta(days=5)  # 5 days in the future

    cached_adapter = CachedPFZAdapter(session_factory=factory)
    query = PFZQuery(
        location=Geometry(lat=15.49, lon=73.83),
        valid_at=stale_valid_at,
        sector="GOA",
        radius_km=50.0,
    )

    # When querying a timestamp past all cached points validity, must reject as unavailable
    with pytest.raises(PFZSourceUnavailable, match="No unexpired cached PFZ"):
        await cached_adapter.fetch(query)


@pytest.mark.asyncio
async def test_all_tiers_exhausted_produces_honest_error_without_fabrication():
    provider = TieredPFZProvider(
        sources=[AlwaysFailingAdapter(), AlwaysFailingAdapter()],
        auto_cache=False,
    )
    state = await run_pfz_query(
        query_text="Nearest PFZ today?",
        location=Geometry(lat=15.49, lon=73.83),
        valid_at=utc_now(),
        sources=[provider],
    )

    assert state.final_answer is not None
    assert state.final_answer.response_type == ResponseType.ERROR
    assert any(w in state.final_answer.answer_text.lower() for w in ("could not verify", "unavailable", "exhausted"))
    # Ensure no fabricated map features were returned
    assert len(state.final_answer.map_overlays) == 0
