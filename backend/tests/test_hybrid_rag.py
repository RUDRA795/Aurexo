from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import uuid
import pytest
from sqlalchemy import text

from orca.agents.graph import create_orca_graph
from orca.agents.runtime import IntentEnum, OrcaAgentRuntime
from orca.agents.state import OrcaGraphState
from orca.database.models.advisory import MarineAdvisoryChunkModel, MarineAdvisoryModel
from orca.database.repositories.advisory_rag import (
    AdvisoryDocument,
    AdvisoryRAGRepository,
    AdvisorySearchResult,
    ChunkSearchResult,
)
from orca.database.session import get_session_factory
from orca.embeddings.base import (
    EmbeddingDimensionMismatchError,
    EmbeddingProviderUnavailableError,
)
from orca.embeddings.bge_m3 import BgeM3EmbeddingProvider
from orca.embeddings.mock import DeterministicMockEmbeddingProvider
from orca.rag.chunking import DeterministicAdvisoryChunker
from orca.rag.reranker import NoOpReranker
from orca.schemas.orca_contract import (
    AccessMethod,
    DataQuality,
    Evidence,
    EvidenceType,
    Geometry,
    ResponseType,
    SourceMetadata,
    utc_now,
)
from orca.schemas.pfz_contract import PFZAccessTier, PFZPoint, PFZQuery, PFZQueryResult


@pytest.fixture
async def db_session():
    factory = get_session_factory()
    async with factory() as session:
        # Clean both chunks and parent advisories for full test isolation
        await session.execute(text("DELETE FROM marine_advisory_chunks"))
        await session.execute(text("DELETE FROM marine_advisories"))
        await session.commit()

        yield session

        await session.execute(text("DELETE FROM marine_advisory_chunks"))
        await session.execute(text("DELETE FROM marine_advisories"))
        await session.commit()


@pytest.fixture
def hybrid_repo_1536(db_session):
    return AdvisoryRAGRepository(
        db_session,
        embedding_provider=DeterministicMockEmbeddingProvider(dimension=1536),
        dimension=1536,
    )


@pytest.fixture
def hybrid_repo_1024(db_session):
    return AdvisoryRAGRepository(
        db_session,
        embedding_provider=DeterministicMockEmbeddingProvider(dimension=1024),
        dimension=1024,
    )


# ===========================================================================
# 1. EMBEDDING SUBSYSTEM TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_deterministic_mock_provider_contracts():
    p1536 = DeterministicMockEmbeddingProvider(1536)
    p1024 = DeterministicMockEmbeddingProvider(1024)

    assert p1536.dimension == 1536
    assert p1536.is_available is True
    assert "mock" in p1536.model_name

    assert p1024.dimension == 1024
    assert p1024.is_available is True

    # Determinism check
    v1 = await p1536.embed_text("Marine advisory test")
    v2 = await p1536.embed_text("Marine advisory test")
    assert v1 == v2
    assert len(v1) == 1536

    # L2-normalization check (length should be ~1.0)
    norm = math.sqrt(sum(x * x for x in v1))
    assert abs(norm - 1.0) < 1e-4

    # Batch embedding check
    batch_vecs = await p1024.embed_batch(["text one", "text two"])
    assert len(batch_vecs) == 2
    assert len(batch_vecs[0]) == 1024
    assert len(batch_vecs[1]) == 1024
    assert batch_vecs[0] != batch_vecs[1]


@pytest.mark.asyncio
async def test_bge_m3_provider_strict_unavailable_rule():
    """Verify non-negotiable rule: BGE-M3 must report explicit UNAVAILABLE when weights/libs absent."""
    provider = BgeM3EmbeddingProvider()

    assert provider.dimension == 1024
    assert provider.model_name == "BAAI/bge-m3"
    assert provider.version == "v1.0"

    # In standard CI without GPU / sentence_transformers weights, is_available must be False
    # and embed_text MUST raise EmbeddingProviderUnavailableError (never silently fall back to mock).
    if not provider.is_available:
        with pytest.raises(EmbeddingProviderUnavailableError, match="BGE-M3 model"):
            await provider.embed_text("Sample query")
        with pytest.raises(EmbeddingProviderUnavailableError, match="BGE-M3 model"):
            await provider.embed_batch(["Batch query"])


