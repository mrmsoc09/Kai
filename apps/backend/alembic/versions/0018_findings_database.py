"""Add findings, scans, and submissions tables for results tracking and analytics.

Revision ID: 0018_findings_database
Revises: 0017_opportunity_credentials
Create Date: 2026-04-13

Creates:
    findings     — vulnerabilities discovered during scans
    scans        — scan execution metadata
    submissions  — submissions to bug bounty platforms
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0018_findings_database"
down_revision = "0017_opportunity_credentials"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create scans table (referenced by findings)
    op.create_table(
        "scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scan_name", sa.Text(), nullable=True),
        sa.Column("scan_type", sa.Text(), nullable=True),
        sa.Column("workflow_template_used", sa.Text(), nullable=True),
        sa.Column("requested_by", sa.Text(), nullable=True),
        sa.Column("triggered_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("available_scanning_modes", postgresql.JSON(), nullable=True),
        sa.Column("playbooks_executed", postgresql.JSON(), nullable=True),
        sa.Column("playbooks_skipped", postgresql.JSON(), nullable=True),
        sa.Column("credentials_used", postgresql.JSON(), nullable=True),
        sa.Column("total_findings_discovered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_findings_submitted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_findings_accepted", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_findings_rejected", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_payout_received", sa.Numeric(precision=10, scale=2), nullable=False, server_default="0"),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("completion_status", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("total_endpoints_tested", sa.Integer(), nullable=True),
        sa.Column("total_requests_made", sa.Integer(), nullable=True),
        sa.Column("rate_limit_hits", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.Column("last_updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'cancelled')",
            name="scans_status_allowed",
        ),
    )
    op.create_index("ix_scans_program_id", "scans", ["program_id"])
    op.create_index("ix_scans_status", "scans", ["status"])
    op.create_index("ix_scans_triggered_date", "scans", ["triggered_at"])

    # Create scan_findings table
    op.create_table(
        "scan_findings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("finding_identifier", sa.Text(), nullable=False, unique=True),
        sa.Column("program_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vulnerability_type", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=True),
        sa.Column("cvss_score", sa.Numeric(precision=3, scale=1), nullable=True),
        sa.Column("endpoint", sa.Text(), nullable=True),
        sa.Column("parameter_name", sa.Text(), nullable=True),
        sa.Column("http_method", sa.Text(), nullable=True),
        sa.Column("payload_used", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("proof_of_concept", sa.Text(), nullable=True),
        sa.Column("impact_description", sa.Text(), nullable=True),
        sa.Column("remediation_guidance", sa.Text(), nullable=True),
        sa.Column("screenshot_url", sa.Text(), nullable=True),
        sa.Column("video_recording_url", sa.Text(), nullable=True),
        sa.Column("logs_or_evidence", postgresql.JSON(), nullable=True),
        sa.Column("estimated_severity", sa.Text(), nullable=True),
        sa.Column("estimated_payout", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("actual_severity", sa.Text(), nullable=True),
        sa.Column("actual_payout", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("payout_currency", sa.Text(), nullable=False, server_default="USD"),
        sa.Column("payout_accuracy_percentage", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="discovered"),
        sa.Column("finding_state", sa.Text(), nullable=True),
        sa.Column("scanning_modes_used", postgresql.JSON(), nullable=True),
        sa.Column("playbook_id", sa.Text(), nullable=True),
        sa.Column("playbook_name", sa.Text(), nullable=True),
        sa.Column("ai_confidence_score", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("submitted_to_platform", sa.Text(), nullable=True),
        sa.Column("submission_id", sa.Text(), nullable=True),
        sa.Column("submission_status", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("platform_response_date", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("platform_decision_notes", sa.Text(), nullable=True),
        sa.Column("is_duplicate", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("duplicate_of_finding_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("deduplication_reason", sa.Text(), nullable=True),
        sa.Column("deduplication_confidence", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("discovered_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("payout_received_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("last_updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.Column("analyst_notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["program_id"], ["programs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["duplicate_of_finding_id"], ["scan_findings.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "severity IS NULL OR severity IN ('critical', 'high', 'medium', 'low')",
            name="findings_severity_allowed",
        ),
        sa.CheckConstraint(
            "status IN ('discovered', 'deduped', 'submitted', 'accepted', 'rejected', 'paid')",
            name="findings_status_allowed",
        ),
        sa.CheckConstraint(
            "finding_state IS NULL OR finding_state IN ('valid', 'false_positive', 'duplicate', 'out_of_scope')",
            name="findings_state_allowed",
        ),
        sa.CheckConstraint(
            "actual_payout IS NULL OR actual_payout >= 0",
            name="findings_payout_positive",
        ),
    )
    op.create_index("ix_scan_findings_program_id", "scan_findings", ["program_id"])
    op.create_index("ix_scan_findings_scan_id", "scan_findings", ["scan_id"])
    op.create_index("ix_scan_findings_vulnerability_type", "scan_findings", ["vulnerability_type"])
    op.create_index("ix_scan_findings_status", "scan_findings", ["status"])
    op.create_index("ix_scan_findings_submitted_to_platform", "scan_findings", ["submitted_to_platform"])
    op.create_index("ix_scan_findings_discovery_date", "scan_findings", ["discovered_at"])
    op.create_index("ix_scan_findings_playbook_id", "scan_findings", ["playbook_id"])
    op.create_index("ix_scan_findings_is_duplicate", "scan_findings", ["is_duplicate"])

    # Create submissions table
    op.create_table(
        "submissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("finding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submitted_to_platform", sa.Text(), nullable=False),
        sa.Column("platform_submission_id", sa.Text(), nullable=True),
        sa.Column("submission_url", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("current_status", sa.Text(), nullable=False),
        sa.Column("status_history", postgresql.JSON(), nullable=True),
        sa.Column("platform_notes", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("payout_amount", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("payout_currency", sa.Text(), nullable=False, server_default="USD"),
        sa.Column("payout_received_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("report_quality_score", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("report_feedback", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=True),
        sa.Column("updated_by", sa.Text(), nullable=True),
        sa.Column("last_updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["finding_id"], ["scan_findings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "current_status IN ('pending', 'accepted', 'rejected', 'duplicate', 'out_of_scope', 'paid')",
            name="submissions_status_allowed",
        ),
    )
    op.create_index("ix_submissions_finding_id", "submissions", ["finding_id"])
    op.create_index("ix_submissions_platform", "submissions", ["submitted_to_platform"])
    op.create_index("ix_submissions_status", "submissions", ["current_status"])
    op.create_index("ix_submissions_submitted_date", "submissions", ["submitted_at"])
    op.create_index("ix_submissions_payout_received", "submissions", ["payout_received_at"])


def downgrade() -> None:
    op.drop_index("ix_submissions_payout_received", table_name="submissions")
    op.drop_index("ix_submissions_submitted_date", table_name="submissions")
    op.drop_index("ix_submissions_status", table_name="submissions")
    op.drop_index("ix_submissions_platform", table_name="submissions")
    op.drop_index("ix_submissions_finding_id", table_name="submissions")
    op.drop_table("submissions")

    op.drop_index("ix_scan_findings_is_duplicate", table_name="scan_findings")
    op.drop_index("ix_scan_findings_playbook_id", table_name="scan_findings")
    op.drop_index("ix_scan_findings_discovery_date", table_name="scan_findings")
    op.drop_index("ix_scan_findings_submitted_to_platform", table_name="scan_findings")
    op.drop_index("ix_scan_findings_status", table_name="scan_findings")
    op.drop_index("ix_scan_findings_vulnerability_type", table_name="scan_findings")
    op.drop_index("ix_scan_findings_scan_id", table_name="scan_findings")
    op.drop_index("ix_scan_findings_program_id", table_name="scan_findings")
    op.drop_table("scan_findings")

    op.drop_index("ix_scans_triggered_date", table_name="scans")
    op.drop_index("ix_scans_status", table_name="scans")
    op.drop_index("ix_scans_program_id", table_name="scans")
    op.drop_table("scans")
