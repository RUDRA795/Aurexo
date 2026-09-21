from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import re
from typing import Any, Sequence
import uuid

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from orca.database.models.advisory import MarineAdvisoryChunkModel, MarineAdvisoryModel
from orca.embeddings.base import (
    EmbeddingDimensionMismatchError,
    EmbeddingProvider,
    EmbeddingProviderUnavailableError,
)
from orca.embeddings.mock import DeterministicMockEmbeddingProvider
from orca.rag.chunking import AdvisoryChunk, DeterministicAdvisoryChunker
from orca.rag.reranker import BaseReranker, NoOpReranker
from orca.schemas.orca_contract import (
    AccessMethod,
    DataQuality,
    Evidence,
    EvidenceType,
    SourceMetadata,
    utc_now,
)
from orca.telemetry.tracer import trace_span


@dataclass(frozen=True)
class AdvisoryDocument:
    """Strongly-typed representation of an indexed marine advisory."""

    id: uuid.UUID
    title: str
    content: str
    source_id: str
    published_at: datetime
    sector: str | None = None
    language: str = "en"
    embedding: list[float] | None = None
    production_embedding: list[float] | None = None
    embedding_model: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ChunkSearchResult:
    """Ranked chunk result carrying lexical, dense, and fused RRF scores."""

    chunk_id: str
    advisory_id: uuid.UUID
    chunk_index: int
    title: str
    content: str
    language: str = "en"
    sector: str | None = None
    source_id: str = "incois_advisory"
    published_at: datetime = field(default_factory=utc_now)
    dense_rank: int | None = None
    dense_similarity: float | None = None
    lexical_rank: int | None = None
    lexical_score: float | None = None
    rrf_score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)
    parent_document: AdvisoryDocument | None = None
    evidence: Evidence | None = None


@dataclass(frozen=True)
class AdvisorySearchResult:
    """Aggregated advisory search result carrying cosine similarity, RRF score, and typed Evidence."""

    document: AdvisoryDocument
    similarity_score: float
    cosine_distance: float
    evidence: Evidence
    matched_chunks: list[ChunkSearchResult] = field(default_factory=list)
    rrf_score: float | None = None
    lexical_score: float | None = None


