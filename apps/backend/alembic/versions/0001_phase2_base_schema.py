"""phase2_base_schema

Revision ID: 0001_phase2_base_schema
Revises:
Create Date: 2026-02-26 00:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0001_phase2_base_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    severity_enum = postgresql.ENUM(
        "INFO",
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
        name="severity_enum",
        create_type=False,
    )
    finding_status_enum = postgresql.ENUM(
        "NEW",
        "IN_REVIEW",
        "HIL_APPROVED",
        "SUBMITTED",
        "RESOLVED",
        "REJECTED",
        "DUPLICATE",
        name="finding_status_enum",
        create_type=False,
    )
    hil_approval_status_enum = postgresql.ENUM(
        "PENDING",
        "APPROVED",
        "REJECTED",
        name="hil_approval_status_enum",
        create_type=False,
    )
    program_scope_min_severity_enum = postgresql.ENUM(
        "INFO",
        "LOW",
        "MEDIUM",
        "HIGH",
        "CRITICAL",
        name="program_scope_min_severity_enum",
        create_type=False,
    )
    execution_status_enum = postgresql.ENUM(
        "PENDING",
        "COMPLETED",
        "FAILED",
        name="execution_status_enum",
        create_type=False,
    )

    bind = op.get_bind()
    severity_enum.create(bind, checkfirst=True)
    finding_status_enum.create(bind, checkfirst=True)
    hil_approval_status_enum.create(bind, checkfirst=True)
    program_scope_min_severity_enum.create(bind, checkfirst=True)
    execution_status_enum.create(bind, checkfirst=True)

    op.create_table(
        "findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program", sa.Text(), nullable=False),
        sa.Column("asset", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("severity", severity_enum, nullable=False),
        sa.Column("status", finding_status_enum, nullable=False, server_default="NEW"),
        sa.Column("scope_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("btrim(program) <> ''", name="ck_findings_finding_program_not_empty"),
        sa.CheckConstraint("btrim(asset) <> ''", name="ck_findings_finding_asset_not_empty"),
        sa.CheckConstraint("btrim(title) <> ''", name="ck_findings_finding_title_not_empty"),
        sa.CheckConstraint("btrim(description) <> ''", name="ck_findings_finding_description_not_empty"),
        sa.PrimaryKeyConstraint("id", name="pk_findings"),
    )
    op.create_index("ix_findings_is_deleted", "findings", ["is_deleted"], unique=False)

    op.create_table(
        "program_scopes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program", sa.Text(), nullable=False),
        sa.Column("allowed_assets", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("excluded_assets", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("allowed_domains", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("excluded_domains", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("min_severity", program_scope_min_severity_enum, nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("btrim(program) <> ''", name="ck_program_scopes_program_scopes_program_not_empty"),
        sa.PrimaryKeyConstraint("id", name="pk_program_scopes"),
        sa.UniqueConstraint("program", name="uq_program_scopes_program"),
    )
    op.create_index("ix_program_scopes_is_deleted", "program_scopes", ["is_deleted"], unique=False)

    op.create_table(
        "evidence",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("sha256", sa.LargeBinary(), nullable=False),
        sa.Column("meta", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("btrim(kind) <> ''", name="ck_evidence_evidence_kind_not_empty"),
        sa.CheckConstraint("btrim(uri) <> ''", name="ck_evidence_evidence_uri_not_empty"),
        sa.ForeignKeyConstraint(["finding_id"], ["findings.id"], name="fk_evidence_finding_id_findings", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_evidence"),
    )
    op.create_index("ix_evidence_finding_id", "evidence", ["finding_id"], unique=False)
    op.create_index("ix_evidence_is_deleted", "evidence", ["is_deleted"], unique=False)

    op.create_table(
        "hil_approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("approved_by", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("status", hil_approval_status_enum, nullable=False, server_default="PENDING"),
        sa.Column("checklist", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.CheckConstraint("btrim(approved_by) <> ''", name="ck_hil_approvals_hil_approvals_approved_by_not_empty"),
        sa.ForeignKeyConstraint(["finding_id"], ["findings.id"], name="fk_hil_approvals_finding_id_findings", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_hil_approvals"),
        sa.UniqueConstraint("finding_id", name="uq_hil_approvals_finding_id"),
    )
    op.create_index("ix_hil_approvals_is_deleted", "hil_approvals", ["is_deleted"], unique=False)

    op.create_table(
        "reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("content_hash", sa.LargeBinary(), nullable=False),
        sa.Column("manifest_hash", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["finding_id"], ["findings.id"], name="fk_reports_finding_id_findings", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_reports"),
    )
    op.create_index("ix_reports_finding_id", "reports", ["finding_id"], unique=False)
    op.create_index("ix_reports_is_deleted", "reports", ["is_deleted"], unique=False)

    op.create_table(
        "audit_merkle_roots",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("root_hash", sa.LargeBinary(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("deleted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_audit_merkle_roots"),
    )
    op.create_index("ix_audit_merkle_roots_is_deleted", "audit_merkle_roots", ["is_deleted"], unique=False)

    op.create_table(
        "execution_contexts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", execution_status_enum, nullable=False, server_default="PENDING"),
        sa.Column("response_payload", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("btrim(operation) <> ''", name="ck_execution_contexts_execution_contexts_operation_not_empty"),
        sa.PrimaryKeyConstraint("id", name="pk_execution_contexts"),
        sa.UniqueConstraint("transaction_id", name="uq_execution_contexts_transaction_id"),
        sa.UniqueConstraint(
            "operation",
            "resource_id",
            "idempotency_key",
            name="uq_execution_contexts_operation_resource_idempotency_key",
        ),
    )
    op.create_index("ix_execution_contexts_resource_id", "execution_contexts", ["resource_id"], unique=False)
    op.create_index("ix_execution_contexts_status", "execution_contexts", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_execution_contexts_status", table_name="execution_contexts")
    op.drop_index("ix_execution_contexts_resource_id", table_name="execution_contexts")
    op.drop_table("execution_contexts")

    op.drop_index("ix_audit_merkle_roots_is_deleted", table_name="audit_merkle_roots")
    op.drop_table("audit_merkle_roots")

    op.drop_index("ix_reports_is_deleted", table_name="reports")
    op.drop_index("ix_reports_finding_id", table_name="reports")
    op.drop_table("reports")

    op.drop_index("ix_hil_approvals_is_deleted", table_name="hil_approvals")
    op.drop_table("hil_approvals")

    op.drop_index("ix_evidence_is_deleted", table_name="evidence")
    op.drop_index("ix_evidence_finding_id", table_name="evidence")
    op.drop_table("evidence")

    op.drop_index("ix_program_scopes_is_deleted", table_name="program_scopes")
    op.drop_table("program_scopes")

    op.drop_index("ix_findings_is_deleted", table_name="findings")
    op.drop_table("findings")

    bind = op.get_bind()
    postgresql.ENUM(name="execution_status_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="program_scope_min_severity_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="hil_approval_status_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="finding_status_enum").drop(bind, checkfirst=True)
    postgresql.ENUM(name="severity_enum").drop(bind, checkfirst=True)
