from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Any

from sqlalchemy import (
    DateTime,
    Float,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from orca.database.models.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AgentRunCursorModel(Base):
    """Authoritative database-backed sequence allocation cursor for agent execution runs.

    Guarantees monotonic sequence numbering across concurrent workers and retries.
    """

    __tablename__ = "agent_run_cursors"

    run_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    next_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class AgentRunEventModel(Base):
    """Durable PostgreSQL event journal for observable ORCA agent execution streams."""

    __tablename__ = "agent_run_events"

    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        nullable=False,
    )
    node: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    duration_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    checkpoint_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    evidence_ids: Mapped[list[str] | None] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    redaction_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="clean",
    )

    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_agent_run_events_run_seq"),
        UniqueConstraint("run_id", "event_id", name="uq_agent_run_events_run_event"),
        Index("idx_agent_run_events_thread_seq", "thread_id", "sequence"),
        Index("idx_agent_run_events_run_seq", "run_id", "sequence"),
    )