class AdvisoryRAGRepository:
    """Repository for indexing, managing, and querying marine text advisories via hybrid pgvector + GIN FTS."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_provider: EmbeddingProvider | None = None,
        *,
        dimension: int = 1536,
        chunker: DeterministicAdvisoryChunker | None = None,
        reranker: BaseReranker | None = None,
    ):
        self.session = session
        self.embedding_provider = embedding_provider or DeterministicMockEmbeddingProvider(dimension=dimension)
        self._expected_dim = self.embedding_provider.dimension
        self.chunker = chunker or DeterministicAdvisoryChunker()
        self.reranker = reranker or NoOpReranker()

    @property
    def dimension(self) -> int:
        return self._expected_dim

    @property
    def is_production_provider(self) -> bool:
        return self.embedding_provider.dimension == 1024 and getattr(self.embedding_provider, "is_available", False)

    def _validate_embedding(self, embedding: Sequence[float], expected_dim: int | None = None) -> None:
        target_dim = expected_dim or self._expected_dim
        if len(embedding) != target_dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {target_dim}, got {len(embedding)}."
            )
        for i, val in enumerate(embedding):
            if not math.isfinite(val):
                raise ValueError(f"Embedding component at index {i} is not a finite float: {val}")

    async def index_advisory(
        self,
        *,
        title: str,
        content: str,
        source_id: str = "incois_advisory",
        published_at: datetime | None = None,
        sector: str | None = None,
        language: str = "en",
        embedding: list[float] | None = None,
        production_embedding: list[float] | None = None,
        metadata: dict[str, Any] | None = None,
        advisory_id: uuid.UUID | None = None,
    ) -> AdvisoryDocument:
        """Index a new marine advisory document and generate deterministic child chunks."""
        if not title or not title.strip():
            raise ValueError("Advisory title cannot be empty.")
        if not content or not content.strip():
            raise ValueError("Advisory content cannot be empty.")

        pub_time = published_at or utc_now()
        if pub_time.tzinfo is None:
            pub_time = pub_time.replace(tzinfo=timezone.utc)

        doc_id = advisory_id or uuid.uuid4()
        clean_sector = sector.strip().upper() if sector else None
        clean_lang = language.strip().lower() if language else "en"

        # Determine embeddings for parent advisory
        emb_1536 = embedding
        emb_1024 = production_embedding
        model_name = None
        model_dim = None
        model_ver = None
        model_prov = None
        embedded_dt = None

        if self.embedding_provider is not None:
            if self.embedding_provider.dimension == 1536:
                if emb_1536 is None:
                    emb_1536 = await self.embedding_provider.embed_text(f"{title}\n{content}")
                self._validate_embedding(emb_1536, 1536)
            elif self.embedding_provider.dimension == 1024:
                if emb_1024 is None:
                    emb_1024 = await self.embedding_provider.embed_text(f"{title}\n{content}")
                self._validate_embedding(emb_1024, 1024)
                model_name = self.embedding_provider.model_name
                model_dim = 1024
                model_ver = self.embedding_provider.version
                model_prov = type(self.embedding_provider).__name__
                embedded_dt = utc_now()

        if emb_1536 is not None:
            self._validate_embedding(emb_1536, 1536)
        if emb_1024 is not None:
            self._validate_embedding(emb_1024, 1024)

        # 1. Create Parent Model
        model = MarineAdvisoryModel(
            id=doc_id,
            title=title.strip(),
            content=content.strip(),
            source_id=source_id.strip(),
            published_at=pub_time,
            sector=clean_sector,
            language=clean_lang,
            embedding=emb_1536,
            production_embedding=emb_1024,
            embedding_model=model_name,
            embedding_dimension=model_dim,
            embedding_version=model_ver,
            embedding_provider=model_prov,
            embedded_at=embedded_dt,
            metadata_json=metadata or {},
        )
        self.session.add(model)

        # 2. Generate Deterministic Chunks
        raw_chunks = self.chunker.chunk_advisory(
            advisory_id=doc_id,
            title=title.strip(),
            content=content.strip(),
            language=clean_lang,
            sector=clean_sector,
            source_id=source_id.strip(),
            published_at=pub_time,
            metadata=metadata,
        )

        # 3. Embed & persist child chunks
        for c in raw_chunks:
            chunk_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}_{c.chunk_index}")
            chunk_1536 = None
            chunk_1024 = None

            if self.embedding_provider is not None:
                chunk_text = f"{c.title}\n{c.content}"
                if self.embedding_provider.dimension == 1536:
                    chunk_1536 = await self.embedding_provider.embed_text(chunk_text)
                elif self.embedding_provider.dimension == 1024:
                    chunk_1024 = await self.embedding_provider.embed_text(chunk_text)

            chunk_meta = dict(c.metadata)
            chunk_meta["unit_count"] = c.unit_count
            chunk_meta["segmentation_method"] = c.segmentation_method

            chunk_model = MarineAdvisoryChunkModel(
                id=chunk_uuid,
                advisory_id=doc_id,
                chunk_index=c.chunk_index,
                title=c.title,
                content=c.content,
                language=c.language,
                sector=c.sector,
                source_id=c.source_id,
                published_at=c.published_at,
                retrieved_at=c.retrieved_at,
                metadata_json=chunk_meta,
                embedding_1536=chunk_1536,
                production_embedding=chunk_1024,
            )
            self.session.add(chunk_model)

        await self.session.commit()
        await self.session.refresh(model)

        return AdvisoryDocument(
            id=model.id,
            title=model.title,
            content=model.content,
            source_id=model.source_id,
            published_at=model.published_at,
            sector=model.sector,
            language=model.language,
            embedding=list(model.embedding) if model.embedding is not None else None,
            production_embedding=list(model.production_embedding) if model.production_embedding is not None else None,
            embedding_model=model.embedding_model,
            metadata=model.metadata_json or {},
        )

    async def update_advisory(
        self,
        advisory_id: uuid.UUID,
        *,
        title: str | None = None,
        content: str | None = None,
        sector: str | None = None,
        language: str | None = None,
        metadata: dict[str, Any] | None = None,
        embedding: list[float] | None = None,
        production_embedding: list[float] | None = None,
    ) -> AdvisoryDocument:
        """Update an existing advisory record and regenerate its child chunks."""
        stmt = select(MarineAdvisoryModel).where(MarineAdvisoryModel.id == advisory_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()

        if model is None:
            raise KeyError(f"Advisory record with ID {advisory_id} not found.")

        if title is not None:
            model.title = title.strip()
        if content is not None:
            model.content = content.strip()
        if sector is not None:
            model.sector = sector.strip().upper() if sector else None
        if language is not None:
            model.language = language.strip().lower() if language else "en"
        if metadata is not None:
            model.metadata_json = metadata

        if embedding is not None:
            self._validate_embedding(embedding, 1536)
            model.embedding = embedding
        if production_embedding is not None:
            self._validate_embedding(production_embedding, 1024)
            model.production_embedding = production_embedding

        # Delete existing chunks and regenerate
        await self.session.execute(
            delete(MarineAdvisoryChunkModel).where(MarineAdvisoryChunkModel.advisory_id == advisory_id)
        )

        raw_chunks = self.chunker.chunk_advisory(
            advisory_id=advisory_id,
            title=model.title,
            content=model.content,
            language=model.language,
            sector=model.sector,
            source_id=model.source_id,
            published_at=model.published_at,
            metadata=model.metadata_json,
        )

        for c in raw_chunks:
            chunk_uuid = uuid.uuid5(uuid.NAMESPACE_DNS, f"{advisory_id}_{c.chunk_index}")
            chunk_1536 = None
            chunk_1024 = None

            if self.embedding_provider is not None:
                chunk_text = f"{c.title}\n{c.content}"
                if self.embedding_provider.dimension == 1536:
                    chunk_1536 = await self.embedding_provider.embed_text(chunk_text)
                elif self.embedding_provider.dimension == 1024:
                    chunk_1024 = await self.embedding_provider.embed_text(chunk_text)

            chunk_meta = dict(c.metadata)
            chunk_meta["unit_count"] = c.unit_count
            chunk_meta["segmentation_method"] = c.segmentation_method

            chunk_model = MarineAdvisoryChunkModel(
                id=chunk_uuid,
                advisory_id=advisory_id,
                chunk_index=c.chunk_index,
                title=c.title,
                content=c.content,
                language=c.language,
                sector=c.sector,
                source_id=c.source_id,
                published_at=c.published_at,
                retrieved_at=c.retrieved_at,
                metadata_json=chunk_meta,
                embedding_1536=chunk_1536,
                production_embedding=chunk_1024,
            )
            self.session.add(chunk_model)

        await self.session.commit()
        await self.session.refresh(model)

        return AdvisoryDocument(
            id=model.id,
            title=model.title,
            content=model.content,
            source_id=model.source_id,
            published_at=model.published_at,
            sector=model.sector,
            language=model.language,
            embedding=list(model.embedding) if model.embedding is not None else None,
            production_embedding=list(model.production_embedding) if model.production_embedding is not None else None,
            embedding_model=model.embedding_model,
            metadata=model.metadata_json or {},
        )

    async def search_lexical(
        self,
        query_text: str,
        *,
        limit: int = 10,
        sector: str | None = None,
        language: str | None = None,
        min_published_at: datetime | None = None,
        exact_terms: Sequence[str] | None = None,
    ) -> list[tuple[MarineAdvisoryChunkModel, float]]:
        """Perform PostgreSQL full-text search with title ('A') and content ('B') weighting.

        Uses plainto_tsquery('simple', ...) for safe user query normalization and
        preserves exact-match boosts for key harbor names and marine terminology.
        """
        if not query_text or not query_text.strip():
            return []

        clean_q = query_text.strip()
        ts_query = func.plainto_tsquery("simple", clean_q)
        rank_col = func.ts_rank_cd(MarineAdvisoryChunkModel.search_vector, ts_query).label("lexical_score")

        stmt = select(MarineAdvisoryChunkModel, rank_col).where(
            MarineAdvisoryChunkModel.search_vector.op("@@")(ts_query)
        )

        if sector:
            stmt = stmt.where(func.upper(MarineAdvisoryChunkModel.sector) == sector.strip().upper())
        if language:
            stmt = stmt.where(func.lower(MarineAdvisoryChunkModel.language) == language.strip().lower())
        if min_published_at:
            if min_published_at.tzinfo is None:
                min_published_at = min_published_at.replace(tzinfo=timezone.utc)
            stmt = stmt.where(MarineAdvisoryChunkModel.published_at >= min_published_at)

        stmt = stmt.order_by(
            rank_col.desc(),
            MarineAdvisoryChunkModel.published_at.desc(),
            MarineAdvisoryChunkModel.advisory_id.asc(),
            MarineAdvisoryChunkModel.chunk_index.asc(),
        ).limit(limit)

        result = await self.session.execute(stmt)
        rows = result.all()

        # If plainto_tsquery yields no results (due to conversational words), try term OR query or ILIKE
        if not rows:
            # Extract non-stop words
            tokens = [t for t in re.findall(r"\w+", clean_q, re.UNICODE) if len(t) > 2]
            stop_words = {"show", "recent", "related", "guidance", "what", "where", "tell", "please", "with", "from"}
            meaningful = [t for t in tokens if t.lower() not in stop_words]

            if meaningful:
                or_expr = " | ".join(meaningful)
                or_ts_query = func.to_tsquery("simple", or_expr)
                or_rank = func.ts_rank_cd(MarineAdvisoryChunkModel.search_vector, or_ts_query).label("lexical_score")
                or_stmt = select(MarineAdvisoryChunkModel, or_rank).where(
                    MarineAdvisoryChunkModel.search_vector.op("@@")(or_ts_query)
                )
                if sector:
                    or_stmt = or_stmt.where(func.upper(MarineAdvisoryChunkModel.sector) == sector.strip().upper())
                if language:
                    or_stmt = or_stmt.where(func.lower(MarineAdvisoryChunkModel.language) == language.strip().lower())
                if min_published_at:
                    or_stmt = or_stmt.where(MarineAdvisoryChunkModel.published_at >= min_published_at)

                or_stmt = or_stmt.order_by(
                    or_rank.desc(),
                    MarineAdvisoryChunkModel.published_at.desc(),
                    MarineAdvisoryChunkModel.advisory_id.asc(),
                    MarineAdvisoryChunkModel.chunk_index.asc(),
                ).limit(limit)

                or_result = await self.session.execute(or_stmt)
                rows = or_result.all()

        return [(row[0], float(row[1])) for row in rows]

    async def search_dense(
        self,
        *,
        query_embedding: Sequence[float],
        limit: int = 10,
        sector: str | None = None,
        language: str | None = None,
        min_published_at: datetime | None = None,
        max_cosine_distance: float | None = None,
        hnsw_iterative_scan: str | None = None,
        ef_search: int | None = None,
    ) -> list[tuple[MarineAdvisoryChunkModel, float]]:
        """Perform dense vector retrieval on chunks using pgvector HNSW index.

        Supports optional session-level tuning:
        - hnsw.iterative_scan: 'off' | 'relaxed_order' | 'strict_order'
        - hnsw.ef_search: integer
        """
        dim = len(query_embedding)
        if dim == 1024:
            target_col = MarineAdvisoryChunkModel.production_embedding
        elif dim == 1536:
            target_col = MarineAdvisoryChunkModel.embedding_1536
        else:
            raise ValueError(f"Embedding dimension mismatch: expected 1024 or 1536, got {dim}.")

        self._validate_embedding(query_embedding, dim)

        # Optional session-level GUC configuration
        if hnsw_iterative_scan in ("off", "relaxed_order", "strict_order"):
            await self.session.execute(text(f"SET LOCAL hnsw.iterative_scan = '{hnsw_iterative_scan}'"))
        if ef_search is not None and ef_search > 0:
            await self.session.execute(text(f"SET LOCAL hnsw.ef_search = {int(ef_search)}"))

        distance_col = target_col.cosine_distance(list(query_embedding)).label("distance")

        stmt = select(MarineAdvisoryChunkModel, distance_col).where(target_col.is_not(None))

        if sector:
            stmt = stmt.where(func.upper(MarineAdvisoryChunkModel.sector) == sector.strip().upper())
        if language:
            stmt = stmt.where(func.lower(MarineAdvisoryChunkModel.language) == language.strip().lower())
        if min_published_at:
            if min_published_at.tzinfo is None:
                min_published_at = min_published_at.replace(tzinfo=timezone.utc)
            stmt = stmt.where(MarineAdvisoryChunkModel.published_at >= min_published_at)
        if max_cosine_distance is not None:
            stmt = stmt.where(distance_col <= max_cosine_distance)

        stmt = stmt.order_by(
            distance_col.asc(),
            MarineAdvisoryChunkModel.published_at.desc(),
            MarineAdvisoryChunkModel.advisory_id.asc(),
            MarineAdvisoryChunkModel.chunk_index.asc(),
        ).limit(limit)

        result = await self.session.execute(stmt)
        rows = result.all()
        return [(row[0], float(row[1])) for row in rows]

    async def search_chunks(
        self,
        query_text: str | None = None,
        *,
        query_embedding: Sequence[float] | None = None,
        limit: int = 5,
        sector: str | None = None,
        language: str | None = None,
        min_published_at: datetime | None = None,
        max_cosine_distance: float | None = None,
        dense_weight: float = 1.0,
        lexical_weight: float = 1.0,
        rrf_k: int = 60,
        hnsw_iterative_scan: str | None = None,
        ef_search: int | None = None,
    ) -> list[ChunkSearchResult]:
        """Perform hybrid retrieval over chunks combining dense HNSW and lexical GIN FTS via RRF.

        RRF formula: RRF(d) = (w_dense / (k + rank_dense)) + (w_lexical / (k + rank_lexical))
        Deterministic tie-breaking:
            RRF score DESC, published_at DESC, advisory_id ASC, chunk_id ASC.
        """
        with trace_span("database.advisory_rag.search_chunks", attributes={"sector": sector or "ALL", "limit": limit}):
            active_embedding = list(query_embedding) if query_embedding is not None else None
            if active_embedding is not None:
                self._validate_embedding(active_embedding)

            # Generate query embedding if needed and available
            if active_embedding is None and query_text:
                if self.embedding_provider.is_available:
                    try:
                        active_embedding = await self.embedding_provider.embed_text(query_text)
                    except EmbeddingProviderUnavailableError:
                        active_embedding = None
                else:
                    active_embedding = None

            candidate_pool_limit = max(limit * 3, 20)

            # 1. Lexical retrieval
            lexical_rows: list[tuple[MarineAdvisoryChunkModel, float]] = []
            if query_text:
                lexical_rows = await self.search_lexical(
                    query_text,
                    limit=candidate_pool_limit,
                    sector=sector,
                    language=language,
                    min_published_at=min_published_at,
                )

            # 2. Dense retrieval
            dense_rows: list[tuple[MarineAdvisoryChunkModel, float]] = []
            if active_embedding is not None:
                dense_rows = await self.search_dense(
                    query_embedding=active_embedding,
                    limit=candidate_pool_limit,
                    sector=sector,
                    language=language,
                    min_published_at=min_published_at,
                    max_cosine_distance=max_cosine_distance,
                    hnsw_iterative_scan=hnsw_iterative_scan,
                    ef_search=ef_search,
                )

            # Map chunk models and calculate ranks
            chunks_by_id: dict[uuid.UUID, MarineAdvisoryChunkModel] = {}
            dense_ranks: dict[uuid.UUID, tuple[int, float]] = {}  # chunk_uuid -> (1-based rank, similarity)
            lexical_ranks: dict[uuid.UUID, tuple[int, float]] = {}  # chunk_uuid -> (1-based rank, score)

            for rank_0, (chunk, dist) in enumerate(dense_rows):
                chunks_by_id[chunk.id] = chunk
                sim = round(max(0.0, 1.0 - dist), 4)
                dense_ranks[chunk.id] = (rank_0 + 1, sim)

            for rank_0, (chunk, score) in enumerate(lexical_rows):
                chunks_by_id[chunk.id] = chunk
                lexical_ranks[chunk.id] = (rank_0 + 1, score)

            if not chunks_by_id:
                return []

            # Pre-fetch parent advisory documents
            parent_ids = list({c.advisory_id for c in chunks_by_id.values()})
            stmt_parents = select(MarineAdvisoryModel).where(MarineAdvisoryModel.id.in_(parent_ids))
            res_parents = await self.session.execute(stmt_parents)
            parents_map = {p.id: p for p in res_parents.scalars().all()}

            # 3. Compute RRF scores
            fused_candidates: list[ChunkSearchResult] = []
            for chunk_uuid, chunk in chunks_by_id.items():
                d_info = dense_ranks.get(chunk_uuid)
                l_info = lexical_ranks.get(chunk_uuid)

                d_rank, d_sim = d_info if d_info else (None, None)
                l_rank, l_score = l_info if l_info else (None, None)

                score_dense = (dense_weight / (rrf_k + d_rank)) if d_rank is not None else 0.0
                score_lex = (lexical_weight / (rrf_k + l_rank)) if l_rank is not None else 0.0
                rrf_score = round(score_dense + score_lex, 6)

                parent_model = parents_map.get(chunk.advisory_id)
                parent_doc = (
                    AdvisoryDocument(
                        id=parent_model.id,
                        title=parent_model.title,
                        content=parent_model.content,
                        source_id=parent_model.source_id,
                        published_at=parent_model.published_at,
                        sector=parent_model.sector,
                        language=parent_model.language,
                        embedding=list(parent_model.embedding) if parent_model.embedding is not None else None,
                        production_embedding=(
                            list(parent_model.production_embedding)
                            if parent_model.production_embedding is not None
                            else None
                        ),
                        embedding_model=parent_model.embedding_model,
                        metadata=parent_model.metadata_json or {},
                    )
                    if parent_model
                    else None
                )

                chunk_id_str = f"{chunk.advisory_id}_chunk_{chunk.chunk_index}"
                res = ChunkSearchResult(
                    chunk_id=chunk_id_str,
                    advisory_id=chunk.advisory_id,
                    chunk_index=chunk.chunk_index,
                    title=chunk.title,
                    content=chunk.content,
                    language=chunk.language,
                    sector=chunk.sector,
                    source_id=chunk.source_id,
                    published_at=chunk.published_at,
                    dense_rank=d_rank,
                    dense_similarity=d_sim,
                    lexical_rank=l_rank,
                    lexical_score=l_score,
                    rrf_score=rrf_score,
                    metadata=chunk.metadata_json or {},
                    parent_document=parent_doc,
                )
                fused_candidates.append(res)

            # 4. Deterministic Tie-breaking:
            # RRF score DESC, published_at DESC, advisory_id ASC, chunk_id ASC
            fused_candidates.sort(
                key=lambda x: (
                    -x.rrf_score,
                    -x.published_at.timestamp(),
                    x.advisory_id,
                    x.chunk_id,
                )
            )

            # 5. Optional Reranking
            if query_text and self.reranker.is_available:
                reranked, was_reranked = await self.reranker.rerank(
                    query_text, fused_candidates, top_k=limit
                )
                if was_reranked:
                    fused_candidates = reranked

            return fused_candidates[:limit]

    async def search_advisories(
        self,
        query_text: str | None = None,
        *,
        query_embedding: list[float] | None = None,
        limit: int = 5,
        sector: str | None = None,
        language: str | None = None,
        min_published_at: datetime | None = None,
        max_cosine_distance: float | None = None,
        dense_weight: float = 1.0,
        lexical_weight: float = 1.0,
        rrf_k: int = 60,
    ) -> list[AdvisorySearchResult]:
        """Hybrid search returning parent AdvisoryDocument results and typed ADVISORY Evidence.

        Fully backward-compatible with original search_advisories contract.
        """
        # If chunks exist, use hybrid chunk retrieval and aggregate by parent advisory
        chunks = await self.search_chunks(
            query_text=query_text,
            query_embedding=query_embedding,
            limit=limit * 2,
            sector=sector,
            language=language,
            min_published_at=min_published_at,
            max_cosine_distance=max_cosine_distance,
            dense_weight=dense_weight,
            lexical_weight=lexical_weight,
            rrf_k=rrf_k,
        )

        if chunks:
            # Group chunks by parent advisory ID, preserving highest scoring chunk first
            grouped: dict[uuid.UUID, list[ChunkSearchResult]] = {}
            for c in chunks:
                grouped.setdefault(c.advisory_id, []).append(c)

            results: list[AdvisorySearchResult] = []
            for adv_id, matched in grouped.items():
                best = matched[0]
                parent = best.parent_document
                if not parent:
                    continue

                # Determine representative similarity & cosine distance
                sim = best.dense_similarity if best.dense_similarity is not None else 1.0
                dist = round(1.0 - sim, 4)

                evidence = Evidence(
                    source=SourceMetadata(
                        source_id=parent.source_id,
                        organization="INCOIS / Regional Fisheries Department",
                        dataset=f"Advisory Bulletin ({parent.title})",
                        domain=["fisheries_advisory", "marine_context"],
                        coverage=parent.sector.lower() if parent.sector else "indian_ocean",
                        authority="official",
                        access=AccessMethod.API,
                        freshness_policy_hours=48.0,
                    ),
                    variable="advisory_context",
                    value={
                        "advisory_id": str(parent.id),
                        "chunk_id": best.chunk_id,
                        "title": parent.title,
                        "content": best.content,
                        "sector": parent.sector,
                        "language": parent.language,
                        "similarity": sim,
                        "dense_rank": best.dense_rank,
                        "lexical_rank": best.lexical_rank,
                        "rrf_score": best.rrf_score,
                    },
                    evidence_type=EvidenceType.ADVISORY,
                    observed_at=parent.published_at,
                    retrieved_at=utc_now(),
                    quality=DataQuality.GOOD,
                    method="hybrid_rrf_pgvector",
                    derived=False,
                    estimated=False,
                    derivation_details=f"hybrid_rrf_k{rrf_k}_score_{best.rrf_score:.6f}",
                )

                results.append(
                    AdvisorySearchResult(
                        document=parent,
                        similarity_score=sim,
                        cosine_distance=dist,
                        evidence=evidence,
                        matched_chunks=matched,
                        rrf_score=best.rrf_score,
                        lexical_score=best.lexical_score,
                    )
                )

            # Sort by RRF score DESC, published_at DESC, id ASC
            results.sort(
                key=lambda r: (
                    -(r.rrf_score or 0.0),
                    -r.document.published_at.timestamp(),
                    r.document.id,
                )
            )
            return results[:limit]

        # Fallback to direct parent advisory search (for backward compatibility if no chunks exist)
        return await self._search_advisories_direct(
            query_text=query_text,
            query_embedding=query_embedding,
            limit=limit,
            sector=sector,
            language=language,
            min_published_at=min_published_at,
            max_cosine_distance=max_cosine_distance,
        )

    async def _search_advisories_direct(
        self,
        query_text: str | None = None,
        *,
        query_embedding: list[float] | None = None,
        limit: int = 5,
        sector: str | None = None,
        language: str | None = None,
        min_published_at: datetime | None = None,
        max_cosine_distance: float | None = None,
    ) -> list[AdvisorySearchResult]:
        """Direct search against marine_advisories table (fallback/legacy path)."""
        active_embedding = query_embedding
        if active_embedding is None:
            if not query_text:
                raise ValueError("Either query_text or query_embedding must be supplied.")
            active_embedding = await self.embedding_provider.embed_text(query_text)

        dim = len(active_embedding)
        target_col = MarineAdvisoryModel.production_embedding if dim == 1024 else MarineAdvisoryModel.embedding
        distance_col = target_col.cosine_distance(active_embedding).label("distance")

        stmt = select(MarineAdvisoryModel, distance_col).where(target_col.is_not(None))

        if sector:
            stmt = stmt.where(func.upper(MarineAdvisoryModel.sector) == sector.strip().upper())
        if language:
            stmt = stmt.where(func.lower(MarineAdvisoryModel.language) == language.strip().lower())
        if min_published_at:
            if min_published_at.tzinfo is None:
                min_published_at = min_published_at.replace(tzinfo=timezone.utc)
            stmt = stmt.where(MarineAdvisoryModel.published_at >= min_published_at)
        if max_cosine_distance is not None:
            stmt = stmt.where(distance_col <= max_cosine_distance)

        stmt = stmt.order_by(
            distance_col.asc(),
            MarineAdvisoryModel.published_at.desc(),
            MarineAdvisoryModel.id.asc(),
        ).limit(limit)

        result = await self.session.execute(stmt)
        rows = result.all()

        search_results: list[AdvisorySearchResult] = []
        for model, dist_val in rows:
            dist = float(dist_val)
            similarity = round(max(0.0, 1.0 - dist), 4)

            doc = AdvisoryDocument(
                id=model.id,
                title=model.title,
                content=model.content,
                source_id=model.source_id,
                published_at=model.published_at,
                sector=model.sector,
                language=model.language,
                embedding=list(model.embedding) if model.embedding is not None else None,
                production_embedding=list(model.production_embedding) if model.production_embedding is not None else None,
                embedding_model=model.embedding_model,
                metadata=model.metadata_json or {},
            )

            evidence = Evidence(
                source=SourceMetadata(
                    source_id=model.source_id,
                    organization="INCOIS / Regional Fisheries Department",
                    dataset=f"Advisory Bulletin ({model.title})",
                    domain=["fisheries_advisory", "marine_context"],
                    coverage=model.sector.lower() if model.sector else "indian_ocean",
                    authority="official",
                    access=AccessMethod.API,
                    freshness_policy_hours=48.0,
                ),
                variable="advisory_context",
                value={
                    "advisory_id": str(model.id),
                    "title": model.title,
                    "content": model.content,
                    "sector": model.sector,
                    "language": model.language,
                    "similarity": similarity,
                },
                evidence_type=EvidenceType.ADVISORY,
                observed_at=model.published_at,
                retrieved_at=utc_now(),
                quality=DataQuality.GOOD,
                method="pgvector_cosine_similarity",
                derived=False,
                estimated=False,
                derivation_details=f"pgvector_rag_cosine_distance_{dist:.4f}",
            )

            search_results.append(
                AdvisorySearchResult(
                    document=doc,
                    similarity_score=similarity,
                    cosine_distance=dist,
                    evidence=evidence,
                )
            )

        return search_results

    async def get_by_id(self, advisory_id: uuid.UUID) -> AdvisoryDocument | None:
        """Fetch an advisory by its unique UUID."""
        stmt = select(MarineAdvisoryModel).where(MarineAdvisoryModel.id == advisory_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None

        return AdvisoryDocument(
            id=model.id,
            title=model.title,
            content=model.content,
            source_id=model.source_id,
            published_at=model.published_at,
            sector=model.sector,
            language=model.language,
            embedding=list(model.embedding) if model.embedding is not None else None,
            production_embedding=list(model.production_embedding) if model.production_embedding is not None else None,
            embedding_model=model.embedding_model,
            metadata=model.metadata_json or {},
        )

    async def delete_by_id(self, advisory_id: uuid.UUID) -> bool:
        """Delete an advisory and all its cascaded chunks by UUID."""
        stmt = delete(MarineAdvisoryModel).where(MarineAdvisoryModel.id == advisory_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def get_chunks_for_advisory(self, advisory_id: uuid.UUID) -> list[ChunkSearchResult]:
        """Retrieve all indexed chunks for a given parent advisory."""
        stmt = (
            select(MarineAdvisoryChunkModel)
            .where(MarineAdvisoryChunkModel.advisory_id == advisory_id)
            .order_by(MarineAdvisoryChunkModel.chunk_index.asc())
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()

        return [
            ChunkSearchResult(
                chunk_id=f"{m.advisory_id}_chunk_{m.chunk_index}",
                advisory_id=m.advisory_id,
                chunk_index=m.chunk_index,
                title=m.title,
                content=m.content,
                language=m.language,
                sector=m.sector,
                source_id=m.source_id,
                published_at=m.published_at,
                metadata=m.metadata_json or {},
            )
            for m in models
        ]
