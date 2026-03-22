"""Add auth tables: tenants, users, api_tokens

Revision ID: 0012_auth_tenants_users_api_tokens
Revises: 0011_phase10_5_specialized_agent_framework
Create Date: 2026-03-18
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0012_auth_tenants_users_api_tokens"
down_revision = "0011_phase10_5_specialized_agent_framework"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- tenants ---
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("config_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tenants_name", "tenants", ["name"], unique=True)

    # --- user_role enum ---
    user_role_enum = postgresql.ENUM(
        "admin", "analyst", "operator", "viewer",
        name="user_role_enum",
        create_type=False,
    )
    user_role_enum.create(op.get_bind(), checkfirst=True)

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(), nullable=False),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=True),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "role",
            postgresql.ENUM("admin", "analyst", "operator", "viewer", name="user_role_enum", create_type=False),
            nullable=False,
            server_default="viewer",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username", "tenant_id", name="uq_user_tenant_username"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])
    op.create_index("ix_users_username", "users", ["username"], unique=True)
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    # --- api_tokens ---
    op.create_table(
        "api_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_api_tokens_tenant_id", "api_tokens", ["tenant_id"])
    op.create_index("ix_api_tokens_token_hash", "api_tokens", ["token_hash"], unique=True)

    # --- approval_gates: ensure tenant_id + FK exist ---
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "approval_gates" in table_names:
        approval_gate_columns = {col["name"] for col in inspector.get_columns("approval_gates")}
        if "tenant_id" not in approval_gate_columns:
            op.add_column("approval_gates", sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True))
            op.create_index("ix_approval_gates_tenant_id", "approval_gates", ["tenant_id"], unique=False)

        inspector = sa.inspect(bind)
        foreign_keys = inspector.get_foreign_keys("approval_gates")
        fk_names = {fk.get("name") for fk in foreign_keys}
        if "fk_approval_gates_tenant_id" not in fk_names:
            op.create_foreign_key(
                "fk_approval_gates_tenant_id",
                "approval_gates",
                "tenants",
                ["tenant_id"],
                ["id"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    table_names = set(inspector.get_table_names())
    if "approval_gates" in table_names:
        foreign_keys = inspector.get_foreign_keys("approval_gates")
        fk_names = {fk.get("name") for fk in foreign_keys}
        if "fk_approval_gates_tenant_id" in fk_names:
            op.drop_constraint("fk_approval_gates_tenant_id", "approval_gates", type_="foreignkey")

        indexes = inspector.get_indexes("approval_gates")
        index_names = {idx.get("name") for idx in indexes}
        if "ix_approval_gates_tenant_id" in index_names:
            op.drop_index("ix_approval_gates_tenant_id", table_name="approval_gates")

        approval_gate_columns = {col["name"] for col in inspector.get_columns("approval_gates")}
        if "tenant_id" in approval_gate_columns:
            op.drop_column("approval_gates", "tenant_id")

    op.drop_index("ix_api_tokens_token_hash", table_name="api_tokens")
    op.drop_index("ix_api_tokens_tenant_id", table_name="api_tokens")
    op.drop_table("api_tokens")

    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_username", table_name="users")
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_table("users")

    sa.Enum(name="user_role_enum").drop(op.get_bind(), checkfirst=True)

    op.drop_index("ix_tenants_name", table_name="tenants")
    op.drop_table("tenants")