# ===========================================================================
# 2. DETERMINISTIC CHUNKING TESTS
# ===========================================================================

def test_deterministic_chunking_invariants():
    chunker = DeterministicAdvisoryChunker(target_window=25, overlap=5)
    adv_id = uuid.UUID("11111111-2222-3333-4444-555555555555")

    text_content = (
        "Advisory Section 1: Strong winds of 45 knots expected off Ratnagiri.\n\n"
        "Advisory Section 2: Fishermen are advised not to venture into deep sea areas off South Maharashtra.\n\n"
        "Advisory Section 3: Safe landing centers identified at Sassoon Dock and Mirkarwada."
    )

    chunks1 = chunker.chunk_advisory(adv_id, "Maharashtra Storm Warning", text_content, sector="MAHARASHTRA")
    chunks2 = chunker.chunk_advisory(adv_id, "Maharashtra Storm Warning", text_content, sector="MAHARASHTRA")

    assert len(chunks1) >= 2
    # Invariant: identical inputs produce identical chunks and IDs
    assert [c.chunk_id for c in chunks1] == [c.chunk_id for c in chunks2]
    assert [c.content for c in chunks1] == [c.content for c in chunks2]
    assert chunks1[0].chunk_id == f"{adv_id}_chunk_0"
    assert chunks1[1].chunk_id == f"{adv_id}_chunk_1"
    assert chunks1[0].sector == "MAHARASHTRA"
    assert chunks1[0].title == "Maharashtra Storm Warning"
    assert chunks1[0].segmentation_method == "unicode_word_segmentation"
    assert chunks1[0].unit_count > 0


# ===========================================================================
# 3. DATABASE ADDITIVE SCHEMA & CASCADE TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_database_schema_and_cascade_deletion(hybrid_repo_1024):
    session = hybrid_repo_1024.session
    now = utc_now()

    doc = await hybrid_repo_1024.index_advisory(
        title="Goa Port Operations Advisory",
        content="Vessel movements restricted at Mormugao Port due to swell. Malim harbor open for small crafts.",
        source_id="test_incois_goa",
        sector="GOA",
        published_at=now,
    )

    assert doc.id is not None
    assert doc.production_embedding is not None
    assert len(doc.production_embedding) == 1024

    # Verify chunks were created
    chunks = await hybrid_repo_1024.get_chunks_for_advisory(doc.id)
    assert len(chunks) >= 1
    assert chunks[0].advisory_id == doc.id
    assert chunks[0].title == "Goa Port Operations Advisory"

    # Verify database search_vector generated column exists on chunk
    res = await session.execute(
        text("SELECT search_vector IS NOT NULL FROM marine_advisory_chunks WHERE advisory_id = :aid"),
        {"aid": doc.id},
    )
    sv_populated = res.scalars().all()
    assert all(sv_populated)

    # Test ON DELETE CASCADE from parent to child chunks
    deleted = await hybrid_repo_1024.delete_by_id(doc.id)
    assert deleted is True

    # Verify child chunks are automatically removed by cascade
    chunks_after = await hybrid_repo_1024.get_chunks_for_advisory(doc.id)
    assert len(chunks_after) == 0


# ===========================================================================
# 4. LEXICAL RETRIEVAL TESTS (PostgreSQL FTS + ts_rank_cd)
# ===========================================================================

@pytest.mark.asyncio
async def test_lexical_retrieval_exact_place_names_and_weighting(hybrid_repo_1024):
    now = utc_now()

    # Document 1: Sassoon Dock in Title (Weight 'A')
    await hybrid_repo_1024.index_advisory(
        title="Sassoon Dock Pelagic Landing Bulletin",
        content="Heavy landings of mackerel and sardine recorded by trawlers.",
        source_id="test_incois_mumbai",
        sector="MAHARASHTRA",
        published_at=now,
    )

    # Document 2: Sassoon Dock only in Content (Weight 'B')
    await hybrid_repo_1024.index_advisory(
        title="Maharashtra Marine Context Summary",
        content="Trawlers from Sassoon Dock reported calm waters 15 nautical miles offshore.",
        source_id="test_incois_mumbai",
        sector="MAHARASHTRA",
        published_at=now - timedelta(hours=1),
    )

    # Document 3: Different harbor (Malim, Goa)
    await hybrid_repo_1024.index_advisory(
        title="Goa Fisheries Bulletin: Malim Jetty",
        content="Good catch of ribbonfish near Malim jetty.",
        source_id="test_incois_goa",
        sector="GOA",
        published_at=now,
    )

    # Search for "Sassoon Dock"
    lex_results = await hybrid_repo_1024.search_lexical("Sassoon Dock", limit=5)
    assert len(lex_results) == 2

    top_chunk, top_score = lex_results[0]
    second_chunk, second_score = lex_results[1]

    # Title match (Weight A) must outrank content-only match (Weight B)
    assert "Sassoon Dock" in top_chunk.title
    assert top_score > second_score


# ===========================================================================
# 5. DENSE RETRIEVAL & HYBRID RRF TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_dense_semantic_and_hybrid_rrf_fusion(hybrid_repo_1024):
    now = utc_now()

    # Doc A: Exact lexical match for rare keyword "Veraval"
    doc_a = await hybrid_repo_1024.index_advisory(
        title="Gujarat Coastal Alert: Veraval Harbor",
        content="Squally weather warning issued specifically for Veraval fishing harbor.",
        source_id="test_incois_gujarat",
        sector="GUJARAT",
        published_at=now,
    )

    # Doc B: Semantic description of rough sea state without mentioning Veraval
    doc_b = await hybrid_repo_1024.index_advisory(
        title="Saurashtra Coast Marine Forecast",
        content="High wave alerts and severe ocean turbulence along the western peninsula.",
        source_id="test_incois_gujarat",
        sector="GUJARAT",
        published_at=now,
    )

    # 1. Lexical-only query finds Doc A
    lex_results = await hybrid_repo_1024.search_lexical("Veraval harbor", limit=2)
    assert len(lex_results) >= 1
    assert lex_results[0][0].advisory_id == doc_a.id

    # 2. Hybrid search fuses dense and lexical with RRF
    hybrid_results = await hybrid_repo_1024.search_advisories(
        query_text="Veraval squally weather",
        sector="GUJARAT",
        limit=2,
    )
    assert len(hybrid_results) >= 1
    top = hybrid_results[0]
    assert top.document.id == doc_a.id
    assert top.rrf_score is not None
    assert top.rrf_score > 0.0
    assert top.evidence.evidence_type == EvidenceType.ADVISORY
    assert top.evidence.variable == "advisory_context"
    assert "hybrid_rrf" in top.evidence.method


@pytest.mark.asyncio
async def test_deterministic_rrf_tie_breaking(hybrid_repo_1024):
    now = utc_now()
    id_1 = uuid.UUID("00000000-0000-0000-0000-000000000001")
    id_2 = uuid.UUID("00000000-0000-0000-0000-000000000002")

    # Insert two identical advisories with same timestamps
    await hybrid_repo_1024.index_advisory(
        advisory_id=id_2,
        title="Identical Advisory",
        content="Identical content for tie breaking verification.",
        published_at=now,
    )
    await hybrid_repo_1024.index_advisory(
        advisory_id=id_1,
        title="Identical Advisory",
        content="Identical content for tie breaking verification.",
        published_at=now,
    )

    results = await hybrid_repo_1024.search_advisories(
        query_text="Identical Advisory",
        limit=2,
    )
    assert len(results) == 2
    # Deterministic tie-breaker: id_1 comes before id_2
    assert results[0].document.id == id_1
    assert results[1].document.id == id_2


# ===========================================================================
# 6. HNSW FILTERED RECALL QUANTITATIVE BENCHMARK
# ===========================================================================

