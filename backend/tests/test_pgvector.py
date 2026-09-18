import pytest
from sqlalchemy import text

from orca.database.repositories.advisory_repository import AdvisoryRepository
from orca.database.session import get_session_factory
from orca.schemas.orca_contract import utc_now


def _make_vector(primary_dim: int, dims: int = 1536) -> list[float]:
    v = [0.0] * dims
    v[primary_dim] = 1.0
    return v


@pytest.mark.asyncio
async def test_pgvector_advisory_similarity_search():
    factory = get_session_factory()
    now = utc_now()

    async with factory() as session:
        # Clean up any leftover test data from previous runs
        await session.execute(
            text("DELETE FROM marine_advisories WHERE source_id = :src"),
            {"src": "test_incois_vector"},
        )
        await session.commit()

        repo = AdvisoryRepository(session)

        # 1. Create vectors: dim 0, dim 1, and dim 2
        vec0 = _make_vector(0)
        vec1 = _make_vector(1)
        vec2 = _make_vector(2)

        adv1 = await repo.create_advisory(
            title="Goa Coastal Fishery Advisory - Sardines",
            content="Heavy pelagic fish aggregation observed off Panaji coast.",
            source_id="test_incois_vector",
            published_at=now,
            sector="GOA",
            embedding=vec0,
            metadata_json={"advisory_type": "pfz_bulletin"},
        )

        adv2 = await repo.create_advisory(
            title="Goa Shallow Trawling Notice",
            content="Notice regarding seasonal trawl restrictions off Mormugao.",
            source_id="test_incois_vector",
            published_at=now,
            sector="GOA",
            embedding=vec1,
            metadata_json={"advisory_type": "restriction"},
        )

        adv3 = await repo.create_advisory(
            title="Gujarat Pelagic Forecast",
            content="Tuna schools reported 40 nautical miles off Veraval.",
            source_id="test_incois_vector",
            published_at=now,
            sector="GUJARAT",
            embedding=vec2,
            metadata_json={"advisory_type": "pfz_bulletin"},
        )

        assert adv1.id is not None
        assert adv2.id is not None
        assert adv3.id is not None

        # 2. Query with vec0 (should match adv1 perfectly, cosine distance ~ 0)
        results = await repo.search_similar(embedding=vec0, limit=3)
        assert len(results) >= 1
        top_advisory, top_distance = results[0]
        assert top_advisory.id == adv1.id
        assert abs(top_distance) < 1e-5

        # 3. Query with sector filter
        gujarat_results = await repo.search_similar(embedding=vec0, limit=3, sector="GUJARAT")
        assert all(r[0].sector == "GUJARAT" for r in gujarat_results)
        assert gujarat_results[0][0].id == adv3.id
