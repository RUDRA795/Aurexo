from __future__ import annotations

import logging
from typing import Any

from orca.data.adapters.incois_chlorophyll import INCOISChlorophyllAdapter
from orca.data.adapters.incois_pfz import INCOISPFZWebGISAdapter
from orca.data.adapters.incois_sst import INCOISSSTAdapter
from orca.database.repositories.pfz_repository import PFZRepository
from orca.database.session import get_session_factory
from orca.schemas.orca_contract import Evidence, Geometry, utc_now
from orca.schemas.pfz_contract import PFZQuery

logger = logging.getLogger("orca.services.ingestion")


async def ingest_live_incois_pfz(sector: str | None = None) -> dict[str, Any]:
    """Operational task fetching live PFZ features from INCOIS WFS and saving to PostGIS."""
    adapter = INCOISPFZWebGISAdapter()
    query = PFZQuery(
        location=Geometry(lat=15.0, lon=73.0),
        valid_at=utc_now(),
        sector=sector,
        radius_km=2000.0,
    )
    result = await adapter.fetch(query)

    factory = get_session_factory()
    async with factory() as session:
        repo = PFZRepository(session)
        count = await repo.upsert_points(
            result.points,
            source_id=result.source.source_id,
            access_tier=result.access_tier.value,
        )

    return {
        "status": "success",
        "source": result.source.source_id,
        "access_tier": result.access_tier.value,
        "sector": sector,
        "points_ingested": count,
        "retrieved_at": result.retrieved_at.isoformat(),
    }


def sample_environmental_context(location: Geometry) -> list[Evidence]:
    """Sample SST and Chlorophyll-a evidence for a specific marine coordinate."""
    import os
    if not os.getenv("ORCA_ENABLE_LIVE_ENVIRONMENT", "").lower() in ("true", "1"):
        return []

    evidence_list: list[Evidence] = []

    # 1. SST
    try:
        sst_adapter = INCOISSSTAdapter()
        ev_sst = sst_adapter.extract_sst(location)
        evidence_list.append(ev_sst)
    except Exception as exc:
        logger.info("SST extraction unavailable at (%s, %s): %s", location.lat, location.lon, exc)

    # 2. Chlorophyll
    try:
        chl_adapter = INCOISChlorophyllAdapter()
        ev_chl = chl_adapter.extract_chlorophyll(location)
        evidence_list.append(ev_chl)
    except Exception as exc:
        logger.info("Chlorophyll extraction unavailable at (%s, %s): %s", location.lat, location.lon, exc)

    return evidence_list
