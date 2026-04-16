"""Phase 2 — evidence lifecycle state machine, validation records, approval-evidence links.

Revision ID: 0027_phase2_evidence_lifecycle
Revises: 02076b75458b
Create Date: 2026-04-15

Changes:
- structured_evidence: add lifecycle_status, lifecycle_transitioned_at, lifecycle_actor
- structured_evidence: add replay_* columns (request_response_uri, command_transcript_uri,
  screen_recording_uri, reproduction_steps, terminal_ref)
- Create evidence_validations table
- Create approval_evidence_links table
- Appropriate indexes on all new tables and columns
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0027_phase2_evidence_lifecycle"
down_revision = "02076b75458b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # structured_evidence — lifecycle columns
    # ------------------------------------------------------------------
    op.add_column(
        "structured_evidence",
        sa.Column(
            "lifecycle_status",
            sa.Text(),
            nullable=False,
            server_default="COLLECTED",
        ),
    )
    op.add_column(
        "structured_evidence",
        sa.Column(
            "lifecycle_transitioned_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "structured_evidence",
        sa.Column("lifecycle_actor", sa.Text(), nullable=True),
    )

    # structured_evidence — replay columns
    op.add_column(
        "structured_evidence",
        sa.Column("replay_request_response_uri", sa.Text(), nullable=True),
    )
    op.add_column(
        "structured_evidence",
        sa.Column("replay_command_transcript_uri", sa.Text(), nullable=True),
    )
    op.add_column(
        "structured_evidence",
        sa.Column("replay_screen_recording_uri", sa.Text(), nullable=True),
    )
    op.add_column(
        "structured_evidence",
        sa.Column("replay_reproduction_steps", sa.Text(), nullable=True),
    )
    op.add_column(
        "structured_evidence",
        sa.Column("replay_terminal_ref", sa.Text(), nullable=True),
    )

    op.create_index(
        "ix_structured_evidence_lifecycle_status",
        "structured_evidence",
        ["lifecycle_status"],
    )

    # ------------------------------------------------------------------
    # evidence_validations table
    # ------------------------------------------------------------------
    op.create_table(
        "evidence_validations",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "evidence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("structured_evidence.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaign_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "finding_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("findings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor", sa.Text(), nullable=False),
        sa.Column("validation_method", sa.Text(), nullable=False),
        sa.Column(
            "validation_outcome",
            sa.Text(),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "validated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "validation_outcome IN ('CONFIRMED', 'INCONCLUSIVE', 'REJECTED', 'NOISE')",
            name="evidence_validations_outcome_allowed",
        ),
    )

    op.create_index(
        "ix_evidence_validations_evidence_id", "evidence_validations", ["evidence_id"]
    )
    op.create_index(
        "ix_evidence_validations_campaign_id", "evidence_validations", ["campaign_id"]
    )
    op.create_index(
        "ix_evidence_validations_tenant_id", "evidence_validations", ["tenant_id"]
    )
    op.create_index(
        "ix_evidence_validations_validated_at", "evidence_validations", ["validated_at"]
    )
    op.create_index(
        "ix_evidence_validations_validation_outcome",
        "evidence_validations",
        ["validation_outcome"],
    )

    # ------------------------------------------------------------------
    # approval_evidence_links table
    # ------------------------------------------------------------------
    op.create_table(
        "approval_evidence_links",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "approval_gate_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("approval_gates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "evidence_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("structured_evidence.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "validation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("evidence_validations.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "campaign_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("campaign_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("linked_by", sa.Text(), nullable=False),
        sa.Column("link_reason", sa.Text(), nullable=True),
        sa.Column("reviewer_intention_snapshot", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    op.create_index(
        "ix_approval_evidence_links_approval_gate_id",
        "approval_evidence_links",
        ["approval_gate_id"],
    )
    op.create_index(
        "ix_approval_evidence_links_evidence_id",
        "approval_evidence_links",
        ["evidence_id"],
    )
    op.create_index(
        "ix_approval_evidence_links_validation_id",
        "approval_evidence_links",
        ["validation_id"],
    )
    op.create_index(
        "ix_approval_evidence_links_campaign_id",
        "approval_evidence_links",
        ["campaign_id"],
    )


def downgrade() -> None:
    # Drop tables first (they FK into structured_evidence)
    op.drop_table("approval_evidence_links")
    op.drop_table("evidence_validations")

    # Drop indexes added to structured_evidence
    op.drop_index("ix_structured_evidence_lifecycle_status", table_name="structured_evidence")

    # Drop columns added to structured_evidence
    op.drop_column("structured_evidence", "replay_terminal_ref")
    op.drop_column("structured_evidence", "replay_reproduction_steps")
    op.drop_column("structured_evidence", "replay_screen_recording_uri")
    op.drop_column("structured_evidence", "replay_command_transcript_uri")
    op.drop_column("structured_evidence", "replay_request_response_uri")
    op.drop_column("structured_evidence", "lifecycle_actor")
    op.drop_column("structured_evidence", "lifecycle_transitioned_at")
    op.drop_column("structured_evidence", "lifecycle_status")
