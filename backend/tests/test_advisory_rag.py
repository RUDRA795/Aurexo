from datetime import datetime, timedelta, timezone
import math
import uuid
import pytest
from sqlalchemy import text

from orca.agents.graph import create_orca_graph
from orca.agents.state import OrcaGraphState
from orca.database.repositories.advisory_rag import (
    AdvisoryRAGRepository,
    DeterministicMockEmbeddingProvider,
)
from orca.database.session import get_session_factory
from orca.schemas.orca_contract import AccessMethod, DataQuality, Geometry, ResponseType, utc_now
from orca.schemas.pfz_contract import PFZAccessTier, PFZPoint, PFZQuery, PFZQueryResult


class MockPFZSourceForRAG:
    def __init__(self, point: PFZPoint):
        self.point = point

    async def fetch(self, query: PFZQuery) -> PFZQueryResult:
        from orca.schemas.orca_contract import SourceMetadata
        return PFZQueryResult(
            points=[self.point],
            source=SourceMetadata(
                source_id="incois_wfs",
                organization="INCOIS",
                dataset="PFZ_WFS",
                authority="official",
                access=AccessMethod.API,
            ),
            access_tier=PFZAccessTier.WEBGIS_LAYER,
            retrieved_at=utc_now(),
        )


@pytest.fixture
async def rag_repo():
    factory = get_session_factory()
    async with factory() as session:
        # Clean up test table for full test isolation
        await session.execute(text("DELETE FROM marine_advisories"))
        await session.commit()

        repo = AdvisoryRAGRepository(session)
        yield repo

        # Teardown
        await session.execute(text("DELETE FROM marine_advisories"))
        await session.commit()



@pytest.mark.asyncio
async def test_pgvector_extension_availability(rag_repo):
    """Verify that the vector extension is installed and active in PostgreSQL."""
    result = await rag_repo.session.execute(
        text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'")
    )
    row = result.fetchone()
    assert row is not None
    assert row[0] == "vector"
    assert len(row[1]) > 0


@pytest.mark.asyncio
async def test_advisory_insertion_and_get_by_id(rag_repo):
    now = utc_now()
    doc = await rag_repo.index_advisory(
        title="Goa Sardine Aggregation Bulletin",
        content="Heavy concentration of oil sardines observed 12nm offshore Panaji.",
        source_id="test_rag_goa",
        published_at=now,
        sector="GOA",
        language="en",
        metadata={"target_species": "sardine", "landing_center": "Panaji"},
    )

    assert doc.id is not None
    assert doc.title == "Goa Sardine Aggregation Bulletin"
    assert doc.sector == "GOA"
    assert doc.language == "en"
    assert doc.embedding is not None
    assert len(doc.embedding) == 1536

    fetched = await rag_repo.get_by_id(doc.id)
    assert fetched is not None
    assert fetched.id == doc.id
    assert fetched.content == doc.content
    assert fetched.metadata.get("target_species") == "sardine"


@pytest.mark.asyncio
async def test_embedding_dimension_validation(rag_repo):
    # Short vector (10 elements instead of 1536)
    with pytest.raises(ValueError, match="Embedding dimension mismatch"):
        await rag_repo.index_advisory(
            title="Invalid Vector Test",
            content="Some text content",
            source_id="test_rag_err",
            embedding=[0.1] * 10,
        )

    # Search with invalid vector dimension
    with pytest.raises(ValueError, match="Embedding dimension mismatch"):
        await rag_repo.search_advisories(query_embedding=[0.5] * 500)


@pytest.mark.asyncio
async def test_semantic_top_k_retrieval(rag_repo):
    now = utc_now()
    # Insert 3 advisories
    doc1 = await rag_repo.index_advisory(
        title="Mackerel Schooling off Malpe",
        content="Pelagic mackerel aggregation noted near Malpe fishing harbor.",
        source_id="test_rag_karnataka",
        published_at=now,
        sector="KARNATAKA",
    )
    doc2 = await rag_repo.index_advisory(
        title="Cyclone Warning Bay of Bengal",
        content="Deep depression formed over central Bay of Bengal. Squally winds expected.",
        source_id="test_rag_cyclone",
        published_at=now,
        sector="ANDHRA PRADESH",
    )
    doc3 = await rag_repo.index_advisory(
        title="Karnataka Coastal Weather",
        content="Moderate sea conditions with light rain off Mangalore.",
        source_id="test_rag_karnataka",
        published_at=now,
        sector="KARNATAKA",
    )

    # Search for mackerel
    results = await rag_repo.search_advisories(query_text="mackerel fishing near Malpe", limit=2)
    assert len(results) >= 1
    top = results[0]
    assert top.document.id == doc1.id
    assert top.similarity_score > 0.0
    assert top.cosine_distance < 1.0
    assert top.evidence.variable == "advisory_context"
    assert top.evidence.source.source_id == "test_rag_karnataka"


@pytest.mark.asyncio
async def test_deterministic_tie_ordering(rag_repo):
    now = utc_now()
    # Create identical embedding for two documents
    identical_vec = [0.0] * 1536
    identical_vec[0] = 1.0

    id_a = uuid.UUID("00000000-0000-0000-0000-000000000001")
    id_b = uuid.UUID("00000000-0000-0000-0000-000000000002")

    await rag_repo.index_advisory(
        advisory_id=id_b,
        title="Advisory B",
        content="Duplicate content B",
        source_id="test_rag_tie",
        published_at=now,
        embedding=identical_vec,
    )
    await rag_repo.index_advisory(
        advisory_id=id_a,
        title="Advisory A",
        content="Duplicate content A",
        source_id="test_rag_tie",
        published_at=now,
        embedding=identical_vec,
    )

    # Query with identical vector
    results = await rag_repo.search_advisories(query_embedding=identical_vec, limit=2)
    assert len(results) == 2
    # Tie-breaker MarineAdvisoryModel.id.asc() ensures id_a comes before id_b
    assert results[0].document.id == id_a
    assert results[1].document.id == id_b


