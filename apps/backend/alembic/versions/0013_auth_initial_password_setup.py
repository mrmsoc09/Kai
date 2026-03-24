"""Add must_change_password to auth users

Revision ID: 0013_auth_initial_password_setup
Revises: 0012_auth_tenants_users_api_tokens
Create Date: 2026-03-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0013_auth_initial_password_setup"
down_revision = "0012_auth_tenants_users_api_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("must_change_password", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("users", "must_change_password")
