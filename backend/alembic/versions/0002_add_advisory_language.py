"""Add language column and index to marine_advisories table

Revision ID: 0002_add_advisory_language
Revises: 0001_initial
Create Date: 2026-09-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002_add_advisory_language"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "marine_advisories",
        sa.Column("language", sa.String(length=16), server_default="en", nullable=False),
    )
    op.create_index(
        op.f("ix_marine_advisories_language"),
        "marine_advisories",
        ["language"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_marine_advisories_language"), table_name="marine_advisories")
    op.drop_column("marine_advisories", "language")