@pytest.mark.asyncio
async def test_hnsw_filtered_recall_benchmark(hybrid_repo_1024):
    """Evaluate HNSW approximate scan against brute-force baseline to measure Recall@K.

    Tests that filtered HNSW meets retrieval thresholds and evaluates iterative_scan setting.
    """
    session = hybrid_repo_1024.session
    now = utc_now()

    # Index 15 synthetic advisories across two sectors
    for i in range(15):
        sec = "MAHARASHTRA" if i % 2 == 0 else "TAMIL NADU"
        await hybrid_repo_1024.index_advisory(
            title=f"Ocean Bulletin {i}",
            content=f"Marine fisheries status number {i} for sector {sec} with operational wave guidance.",
            sector=sec,
            published_at=now - timedelta(hours=i),
        )

    # Brute-force baseline: exact calculation over filtered set
    q_vec = await hybrid_repo_1024.embedding_provider.embed_text("operational wave guidance")
    target_k = 3

    # Exact ground truth using brute force distance calculation
    res_exact = await session.execute(
        text("""
            SELECT id, advisory_id, (production_embedding <-> :q_vec) AS dist
            FROM marine_advisory_chunks
            WHERE sector = 'MAHARASHTRA'
            ORDER BY dist ASC, published_at DESC, advisory_id ASC
            LIMIT :k
        """),
        {"q_vec": str(q_vec), "k": target_k},
    )
    exact_ground_truth_ids = [row[0] for row in res_exact.fetchall()]

    # Filtered HNSW retrieval using default iterative_scan
    hnsw_results_default = await hybrid_repo_1024.search_dense(
        query_embedding=q_vec,
        limit=target_k,
        sector="MAHARASHTRA",
        hnsw_iterative_scan="off",
    )
    hnsw_ids_default = [chunk.id for chunk, _ in hnsw_results_default]

    # Filtered HNSW retrieval using strict_order iterative scan
    hnsw_results_iterative = await hybrid_repo_1024.search_dense(
        query_embedding=q_vec,
        limit=target_k,
        sector="MAHARASHTRA",
        hnsw_iterative_scan="strict_order",
    )
    hnsw_ids_iterative = [chunk.id for chunk, _ in hnsw_results_iterative]

    # Calculate Recall@K
    recall_default = len(set(exact_ground_truth_ids).intersection(set(hnsw_ids_default))) / float(target_k)
    recall_iterative = len(set(exact_ground_truth_ids).intersection(set(hnsw_ids_iterative))) / float(target_k)

    print(f"\n[HNSW FILTERED RECALL BENCHMARK]")
    print(f"  Exact Ground Truth IDs: {exact_ground_truth_ids}")
    print(f"  HNSW Default IDs:       {hnsw_ids_default} (Recall@{target_k}: {recall_default:.2f})")
    print(f"  HNSW Iterative IDs:     {hnsw_ids_iterative} (Recall@{target_k}: {recall_iterative:.2f})")

    assert recall_default >= 0.66, f"HNSW default filtered recall ({recall_default}) below acceptable threshold"
    assert recall_iterative >= recall_default, "HNSW iterative scan should equal or exceed default recall"


# ===========================================================================
# 7. MULTILINGUAL RETRIEVAL TESTS (Indic Languages)
# ===========================================================================

@pytest.mark.asyncio
async def test_multilingual_indic_advisories(hybrid_repo_1024):
    now = utc_now()

    # Hindi
    await hybrid_repo_1024.index_advisory(
        title="महाराष्ट्र मछुआरा चेतावनी",
        content="मुंबई और रायगढ़ तट पर 45 किमी प्रति घंटे की तेज हवाएं चलने की संभावना है।",
        sector="MAHARASHTRA",
        language="hi",
        published_at=now,
    )

    # Malayalam
    await hybrid_repo_1024.index_advisory(
        title="കേരള തീരദേശ മുന്നറിയിപ്പ്",
        content="കൊച്ചി തീരത്ത് ഉയർന്ന തിരമാലകൾക്കും ശക്തമായ കാറ്റിനും സാധ്യത.",
        sector="KERALA",
        language="ml",
        published_at=now,
    )

    # Tamil
    await hybrid_repo_1024.index_advisory(
        title="தமிழ்நாடு மீனவர் எச்சரிக்கை",
        content="சென்னைக் கடற்பகுதியில் பலத்த காற்று வீசக்கூடும்.",
        sector="TAMIL NADU",
        language="ta",
        published_at=now,
    )

    # Kannada
    await hybrid_repo_1024.index_advisory(
        title="ಕರ್ನಾಟಕ ಕರಾವಳಿ ಎಚ್ಚರಿಕೆ",
        content="ಮಂಗಳೂರು ಬಂದರಿನ ಬಳಿ ಮೀನುಗಾರರು ಸಮುದ್ರಕ್ಕೆ ಇಳಿಯದಂತೆ ಸೂಚನೆ.",
        sector="KARNATAKA",
        language="kn",
        published_at=now,
    )

    # Telugu
    await hybrid_repo_1024.index_advisory(
        title="విశాఖపట్నం సముద్ర హెచ్చరిక",
        content="తీరం వెంబడి బలమైన గాలులు వీచే అవకాశం ఉంది.",
        sector="ANDHRA PRADESH",
        language="te",
        published_at=now,
    )

    # Search in Hindi
    hi_res = await hybrid_repo_1024.search_advisories(query_text="मछुआरा चेतावनी मुंबई", language="hi", limit=1)
    assert len(hi_res) == 1
    assert hi_res[0].document.language == "hi"
    assert "महाराष्ट्र" in hi_res[0].document.title

    # Search in Malayalam
    ml_res = await hybrid_repo_1024.search_advisories(query_text="തീരദേശ മുന്നറിയിപ്പ് കൊച്ചി", language="ml", limit=1)
    assert len(ml_res) == 1
    assert ml_res[0].document.language == "ml"
    assert "കേരള" in ml_res[0].document.title


