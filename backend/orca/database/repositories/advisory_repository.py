from __future__ import annotations

from datetime import datetime
from typing import Any
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from orca.database.models.advisory import MarineAdvisoryModel


class AdvisoryRepository:
    """Repository for marine text advisories and pgvector semantic search."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_advisory(
        self,
        *,
        title: str,
        content: str,
        source_id: str = "incois",
        published_at: datetime,
        sector: str | None = None,
        embedding: list[float] | None = None,
        metadata_json: dict[str, Any] | None = None,
    ) -> MarineAdvisoryModel:
        model = MarineAdvisoryModel(
            id=uuid.uuid4(),
            title=title,
            content=content,
            source_id=source_id,
            published_at=published_at,
            sector=sector.strip().upper() if sector else None,
            embedding=embedding,
            metadata_json=metadata_json,
        )
        self.session.add(model)
        await self.session.commit()
        await self.session.refresh(model)
        return model

    async def search_similar(
        self,
        embedding: list[float],
        *,
        limit: int = 5,
        sector: str | None = None,
    ) -> list[tuple[MarineAdvisoryModel, float]]:
        """Search advisories by cosine similarity using pgvector distance."""
        distance_col = MarineAdvisoryModel.embedding.cosine_distance(embedding).label("distance")
        stmt = (
            select(MarineAdvisoryModel, distance_col)
            .where(MarineAdvisoryModel.embedding.is_not(None))
            .order_by(distance_col, MarineAdvisoryModel.created_at.desc())
            .limit(limit)
        )
        if sector:
            stmt = stmt.where(MarineAdvisoryModel.sector == sector.strip().upper())

        result = await self.session.execute(stmt)
        return [(row[0], float(row[1])) for row in result.all()]

    async def count(self) -> int:
        result = await self.session.execute(select(MarineAdvisoryModel.id))
        return len(result.all())
