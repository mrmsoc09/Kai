"""Create rotating scan pool tables

Revision ID: 0015_scan_pool_tables
Revises: 0014_user_scan_queue_settings
Create Date: 2026-03-26

Creates:
    opportunity_scan_pools        — pool-level config and cycle tracking
    opportunity_scan_pool_entries — per-entry queue slots with round-robin ordering
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic
revision = "0015_scan_pool_tables"
down_revision = "0014_user_scan_queue_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------ #
    # opportunity_scan_pools                                               #
    # ------------------------------------------------------------------ #
    op.create_table(
        "opportunity_scan_pools",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("user_id", sa.Text(), nullable=True),
        # Pool lifecycle status.
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="paused",
        ),
        # Concurrency window.
        sa.Column(
            "min_concurrent",
            sa.Integer(),
            nullable=False,
            server_default="5",
        ),
        sa.Column(
            "max_concurrent",
            sa.Integer(),
            nullable=False,
            server_default="7",
        ),
        # Cycle tracking.
        sa.Column(
            "current_cycle",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "cycle_started_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_cycle_completed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.Column("target_cycle_days", sa.Integer(), nullable=True),
        # TimestampMixin columns.
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # Primary key.
        sa.PrimaryKeyConstraint("id", name="pk_opportunity_scan_pools"),
        # Constraints.
        sa.CheckConstraint(
            "status IN ('active', 'paused', 'stopped')",
            name="ck_opportunity_scan_pools_opportunity_scan_pools_status_allowed",
        ),
        sa.CheckConstraint(
            "min_concurrent >= 1",
            name="ck_osp_min_concurrent_ge_1",
        ),
        sa.CheckConstraint(
            "max_concurrent >= 1 AND max_concurrent <= 25",
            name="ck_osp_max_concurrent_range",
        ),
        sa.CheckConstraint(
            "min_concurrent <= max_concurrent",
            name="ck_opportunity_scan_pools_opportunity_scan_pools_min_le_max",
        ),
    )

    # ------------------------------------------------------------------ #
    # opportunity_scan_pool_entries                                        #
    # ------------------------------------------------------------------ #
    op.create_table(
        "opportunity_scan_pool_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "pool_id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            "program_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "schedule_job_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            "queue_position",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="waiting",
        ),
        # Denormalized program display info.
        sa.Column("program_name", sa.Text(), nullable=False),
        sa.Column("platform", sa.Text(), nullable=True),
        sa.Column("program_handle", sa.Text(), nullable=True),
        # Per-entry cycle tracking.
        sa.Column(
            "total_scans_completed",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "current_cycle_scanned",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        # Timing and correlation.
        sa.Column("last_activated_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("last_scan_status", sa.Text(), nullable=True),
        sa.Column("last_celery_task_id", sa.Text(), nullable=True),
        sa.Column(
            "last_workflow_run_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        # TimestampMixin columns.
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # Primary key.
        sa.PrimaryKeyConstraint("id", name="pk_opportunity_scan_pool_entries"),
        # Foreign keys.
        sa.ForeignKeyConstraint(
            ["pool_id"],
            ["opportunity_scan_pools.id"],
            ondelete="CASCADE",
            name="fk_opportunity_scan_pool_entries_pool_id_opportunity_scan_pools",
        ),
        sa.ForeignKeyConstraint(
            ["program_id"],
            ["programs.id"],
            ondelete="CASCADE",
            name="fk_opportunity_scan_pool_entries_program_id_programs",
        ),
        sa.ForeignKeyConstraint(
            ["schedule_job_id"],
            ["hunt_schedule_jobs.id"],
            ondelete="SET NULL",
            name="fk_ospe_schedule_job_hunt_schedule_jobs",
        ),
        # Unique position within pool.
        sa.UniqueConstraint(
            "pool_id",
            "queue_position",
            name="uq_opportunity_scan_pool_entries_pool_position",
        ),
        # Status constraint.
        sa.CheckConstraint(
            "status IN ('waiting', 'active', 'paused', 'error')",
            name="ck_ospe_status_allowed",
        ),
    )

    # Composite index on (pool_id, status) for efficient queue lookups.
    op.create_index(
        "ix_opportunity_scan_pool_entries_pool_id_status",
        "opportunity_scan_pool_entries",
        ["pool_id", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_opportunity_scan_pool_entries_pool_id_status",
        table_name="opportunity_scan_pool_entries",
    )
    op.drop_table("opportunity_scan_pool_entries")
    op.drop_table("opportunity_scan_pools")
