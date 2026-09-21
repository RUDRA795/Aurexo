from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, DateTime, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from orca.database.models.base import Base, TimestampMixin, utc_now


class MarineAdvisoryModel(Base, TimestampMixin):
    __tablename__ = "marine_advisories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, default=utc_now, nullable=False
    )
    sector: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    language: Mapped[str] = mapped_column(String(16), default="en", index=True, nullable=False)
    embedding = mapped_column(Vector(1536), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Additive production embedding columns (P3.2)
    production_embedding = mapped_column(Vector(1024), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    embedding_dimension: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    embedding_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    search_vector = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('simple'::regconfig, coalesce(title, '')), 'A') || "
            "setweight(to_tsvector('simple'::regconfig, coalesce(content, '')), 'B')",
            persisted=True,
        ),
        nullable=True,
    )

    # Relationship to child chunks
    chunks: Mapped[list[MarineAdvisoryChunkModel]] = relationship(
        "MarineAdvisoryChunkModel",
        back_populates="advisory",
        cascade="all, delete-orphan",
        order_by="MarineAdvisoryChunkModel.chunk_index",
    )

    __table_args__ = (
        Index(
            "ix_marine_advisories_embedding_hnsw",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "ix_marine_advisories_production_embedding_hnsw",
            production_embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"production_embedding": "vector_cosine_ops"},
        ),
        Index(
            "ix_marine_advisories_search_vector_gin",
            search_vector,
            postgresql_using="gin",
        ),
    )


class MarineAdvisoryChunkModel(Base, TimestampMixin):
    __tablename__ = "marine_advisory_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    advisory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("marine_advisories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String(16), default="en", index=True, nullable=False)
    sector: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    source_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, default=utc_now, nullable=False
    )
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    embedding_1536 = mapped_column(Vector(1536), nullable=True)
    production_embedding = mapped_column(Vector(1024), nullable=True)
    search_vector = mapped_column(
        TSVECTOR,
        Computed(
            "setweight(to_tsvector('simple'::regconfig, coalesce(title, '')), 'A') || "
            "setweight(to_tsvector('simple'::regconfig, coalesce(content, '')), 'B')",
            persisted=True,
        ),
        nullable=True,
    )

    advisory: Mapped[MarineAdvisoryModel] = relationship(
        "MarineAdvisoryModel",
        back_populates="chunks",
    )

    __table_args__ = (
        Index(
            "ix_advisory_chunks_advisory_idx",
            advisory_id,
            chunk_index,
        ),
        Index(
            "ix_marine_advisory_chunks_1536_hnsw",
            embedding_1536,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding_1536": "vector_cosine_ops"},
        ),
        Index(
            "ix_marine_advisory_chunks_prod_hnsw",
            production_embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"production_embedding": "vector_cosine_ops"},
        ),
        Index(
            "ix_marine_advisory_chunks_search_vector_gin",
            search_vector,
            postgresql_using="gin",
        ),
    )
