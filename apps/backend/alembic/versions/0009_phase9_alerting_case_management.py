"""phase 9 alerting and case management persistence

Revision ID: 0009_phase9_alerting_case_management
Revises: 0008_phase7_prediction_selection_engine
Create Date: 2026-03-14 10:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0009_phase9_alerting_case_management"
down_revision = "0008_phase7_prediction_selection_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_alert_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "program_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("programs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scope_target_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scope_targets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "workflow_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "analyst_queue_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyst_queue_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "prediction_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vulnerability_prediction_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "recommendation_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_recommendation_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "submission_draft_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("submission_drafts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("alert_type", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("urgency", sa.Text(), nullable=False),
        sa.Column("alert_fingerprint", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("reasoning_summary", sa.Text(), nullable=True),
        sa.Column(
            "supporting_signal_ids_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        sa.Column(
            "supporting_record_ids_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'::json"),
        ),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'OPEN'")),
        sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "first_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "last_seen_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("acknowledged_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.Text(), nullable=True),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "btrim(alert_type) <> ''",
            name="notification_alert_records_alert_type_not_empty",
        ),
        sa.CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="notification_alert_records_severity_allowed",
        ),
        sa.CheckConstraint(
            "urgency IN ('LOW', 'MEDIUM', 'HIGH', 'IMMEDIATE')",
            name="notification_alert_records_urgency_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'ACKNOWLEDGED', 'SUPPRESSED', 'RESOLVED')",
            name="notification_alert_records_status_allowed",
        ),
        sa.CheckConstraint(
            "occurrence_count >= 1",
            name="notification_alert_records_occurrence_positive",
        ),
        sa.CheckConstraint(
            "btrim(alert_fingerprint) <> ''",
            name="notification_alert_records_fingerprint_not_empty",
        ),
    )
    op.create_index(
        "ix_notification_alert_records_program_id",
        "notification_alert_records",
        ["program_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_alert_records_scope_target_id",
        "notification_alert_records",
        ["scope_target_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_alert_records_queue_item_id",
        "notification_alert_records",
        ["analyst_queue_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_alert_records_prediction_id",
        "notification_alert_records",
        ["prediction_record_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_alert_records_recommendation_id",
        "notification_alert_records",
        ["recommendation_record_id"],
        unique=False,
    )
    op.create_index(
        "ix_notification_alert_records_status",
        "notification_alert_records",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_notification_alert_records_severity",
        "notification_alert_records",
        ["severity"],
        unique=False,
    )
    op.create_index(
        "ix_notification_alert_records_urgency",
        "notification_alert_records",
        ["urgency"],
        unique=False,
    )
    op.create_index(
        "ix_notification_alert_records_fingerprint",
        "notification_alert_records",
        ["alert_fingerprint"],
        unique=False,
    )
    op.create_index(
        "ix_notification_alert_records_last_seen_at",
        "notification_alert_records",
        ["last_seen_at"],
        unique=False,
    )

    op.create_table(
        "analyst_case_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "program_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("programs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "scope_target_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scope_targets.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "workflow_run_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "alert_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("notification_alert_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "analyst_queue_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyst_queue_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "prediction_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("vulnerability_prediction_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "recommendation_record_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("workflow_recommendation_records.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "submission_draft_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("submission_drafts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("reasoning_summary", sa.Text(), nullable=True),
        sa.Column("priority", sa.Text(), nullable=False, server_default=sa.text("'MEDIUM'")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'new'")),
        sa.Column("owner", sa.Text(), nullable=True),
        sa.Column("last_actor", sa.Text(), nullable=True),
        sa.Column("assigned_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_transition_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("closed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("closure_reason", sa.Text(), nullable=True),
        sa.Column("evidence_refs_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("triage_notes_json", sa.JSON(), nullable=False, server_default=sa.text("'[]'::json")),
        sa.Column("details_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="analyst_case_records_priority_allowed",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'new', "
            "'acknowledged', "
            "'triaging', "
            "'needs_manual_validation', "
            "'ready_for_report', "
            "'dismissed', "
            "'duplicate', "
            "'escalated', "
            "'submitted', "
            "'closed'"
            ")",
            name="analyst_case_records_status_allowed",
        ),
        sa.CheckConstraint(
            "btrim(title) <> ''",
            name="analyst_case_records_title_not_empty",
        ),
    )
    op.create_index(
        "ix_analyst_case_records_program_id",
        "analyst_case_records",
        ["program_id"],
        unique=False,
    )
    op.create_index(
        "ix_analyst_case_records_scope_target_id",
        "analyst_case_records",
        ["scope_target_id"],
        unique=False,
    )
    op.create_index(
        "ix_analyst_case_records_alert_id",
        "analyst_case_records",
        ["alert_id"],
        unique=False,
    )
    op.create_index(
        "ix_analyst_case_records_queue_item_id",
        "analyst_case_records",
        ["analyst_queue_item_id"],
        unique=False,
    )
    op.create_index(
        "ix_analyst_case_records_prediction_id",
        "analyst_case_records",
        ["prediction_record_id"],
        unique=False,
    )
    op.create_index(
        "ix_analyst_case_records_recommendation_id",
        "analyst_case_records",
        ["recommendation_record_id"],
        unique=False,
    )
    op.create_index(
        "ix_analyst_case_records_owner",
        "analyst_case_records",
        ["owner"],
        unique=False,
    )
    op.create_index(
        "ix_analyst_case_records_priority",
        "analyst_case_records",
        ["priority"],
        unique=False,
    )
    op.create_index(
        "ix_analyst_case_records_status",
        "analyst_case_records",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_analyst_case_records_last_transition_at",
        "analyst_case_records",
        ["last_transition_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_analyst_case_records_last_transition_at", table_name="analyst_case_records")
    op.drop_index("ix_analyst_case_records_status", table_name="analyst_case_records")
    op.drop_index("ix_analyst_case_records_priority", table_name="analyst_case_records")
    op.drop_index("ix_analyst_case_records_owner", table_name="analyst_case_records")
    op.drop_index("ix_analyst_case_records_recommendation_id", table_name="analyst_case_records")
    op.drop_index("ix_analyst_case_records_prediction_id", table_name="analyst_case_records")
    op.drop_index("ix_analyst_case_records_queue_item_id", table_name="analyst_case_records")
    op.drop_index("ix_analyst_case_records_alert_id", table_name="analyst_case_records")
    op.drop_index("ix_analyst_case_records_scope_target_id", table_name="analyst_case_records")
    op.drop_index("ix_analyst_case_records_program_id", table_name="analyst_case_records")
    op.drop_table("analyst_case_records")

    op.drop_index("ix_notification_alert_records_last_seen_at", table_name="notification_alert_records")
    op.drop_index("ix_notification_alert_records_fingerprint", table_name="notification_alert_records")
    op.drop_index("ix_notification_alert_records_urgency", table_name="notification_alert_records")
    op.drop_index("ix_notification_alert_records_severity", table_name="notification_alert_records")
    op.drop_index("ix_notification_alert_records_status", table_name="notification_alert_records")
    op.drop_index("ix_notification_alert_records_recommendation_id", table_name="notification_alert_records")
    op.drop_index("ix_notification_alert_records_prediction_id", table_name="notification_alert_records")
    op.drop_index("ix_notification_alert_records_queue_item_id", table_name="notification_alert_records")
    op.drop_index("ix_notification_alert_records_scope_target_id", table_name="notification_alert_records")
    op.drop_index("ix_notification_alert_records_program_id", table_name="notification_alert_records")
    op.drop_table("notification_alert_records")
