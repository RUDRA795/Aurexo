"""Initial PostGIS and pgvector schema for PFZ points and Marine Advisories

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-18 20:15:00.000000

"""
from typing import Sequence, Union

import geoalchemy2
import pgvector
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis;")
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 2. pfz_points table
    op.create_table(
        "pfz_points",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("pfz_id", sa.String(length=64), nullable=False),
        sa.Column(
            "geom",
            geoalchemy2.types.Geography(
                geometry_type="POINT",
                srid=4326,
                from_text="ST_GeogFromText",
                name="geography",
                nullable=False,
            ),
            nullable=False,
        ),
        sa.Column("sector", sa.String(length=64), nullable=False),
        sa.Column("depth_m", sa.Float(), nullable=True),
        sa.Column("landing_center", sa.String(length=128), nullable=True),
        sa.Column("distance_from_landing_center_km", sa.Float(), nullable=True),
        sa.Column("bearing_from_landing_center_deg", sa.Float(), nullable=True),
        sa.Column("forecast_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("wind_speed_ms", sa.Float(), nullable=True),
        sa.Column("wind_direction_deg", sa.Float(), nullable=True),
        sa.Column("source_id", sa.String(length=64), server_default="incois", nullable=False),
        sa.Column("access_tier", sa.String(length=64), server_default="text_advisory", nullable=False),
        sa.Column("raw_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pfz_id", "forecast_date", name="uq_pfz_points_id_forecast"),
    )
    op.create_index(op.f("ix_pfz_points_pfz_id"), "pfz_points", ["pfz_id"], unique=False)
    op.create_index(op.f("ix_pfz_points_sector"), "pfz_points", ["sector"], unique=False)
    op.create_index(op.f("ix_pfz_points_forecast_date"), "pfz_points", ["forecast_date"], unique=False)
    op.create_index(op.f("ix_pfz_points_valid_from"), "pfz_points", ["valid_from"], unique=False)
    op.create_index(op.f("ix_pfz_points_valid_until"), "pfz_points", ["valid_until"], unique=False)
    op.create_index(
        "ix_pfz_points_sector_valid",
        "pfz_points",
        ["sector", "valid_from", "valid_until"],
        unique=False,
    )

    # 3. marine_advisories table
    op.create_table(
        "marine_advisories",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_id", sa.String(length=64), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sector", sa.String(length=64), nullable=True),
        sa.Column("embedding", pgvector.sqlalchemy.Vector(1536), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_marine_advisories_source_id"), "marine_advisories", ["source_id"], unique=False)
    op.create_index(op.f("ix_marine_advisories_published_at"), "marine_advisories", ["published_at"], unique=False)
    op.create_index(op.f("ix_marine_advisories_sector"), "marine_advisories", ["sector"], unique=False)

    # HNSW index for vector cosine similarity search
    op.execute(
        """
        CREATE INDEX ix_marine_advisories_embedding_hnsw
        ON marine_advisories USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
        """
    )


def downgrade() -> None:
    op.drop_table("marine_advisories")
    op.drop_table("pfz_points")
