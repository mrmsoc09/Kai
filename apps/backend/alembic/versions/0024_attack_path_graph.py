"""Create attack_path_nodes and attack_path_edges tables.

Revision ID: 0024_attack_path_graph
Revises: 0023_structured_evidence
Create Date: 2026-04-15
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0024_attack_path_graph"
down_revision = "0023_structured_evidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attack_path_nodes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("mission_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("node_type", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "node_type IN ('asset','endpoint','parameter','finding','evidence','auth_boundary')",
            name="attack_path_nodes_node_type_allowed",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_attack_path_nodes_mission_id", "attack_path_nodes", ["mission_id"])
    op.create_index("ix_attack_path_nodes_node_type", "attack_path_nodes", ["node_type"])

    op.create_table(
        "attack_path_edges",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "source_node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("attack_path_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("attack_path_nodes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("relationship_type", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.5"),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "relationship_type IN ('leads_to','exploits','bypasses','discovers')",
            name="attack_path_edges_relationship_type_allowed",
        ),
        sa.CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="attack_path_edges_confidence_range",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_attack_path_edges_source_node_id", "attack_path_edges", ["source_node_id"]
    )
    op.create_index(
        "ix_attack_path_edges_target_node_id", "attack_path_edges", ["target_node_id"]
    )
    op.create_index(
        "ix_attack_path_edges_relationship_type", "attack_path_edges", ["relationship_type"]
    )


def downgrade() -> None:
    op.drop_index("ix_attack_path_edges_relationship_type", table_name="attack_path_edges")
    op.drop_index("ix_attack_path_edges_target_node_id", table_name="attack_path_edges")
    op.drop_index("ix_attack_path_edges_source_node_id", table_name="attack_path_edges")
    op.drop_table("attack_path_edges")

    op.drop_index("ix_attack_path_nodes_node_type", table_name="attack_path_nodes")
    op.drop_index("ix_attack_path_nodes_mission_id", table_name="attack_path_nodes")
    op.drop_table("attack_path_nodes")
