"""Add tenant_id columns and signal_score FK constraints for Phase 1 resources.

Revision ID: 0026_phase1_tenant_and_fk
Revises: 0025_signal_scores
Create Date: 2026-04-15

Changes:
- structured_evidence: add tenant_id (nullable UUID FK -> tenants.id) + index
- attack_path_nodes: add tenant_id (nullable UUID FK -> tenants.id) + index
- attack_path_edges: add tenant_id (nullable UUID FK -> tenants.id) + index
- signal_scores: add tenant_id (nullable UUID FK -> tenants.id) + index
- signal_scores: add FK campaign_id -> campaign_runs.id (SET NULL)
- signal_scores: add FK finding_id -> findings.id (SET NULL)

All new columns are nullable for backward compatibility with existing rows.
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0026_phase1_tenant_and_fk"
down_revision = "0025_signal_scores"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # structured_evidence — tenant_id                                     #
    # ------------------------------------------------------------------ #
    op.add_column(
        "structured_evidence",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_structured_evidence_tenant_id",
        "structured_evidence",
        "tenants",
        ["tenant_id"],
        ["id"],
    )
    op.create_index(
        "ix_structured_evidence_tenant_id",
        "structured_evidence",
        ["tenant_id"],
    )

    # ------------------------------------------------------------------ #
    # attack_path_nodes — tenant_id                                       #
    # ------------------------------------------------------------------ #
    op.add_column(
        "attack_path_nodes",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_attack_path_nodes_tenant_id",
        "attack_path_nodes",
        "tenants",
        ["tenant_id"],
        ["id"],
    )
    op.create_index(
        "ix_attack_path_nodes_tenant_id",
        "attack_path_nodes",
        ["tenant_id"],
    )

    # ------------------------------------------------------------------ #
    # attack_path_edges — tenant_id                                       #
    # ------------------------------------------------------------------ #
    op.add_column(
        "attack_path_edges",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_attack_path_edges_tenant_id",
        "attack_path_edges",
        "tenants",
        ["tenant_id"],
        ["id"],
    )
    op.create_index(
        "ix_attack_path_edges_tenant_id",
        "attack_path_edges",
        ["tenant_id"],
    )

    # ------------------------------------------------------------------ #
    # signal_scores — tenant_id + FK constraints on campaign_id/finding_id #
    # ------------------------------------------------------------------ #
    op.add_column(
        "signal_scores",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_signal_scores_tenant_id",
        "signal_scores",
        "tenants",
        ["tenant_id"],
        ["id"],
    )
    op.create_index(
        "ix_signal_scores_tenant_id",
        "signal_scores",
        ["tenant_id"],
    )
    op.create_foreign_key(
        "fk_signal_scores_campaign_id",
        "signal_scores",
        "campaign_runs",
        ["campaign_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_signal_scores_finding_id",
        "signal_scores",
        "findings",
        ["finding_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # ------------------------------------------------------------------ #
    # signal_scores — reverse in order                                    #
    # ------------------------------------------------------------------ #
    op.drop_constraint("fk_signal_scores_finding_id", "signal_scores", type_="foreignkey")
    op.drop_constraint("fk_signal_scores_campaign_id", "signal_scores", type_="foreignkey")
    op.drop_index("ix_signal_scores_tenant_id", table_name="signal_scores")
    op.drop_constraint("fk_signal_scores_tenant_id", "signal_scores", type_="foreignkey")
    op.drop_column("signal_scores", "tenant_id")

    # ------------------------------------------------------------------ #
    # attack_path_edges                                                   #
    # ------------------------------------------------------------------ #
    op.drop_index("ix_attack_path_edges_tenant_id", table_name="attack_path_edges")
    op.drop_constraint(
        "fk_attack_path_edges_tenant_id", "attack_path_edges", type_="foreignkey"
    )
    op.drop_column("attack_path_edges", "tenant_id")

    # ------------------------------------------------------------------ #
    # attack_path_nodes                                                   #
    # ------------------------------------------------------------------ #
    op.drop_index("ix_attack_path_nodes_tenant_id", table_name="attack_path_nodes")
    op.drop_constraint(
        "fk_attack_path_nodes_tenant_id", "attack_path_nodes", type_="foreignkey"
    )
    op.drop_column("attack_path_nodes", "tenant_id")

    # ------------------------------------------------------------------ #
    # structured_evidence                                                 #
    # ------------------------------------------------------------------ #
    op.drop_index("ix_structured_evidence_tenant_id", table_name="structured_evidence")
    op.drop_constraint(
        "fk_structured_evidence_tenant_id", "structured_evidence", type_="foreignkey"
    )
    op.drop_column("structured_evidence", "tenant_id")