@pytest.mark.asyncio
async def test_metadata_filtering_by_sector(rag_repo):
    now = utc_now()
    await rag_repo.index_advisory(
        title="Kerala Pelagic Notice",
        content="Yellowfin tuna aggregation 20nm west of Kochi.",
        source_id="test_rag_filter",
        published_at=now,
        sector="KERALA",
    )
    await rag_repo.index_advisory(
        title="Goa Trawl Notice",
        content="Squid aggregation near Aguada reef.",
        source_id="test_rag_filter",
        published_at=now,
        sector="GOA",
    )

    kerala_results = await rag_repo.search_advisories(
        query_text="marine pelagic aggregation",
        sector="KERALA",
    )
    assert all(r.document.sector == "KERALA" for r in kerala_results)
    assert any("Kochi" in r.document.content for r in kerala_results)


@pytest.mark.asyncio
async def test_multilingual_language_filtering(rag_repo):
    now = utc_now()
    await rag_repo.index_advisory(
        title="Kerala English Bulletin",
        content="Good fishing potential for sardine and anchovy.",
        source_id="test_rag_lang",
        published_at=now,
        sector="KERALA",
        language="en",
    )
    await rag_repo.index_advisory(
        title="Kerala Malayalam Bulletin",
        content="കൊച്ചി തീരത്ത് ചാള, നത്തോലി എന്നിവയുടെ ലഭ്യത.",
        source_id="test_rag_lang",
        published_at=now,
        sector="KERALA",
        language="ml",
    )

    ml_results = await rag_repo.search_advisories(
        query_text="ചാള ലഭ്യത",
        language="ml",
    )
    assert len(ml_results) >= 1
    assert all(r.document.language == "ml" for r in ml_results)


@pytest.mark.asyncio
async def test_freshness_filtering(rag_repo):
    now = utc_now()
    old_time = now - timedelta(days=7)

    await rag_repo.index_advisory(
        title="Old Expired Advisory",
        content="Old fishery aggregation from last week.",
        source_id="test_rag_freshness",
        published_at=old_time,
        sector="GOA",
    )
    await rag_repo.index_advisory(
        title="Fresh Advisory",
        content="Current fishery aggregation from today.",
        source_id="test_rag_freshness",
        published_at=now,
        sector="GOA",
    )

    # Filter for advisories published within the last 24 hours
    fresh_cutoff = now - timedelta(hours=24)
    fresh_results = await rag_repo.search_advisories(
        query_text="fishery aggregation",
        sector="GOA",
        min_published_at=fresh_cutoff,
    )

    assert len(fresh_results) == 1
    assert fresh_results[0].document.title == "Fresh Advisory"


@pytest.mark.asyncio
async def test_empty_result_behavior(rag_repo):
    results = await rag_repo.search_advisories(
        query_text="Arctic cod migration",
        sector="NON_EXISTENT_SECTOR",
    )
    assert results == []


@pytest.mark.asyncio
async def test_provenance_preservation(rag_repo):
    now = utc_now()
    doc = await rag_repo.index_advisory(
        title="Provenanced Advisory Test",
        content="Advisory content for provenance check.",
        source_id="test_rag_provenance_src",
        published_at=now,
        sector="MAHARASHTRA",
    )

    results = await rag_repo.search_advisories(query_text="provenance check", limit=1)
    assert len(results) >= 1
    ev = results[0].evidence

    assert ev.source.source_id == "test_rag_provenance_src"
    assert ev.source.authority == "official"
    assert ev.variable == "advisory_context"
    assert ev.observed_at == doc.published_at
    assert (utc_now() - ev.retrieved_at).total_seconds() < 5.0
    assert ev.quality == DataQuality.GOOD
    assert "pgvector" in ev.method


@pytest.mark.asyncio
async def test_langgraph_integration_with_advisory_rag(rag_repo):
    now = utc_now()
    await rag_repo.index_advisory(
        title="Goa Coastal Sardine Alert",
        content="High concentration of sardines observed within 15km of Panaji port.",
        source_id="test_rag_graph",
        published_at=now,
        sector="GOA",
    )

    pfz_point = PFZPoint(
        pfz_id="pfz_rag_001",
        location=Geometry(lat=15.48, lon=73.75),
        sector="GOA",
        depth_m=35.0,
        source_valid_from=now,
        freshness_deadline=now + timedelta(hours=24),
    )

    graph = create_orca_graph(
        pfz_sources=[MockPFZSourceForRAG(pfz_point)],
        advisory_rag_repo=rag_repo,
    )

    state: OrcaGraphState = {
        "user_query": "Where are sardines aggregating off Goa coast?",
        "coordinates": Geometry(lat=15.45, lon=73.70),
    }

    result = await graph.ainvoke(state)
    ans = result["final_answer"]

    assert ans.response_type == ResponseType.FACTUAL
    # Verify contextual RAG distinction in synthesis
    assert "Contextual Advisory (Goa Coastal Sardine Alert):" in ans.answer_text
    assert "High concentration of sardines" in ans.answer_text

    # Verify RAG evidence is in evidence_summary
    rag_ev = next((e for e in ans.evidence_summary if e.variable == "advisory_context"), None)
    assert rag_ev is not None
    assert rag_ev.source.source_id == "test_rag_graph"
