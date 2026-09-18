from __future__ import annotations

import logging
from typing import Sequence

from orca.agents.pfz_pipeline import PFZDataSource, PFZSourceUnavailable
from orca.data.adapters.cached_pfz import CachedPFZAdapter
from orca.data.adapters.incois_pfz import INCOISPFZWebGISAdapter
from orca.data.adapters.incois_text_advisory import INCOISTextAdvisoryAdapter
from orca.database.repositories.pfz_repository import PFZRepository
from orca.database.session import get_session_factory
from orca.schemas.pfz_contract import PFZAccessTier, PFZQuery, PFZQueryResult

logger = logging.getLogger("orca.data.registry")


class TieredPFZProvider(PFZDataSource):
    """Production provider managing tiered failover:
    WebGIS -> Text Advisory -> Cached -> Unavailable.
    """

    tier = PFZAccessTier.STRUCTURED_SPATIAL

    def __init__(
        self,
        sources: Sequence[PFZDataSource] | None = None,
        *,
        auto_cache: bool = True,
        session_factory=None,
    ):
        self._session_factory = session_factory or get_session_factory()
        self.auto_cache = auto_cache
        if sources is not None:
            self.sources = list(sources)
        else:
            self.sources = [
                INCOISPFZWebGISAdapter(),
                INCOISTextAdvisoryAdapter(),
                CachedPFZAdapter(session_factory=self._session_factory),
            ]

    async def fetch(self, query: PFZQuery) -> PFZQueryResult:
        errors: list[str] = []

        for source in self.sources:
            tier_name = source.tier.value if hasattr(source, "tier") else type(source).__name__
            try:
                result = await source.fetch(query)
                # Verify non-empty and valid points
                if result.points:
                    # Auto-persist fresh live data to local PostGIS repository for cache resilience
                    if self.auto_cache and source.tier in (PFZAccessTier.WEBGIS_LAYER, PFZAccessTier.TEXT_ADVISORY):
                        await self._persist_points(result)
                    return result
                else:
                    errors.append(f"{tier_name}: 0 points matched query")
            except PFZSourceUnavailable as exc:
                logger.info("PFZ tier %s unavailable: %s", tier_name, exc)
                errors.append(f"{tier_name}: {exc}")
            except Exception as exc:
                logger.warning("PFZ tier %s unexpected failure: %s", tier_name, exc)
                errors.append(f"{tier_name}: {exc}")

        raise PFZSourceUnavailable("All PFZ source tiers exhausted: " + " | ".join(errors))

    async def _persist_points(self, result: PFZQueryResult) -> None:
        """Asynchronously cache newly retrieved live points to PostGIS."""
        try:
            async with self._session_factory() as session:
                repo = PFZRepository(session)
                await repo.upsert_points(
                    result.points,
                    source_id=result.source.source_id,
                    access_tier=result.access_tier.value,
                )
        except Exception as exc:
            # Failure to cache does not destroy immediate query response
            logger.error("Failed to auto-cache live PFZ points to database: %s", exc)
