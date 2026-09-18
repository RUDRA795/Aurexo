from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Index, JSON, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

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
    embedding = mapped_column(Vector(1536), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    __table_args__ = (
        Index(
            "ix_marine_advisories_embedding_hnsw",
            embedding,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )
