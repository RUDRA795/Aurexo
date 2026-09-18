from __future__ import annotations

from orca.agents.pfz_pipeline import PFZDataSource, PFZSourceUnavailable
from orca.database.repositories.pfz_repository import PFZRepository
from orca.database.session import get_session_factory
from orca.schemas.orca_contract import AccessMethod, SourceMetadata, utc_now
from orca.schemas.pfz_contract import PFZAccessTier, PFZPoint, PFZQuery, PFZQueryResult


class CachedPFZAdapter(PFZDataSource):
    """Tier-3 fallback adapter querying verified unexpired points from PostgreSQL / PostGIS."""

    tier = PFZAccessTier.CACHED

    def __init__(self, session_factory=None):
        self._session_factory = session_factory or get_session_factory()

    @classmethod
    def get_source_metadata(cls) -> SourceMetadata:
        return SourceMetadata(
            source_id="incois_pfz_cached",
            organization="INCOIS",
            dataset="Cached Operational PostGIS Observations",
            domain=["pfz", "fisheries", "cache"],
            coverage="indian_coast",
            latency="historical",
            authority="official",
            access=AccessMethod.INTERNAL,
            freshness_policy_hours=36.0,
            fallbacks=[],
        )

    async def fetch(self, query: PFZQuery) -> PFZQueryResult:
        factory = self._session_factory
        async with factory() as session:
            repo = PFZRepository(session)
            results = await repo.query_nearest(
                origin=query.location,
                valid_at=query.valid_at,
                radius_km=query.radius_km,
                sector=query.sector,
                limit=50,
            )

        valid_points: list[PFZPoint] = []
        for r in results:
            pt: PFZPoint = r["point"]
            # Strict stale data check
            if pt.is_valid_at(query.valid_at):
                valid_points.append(pt)

        if not valid_points:
            raise PFZSourceUnavailable(
                f"No unexpired cached PFZ observations available for sector '{query.sector}' at {query.valid_at.isoformat()}."
            )

        return PFZQueryResult(
            points=valid_points,
            source=self.get_source_metadata(),
            access_tier=self.tier,
            retrieved_at=utc_now(),
            limitations=["Verified unexpired INCOIS observation retrieved from local PostGIS repository."],
        )
