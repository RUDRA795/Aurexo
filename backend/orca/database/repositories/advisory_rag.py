from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import math
from typing import Any
import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from orca.database.models.advisory import MarineAdvisoryModel
from orca.schemas.orca_contract import (
    AccessMethod,
    DataQuality,
    Evidence,
    SourceMetadata,
    utc_now,
)


class EmbeddingProvider(ABC):
    """Abstract boundary for text embedding generation."""

    @abstractmethod
    async def embed_text(self, text: str) -> list[float]:
        raise NotImplementedError

    @property
    @abstractmethod
    def dimension(self) -> int:
        raise NotImplementedError


class DeterministicMockEmbeddingProvider(EmbeddingProvider):
    """Deterministic local embedding generator for test and offline environments.
    
    Generates unit-normalized float vectors of fixed dimension based on SHA-256
    digest tokens without requiring external network access or LLM APIs.
    """

    def __init__(self, dimension: int = 1536):
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed_text(self, text: str) -> list[float]:
        return self.embed_text_sync(text)

    def embed_text_sync(self, text: str) -> list[float]:
        if not text:
            raise ValueError("Cannot embed empty text string.")

        h = hashlib.sha256(text.encode("utf-8")).digest()
        vec = [0.0] * self._dimension
        for i in range(self._dimension):
            byte_val = h[i % len(h)]
            # Spread pseudo-random values around zero
            vec[i] = float((byte_val % 31) - 15) / 15.0

        # L2-normalize vector to unit length
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [round(x / norm, 6) for x in vec]
        return vec


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
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AdvisorySearchResult:
    """SearchResult carrying cosine distance, computed similarity, and typed ORCA Evidence."""

    document: AdvisoryDocument
    similarity_score: float
    cosine_distance: float
    evidence: Evidence


class AdvisoryRAGRepository:
    """Repository for indexing, managing, and querying marine text advisories via pgvector."""

    def __init__(
        self,
        session: AsyncSession,
        embedding_provider: EmbeddingProvider | None = None,
        *,
        dimension: int = 1536,
    ):
        self.session = session
        self.embedding_provider = embedding_provider or DeterministicMockEmbeddingProvider(dimension=dimension)
        self._expected_dim = self.embedding_provider.dimension

    @property
    def dimension(self) -> int:
        return self._expected_dim

    def _validate_embedding(self, embedding: list[float]) -> None:
        if len(embedding) != self._expected_dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {self._expected_dim}, got {len(embedding)}."
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
        metadata: dict[str, Any] | None = None,
        advisory_id: uuid.UUID | None = None,
    ) -> AdvisoryDocument:
        """Index a new marine advisory document with optional auto-generated embedding."""
        if not title or not title.strip():
            raise ValueError("Advisory title cannot be empty.")
        if not content or not content.strip():
            raise ValueError("Advisory content cannot be empty.")

        pub_time = published_at or utc_now()
        if pub_time.tzinfo is None:
            pub_time = pub_time.replace(tzinfo=timezone.utc)

        # Generate embedding if not supplied
        active_embedding = embedding
        if active_embedding is None and self.embedding_provider is not None:
            active_embedding = await self.embedding_provider.embed_text(f"{title}\n{content}")

        if active_embedding is not None:
            self._validate_embedding(active_embedding)

        doc_id = advisory_id or uuid.uuid4()
        clean_sector = sector.strip().upper() if sector else None
        clean_lang = language.strip().lower() if language else "en"

        model = MarineAdvisoryModel(
            id=doc_id,
            title=title.strip(),
            content=content.strip(),
            source_id=source_id.strip(),
            published_at=pub_time,
            sector=clean_sector,
            language=clean_lang,
            embedding=active_embedding,
            metadata_json=metadata or {},
        )

        self.session.add(model)
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
    ) -> AdvisoryDocument:
        """Update an existing advisory record in the database."""
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
            self._validate_embedding(embedding)
            model.embedding = embedding

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
            metadata=model.metadata_json or {},
        )

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
    ) -> list[AdvisorySearchResult]:
        """Perform semantic similarity search with metadata and freshness filtering.
        
        Guarantees deterministic tie-breaking by published_at DESC and primary key ID ASC.
        """
        active_embedding = query_embedding
        if active_embedding is None:
            if not query_text:
                raise ValueError("Either query_text or query_embedding must be supplied.")
            active_embedding = await self.embedding_provider.embed_text(query_text)

        self._validate_embedding(active_embedding)

        distance_col = MarineAdvisoryModel.embedding.cosine_distance(active_embedding).label("distance")

        stmt = select(MarineAdvisoryModel, distance_col).where(MarineAdvisoryModel.embedding.is_not(None))

        # Sector filter
        if sector:
            stmt = stmt.where(func.upper(MarineAdvisoryModel.sector) == sector.strip().upper())

        # Multilingual / language filter
        if language:
            stmt = stmt.where(func.lower(MarineAdvisoryModel.language) == language.strip().lower())

        # Freshness / temporal filter
        if min_published_at:
            if min_published_at.tzinfo is None:
                min_published_at = min_published_at.replace(tzinfo=timezone.utc)
            stmt = stmt.where(MarineAdvisoryModel.published_at >= min_published_at)

        # Distance threshold filter
        if max_cosine_distance is not None:
            stmt = stmt.where(distance_col <= max_cosine_distance)

        # Deterministic tie-breaking order
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
            metadata=model.metadata_json or {},
        )

    async def delete_by_id(self, advisory_id: uuid.UUID) -> bool:
        """Delete an advisory by its unique UUID."""
        stmt = delete(MarineAdvisoryModel).where(MarineAdvisoryModel.id == advisory_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0