# ===========================================================================
# 8. RUNTIME & SUFFICIENCY NON-SUBSTITUTION REGRESSION TESTS
# ===========================================================================

@pytest.mark.asyncio
async def test_advisory_evidence_cannot_substitute_for_physical_observations():
    """Verify non-negotiable rule: Advisory evidence must NEVER satisfy mandatory physical requirements."""
    runtime = OrcaAgentRuntime()

    # Create typed Evidence of EvidenceType.ADVISORY
    advisory_evidence = Evidence(
        source=SourceMetadata(
            source_id="incois_advisory",
            organization="INCOIS",
            dataset="Advisory Bulletin",
            domain=["fisheries_advisory"],
            coverage="maharashtra",
            authority="official",
            access=AccessMethod.API,
        ),
        variable="advisory_context",
        value={
            "advisory_id": str(uuid.uuid4()),
            "title": "Maharashtra Gale Warning",
            "content": "Wind speed 40 knots, wave height 3.5m observed near Mumbai.",
        },
        evidence_type=EvidenceType.ADVISORY,
        observed_at=utc_now(),
        retrieved_at=utc_now(),
        quality=DataQuality.GOOD,
        method="hybrid_rrf_pgvector",
    )

    # Evaluate sufficiency for FISHING_SUITABILITY (which strictly requires physical SST, Chlorophyll, Weather)
    eval_result = runtime.evaluate_evidence_sufficiency(
        intent=IntentEnum.FISHING_SUITABILITY,
        evidence_list=[advisory_evidence],
    )

    # Invariant: Advisory text mentioning weather cannot substitute for physical observation instruments
    assert eval_result.is_sufficient is False
    assert "marine_operational_conditions" in eval_result.missing_mandatory
    assert "sea_surface_temperature" in eval_result.missing_mandatory
    assert "chlorophyll_a" in eval_result.missing_mandatory
    assert eval_result.answer_confidence < 0.5


# ===========================================================================
# 9. RETRIEVAL BENCHMARK SUITE (Recall@K, MRR, Hybrid Recovery)
# ===========================================================================

