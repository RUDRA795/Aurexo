"""Create agent_run_cursors and agent_run_events tables for observable streaming

Revision ID: 0004_create_agent_run_events
Revises: 0003_add_advisory_chunks
Create Date: 2026-09-21 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0004_create_agent_run_events"
down_revision: Union[str, None] = "0003_add_advisory_chunks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Agent run cursors table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_run_cursors (
            run_id VARCHAR(64) PRIMARY KEY,
            next_sequence INTEGER NOT NULL DEFAULT 1,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """
    )

    # 2. Agent run events table
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_run_events (
            event_id UUID PRIMARY KEY,
            run_id VARCHAR(64) NOT NULL,
            thread_id VARCHAR(64) NOT NULL,
            trace_id VARCHAR(64) NOT NULL,
            sequence INTEGER NOT NULL,
            event_type VARCHAR(64) NOT NULL,
            timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            node VARCHAR(64),
            agent VARCHAR(64),
            tool VARCHAR(64),
            status VARCHAR(32),
            duration_ms DOUBLE PRECISION,
            checkpoint_id VARCHAR(64),
            evidence_ids JSONB,
            error_code VARCHAR(64),
            payload_json JSONB,
            redaction_status VARCHAR(32) NOT NULL DEFAULT 'clean',
            CONSTRAINT uq_agent_run_events_run_seq UNIQUE (run_id, sequence),
            CONSTRAINT uq_agent_run_events_run_event UNIQUE (run_id, event_id)
        );
        CREATE INDEX IF NOT EXISTS idx_agent_run_events_thread_seq
            ON agent_run_events (thread_id, sequence);
        CREATE INDEX IF NOT EXISTS idx_agent_run_events_run_seq
            ON agent_run_events (run_id, sequence);
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS agent_run_events CASCADE;")
    op.execute("DROP TABLE IF EXISTS agent_run_cursors CASCADE;")
