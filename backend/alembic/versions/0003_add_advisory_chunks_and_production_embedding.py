"""Add advisory chunks table and additive production embedding columns

Revision ID: 0003_add_advisory_chunks
Revises: 0002_add_advisory_language
Create Date: 2026-09-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "0003_add_advisory_chunks"
down_revision: Union[str, None] = "0002_add_advisory_language"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add additive columns to marine_advisories
    op.execute("ALTER TABLE marine_advisories ADD COLUMN IF NOT EXISTS production_embedding vector(1024);")
    op.execute("ALTER TABLE marine_advisories ADD COLUMN IF NOT EXISTS embedding_model varchar(128);")
    op.execute("ALTER TABLE marine_advisories ADD COLUMN IF NOT EXISTS embedding_dimension integer;")
    op.execute("ALTER TABLE marine_advisories ADD COLUMN IF NOT EXISTS embedding_version varchar(32);")
    op.execute("ALTER TABLE marine_advisories ADD COLUMN IF NOT EXISTS embedding_provider varchar(64);")
    op.execute("ALTER TABLE marine_advisories ADD COLUMN IF NOT EXISTS embedded_at timestamptz;")
    op.execute("""
        ALTER TABLE marine_advisories ADD COLUMN IF NOT EXISTS search_vector tsvector
        GENERATED ALWAYS AS (
            setweight(to_tsvector('simple'::regconfig, coalesce(title, '')), 'A') ||
            setweight(to_tsvector('simple'::regconfig, coalesce(content, '')), 'B')
        ) STORED;
    """)

    # Indexes on marine_advisories
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_marine_advisories_production_embedding_hnsw
        ON marine_advisories USING hnsw (production_embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_marine_advisories_search_vector_gin
        ON marine_advisories USING gin (search_vector);
    """)

    # 2. Create marine_advisory_chunks table
    op.execute("""
        CREATE TABLE IF NOT EXISTS marine_advisory_chunks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            advisory_id UUID NOT NULL REFERENCES marine_advisories(id) ON DELETE CASCADE,
            chunk_index INTEGER NOT NULL,
            title VARCHAR(256) NOT NULL,
            content TEXT NOT NULL,
            language VARCHAR(16) NOT NULL DEFAULT 'en',
            sector VARCHAR(64),
            source_id VARCHAR(64) NOT NULL,
            published_at TIMESTAMPTZ NOT NULL,
            retrieved_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            metadata_json JSONB,
            embedding_1536 vector(1536),
            production_embedding vector(1024),
            search_vector tsvector GENERATED ALWAYS AS (
                setweight(to_tsvector('simple'::regconfig, coalesce(title, '')), 'A') ||
                setweight(to_tsvector('simple'::regconfig, coalesce(content, '')), 'B')
            ) STORED,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
    """)

    # Indexes on marine_advisory_chunks
    op.execute("CREATE INDEX IF NOT EXISTS ix_marine_advisory_chunks_advisory_id ON marine_advisory_chunks (advisory_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_advisory_chunks_advisory_idx ON marine_advisory_chunks (advisory_id, chunk_index);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marine_advisory_chunks_sector ON marine_advisory_chunks (sector);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marine_advisory_chunks_language ON marine_advisory_chunks (language);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_marine_advisory_chunks_published_at ON marine_advisory_chunks (published_at);")

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_marine_advisory_chunks_search_vector_gin
        ON marine_advisory_chunks USING gin (search_vector);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_marine_advisory_chunks_1536_hnsw
        ON marine_advisory_chunks USING hnsw (embedding_1536 vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_marine_advisory_chunks_prod_hnsw
        ON marine_advisory_chunks USING hnsw (production_embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS marine_advisory_chunks CASCADE;")
    op.execute("DROP INDEX IF EXISTS ix_marine_advisories_production_embedding_hnsw;")
    op.execute("DROP INDEX IF EXISTS ix_marine_advisories_search_vector_gin;")
    op.execute("ALTER TABLE marine_advisories DROP COLUMN IF EXISTS search_vector;")
    op.execute("ALTER TABLE marine_advisories DROP COLUMN IF EXISTS embedded_at;")
    op.execute("ALTER TABLE marine_advisories DROP COLUMN IF EXISTS embedding_provider;")
    op.execute("ALTER TABLE marine_advisories DROP COLUMN IF EXISTS embedding_version;")
    op.execute("ALTER TABLE marine_advisories DROP COLUMN IF EXISTS embedding_dimension;")
    op.execute("ALTER TABLE marine_advisories DROP COLUMN IF EXISTS embedding_model;")
    op.execute("ALTER TABLE marine_advisories DROP COLUMN IF EXISTS production_embedding;")
