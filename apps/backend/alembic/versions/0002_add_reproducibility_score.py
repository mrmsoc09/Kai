"""add reproducibility_score to findings

Revision ID: 0002_add_reproducibility_score
Revises: 0001_phase2_base_schema
Create Date: 2026-02-26 01:05:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_add_reproducibility_score"
down_revision = "0001_phase2_base_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "findings",
        sa.Column("reproducibility_score", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("findings", "reproducibility_score")