@pytest.mark.asyncio
async def test_comprehensive_retrieval_benchmark(hybrid_repo_1024):
    """Run comprehensive benchmark measuring Recall@K, MRR, and hybrid-only recovery."""
    now = utc_now()

    # Benchmark corpus
    corpus = [
        ("fishermen warning Maharashtra", "High squall warning along Ratnagiri and Mumbai coast.", "MAHARASHTRA", "en"),
        ("Sassoon Dock advisory", "Deep sea trawling vessels returning to Sassoon Dock harbor.", "MAHARASHTRA", "en"),
        ("PFZ Mumbai guidance", "High pelagic fish aggregation 25km offshore Mumbai.", "MAHARASHTRA", "en"),
        ("Arabian Sea fishing advisory", "North Arabian Sea advisory on tuna longlining conditions.", "ARABIAN SEA", "en"),
        ("Recent Maharashtra advisory", "Updated fishing zones and coastal security advisories for Maharashtra.", "MAHARASHTRA", "en"),
        ("महाराष्ट्र मछुआरा चेतावनी", "मुंबई समुद्र तट पर चक्रवाती हवाएं।", "MAHARASHTRA", "hi"),
        ("കേരള തീരദേശ മുന്നറിയിപ്പ്", "കൊച്ചി തീരത്ത് മത്സ്യത്തൊഴിലാളികൾക്കുള്ള ജാഗ്രതാ നിർദ്ദേശം.", "KERALA", "ml"),
        ("ಕರ್ನಾಟಕ ಕರಾವಳಿ ಎಚ್ಚರಿಕೆ", "ಮಲ್ಪೆ ಮತ್ತು ಮಂಗಳೂರು ಕರಾವಳಿಯಲ್ಲಿ ಭಾರಿ ಮಳೆ ಮುನ್ಸೂಚನೆ.", "KARNATAKA", "kn"),
        ("தமிழ்நாடு மீனவர் எச்சரிக்கை", "ராமேஸ்வரம் கடல் பகுதியில் பலத்த காற்று.", "TAMIL NADU", "ta"),
        ("విశాఖపట్నం సముద్ర హెచ్చరిక", "మత్స్యకారులు సముద్రంలోకి వెళ్లరాదని హెచ్చరిక.", "ANDHRA PRADESH", "te"),
    ]

    doc_ids = {}
    for title, content, sec, lang in corpus:
        doc = await hybrid_repo_1024.index_advisory(
            title=title,
            content=content,
            sector=sec,
            language=lang,
            published_at=now,
        )
        doc_ids[title] = doc.id

    # Benchmark test queries with expected relevant document title
    queries = [
        ("fishermen warning Maharashtra", "fishermen warning Maharashtra"),
        ("Sassoon Dock harbor advisory", "Sassoon Dock advisory"),
        ("PFZ pelagic aggregation Mumbai", "PFZ Mumbai guidance"),
        ("Arabian Sea tuna guidance", "Arabian Sea fishing advisory"),
        ("Maharashtra fishermen advisory", "Recent Maharashtra advisory"),
        ("मुंबई मछुआरा चेतावनी", "महाराष्ट्र मछुआरा चेतावनी"),
        ("കൊച്ചി തീരദേശ മുന്നറിയിപ്പ്", "കേരള തീരദേശ മുന്നറിയിപ്പ്"),
        ("ಮಂಗಳೂರು ಕರಾವಳಿ ಎಚ್ಚರಿಕೆ", "ಕರ್ನಾಟಕ ಕರಾವಳಿ ಎಚ್ಚರಿಕೆ"),
        ("ராமேஸ்வரம் மீனவர் எச்சரிக்கை", "தமிழ்நாடு மீனவர் எச்சரிக்கை"),
        ("విశాఖపట్నం హెచ్చరిక", "విశాఖపట్నం సముద్ర హెచ్చరిక"),
    ]

    k = 3
    recall_hits = 0
    reciprocal_ranks = []
    hybrid_only_recoveries = 0

    for q_text, expected_title in queries:
        target_id = doc_ids[expected_title]
        results = await hybrid_repo_1024.search_advisories(query_text=q_text, limit=k)
        retrieved_ids = [r.document.id for r in results]

        # Check hit in top-k
        if target_id in retrieved_ids:
            recall_hits += 1
            rank = retrieved_ids.index(target_id) + 1
            reciprocal_ranks.append(1.0 / rank)
        else:
            reciprocal_ranks.append(0.0)

        # Check hybrid-only recovery: retrieved by hybrid RRF
        top_match = results[0] if results else None
        if top_match and top_match.document.id == target_id:
            hybrid_only_recoveries += 1

    total_queries = len(queries)
    recall_at_k = recall_hits / float(total_queries)
    mrr = sum(reciprocal_ranks) / float(total_queries)

    print(f"\n==================================================")
    print(f"ORCA HYBRID RAG RETRIEVAL BENCHMARK RESULTS")
    print(f"==================================================")
    print(f"  Total Queries Evaluated:    {total_queries}")
    print(f"  Recall@{k}:                  {recall_at_k * 100:.1f}% ({recall_hits}/{total_queries})")
    print(f"  Mean Reciprocal Rank (MRR): {mrr:.4f}")
    print(f"  Top-1 Hybrid Recoveries:    {hybrid_only_recoveries}/{total_queries}")
    print(f"==================================================")

    assert recall_at_k >= 0.80, f"Benchmark Recall@{k} ({recall_at_k}) below minimum 80% threshold"
    assert mrr >= 0.70, f"Benchmark MRR ({mrr}) below minimum 0.70 threshold"
