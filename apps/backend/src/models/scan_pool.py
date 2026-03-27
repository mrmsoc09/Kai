"""SQLAlchemy models for the rotating opportunity scan pool.

Two tables:
- opportunity_scan_pools  — pool-level configuration and cycle tracking
- opportunity_scan_pool_entries — per-program queue slots
"""
from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base
from .mixins import TimestampMixin, UTCAwareDatetime


class OpportunityScanPool(Base, TimestampMixin):
    """Rotating scan pool: holds 75–125 bug bounty opportunities and drives
    round-robin scanning with configurable concurrency.
    """

    __tablename__ = "opportunity_scan_pools"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'paused', 'stopped')",
            name="opportunity_scan_pools_status_allowed",
        ),
        CheckConstraint(
            "min_concurrent >= 1",
            name="opportunity_scan_pools_min_concurrent_ge_1",
        ),
        CheckConstraint(
            "max_concurrent >= 1 AND max_concurrent <= 25",
            name="opportunity_scan_pools_max_concurrent_range",
        ),
        CheckConstraint(
            "min_concurrent <= max_concurrent",
            name="opportunity_scan_pools_min_le_max",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    # Optional owner reference — stored as plain text to avoid coupling to
    # a specific auth model table.
    user_id = Column(Text, nullable=True)

    # Pool lifecycle control.
    # "active"  → ticker advances the queue every 2 minutes.
    # "paused"  → no new scans started; in-progress scans finish naturally.
    # "stopped" → no new scans started; existing active entries stay active
    #             until manually resolved.
    status = Column(Text, nullable=False, server_default="paused")

    # Concurrency window.  min_concurrent is the target floor that advance_queue
    # tries to fill; max_concurrent is the hard ceiling.
    min_concurrent = Column(Integer, nullable=False, server_default="5")
    max_concurrent = Column(Integer, nullable=False, server_default="7")

    # Cycle tracking.  A "cycle" completes when every entry in the pool has been
    # scanned at least once since the last cycle reset.
    current_cycle = Column(Integer, nullable=False, server_default="0")
    cycle_started_at = Column(UTCAwareDatetime, nullable=True)
    last_cycle_completed_at = Column(UTCAwareDatetime, nullable=True)
    # Optional SLA: how many days a full cycle should take (for reporting).
    target_cycle_days = Column(Integer, nullable=True)

    entries = relationship(
        "OpportunityScanPoolEntry",
        back_populates="pool",
        order_by="OpportunityScanPoolEntry.queue_position",
    )


class OpportunityScanPoolEntry(Base, TimestampMixin):
    """One slot in a rotating scan pool queue.

    queue_position is 1-based and unique within a pool; advance_queue fills
    slots in ascending position order.  When an entry completes, it is
    re-queued at max_position + 1 (round-robin tail append).
    """

    __tablename__ = "opportunity_scan_pool_entries"
    __table_args__ = (
        UniqueConstraint(
            "pool_id",
            "queue_position",
            name="uq_opportunity_scan_pool_entries_pool_position",
        ),
        CheckConstraint(
            "status IN ('waiting', 'active', 'paused', 'error')",
            name="opportunity_scan_pool_entries_status_allowed",
        ),
        Index("ix_opportunity_scan_pool_entries_pool_id_status", "pool_id", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pool_id = Column(
        UUID(as_uuid=True),
        ForeignKey("opportunity_scan_pools.id", ondelete="CASCADE"),
        nullable=False,
    )
    # FK to programs table — nullable for manually-entered opportunities that
    # are not yet linked to a scraped program record.
    program_id = Column(
        UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=True,
    )
    # FK to hunt_schedule_jobs — required to actually dispatch a scan via
    # run_bug_bounty_schedule_task.  When NULL the entry cannot be activated.
    schedule_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hunt_schedule_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )

    # 1-based ordering within the pool.  Unique per pool (enforced by
    # uq_opportunity_scan_pool_entries_pool_position above).
    queue_position = Column(Integer, nullable=False, server_default="1")

    # Entry lifecycle status.
    # "waiting" → in queue, not currently scanning.
    # "active"  → scan dispatched to Celery; waiting for completion.
    # "paused"  → manually paused; will not be activated until resumed.
    # "error"   → last activation failed or timed out.
    status = Column(Text, nullable=False, server_default="waiting")

    # Denormalized program info so the queue view does not need a JOIN.
    program_name = Column(Text, nullable=False)
    platform = Column(Text, nullable=True)
    program_handle = Column(Text, nullable=True)

    # Per-entry cycle tracking.
    total_scans_completed = Column(Integer, nullable=False, server_default="0")
    # Reset to False when a new pool cycle begins; set True when this entry
    # completes a scan in the current cycle.
    current_cycle_scanned = Column(Boolean, nullable=False, server_default="false")

    # Timing and correlation metadata for status polling and diagnostics.
    last_activated_at = Column(UTCAwareDatetime, nullable=True)
    last_completed_at = Column(UTCAwareDatetime, nullable=True)
    # "completed" | "failed" | "timeout"
    last_scan_status = Column(Text, nullable=True)
    # Celery task ID returned by run_bug_bounty_schedule_task.delay(); used
    # for result-backend polling and cancellation.
    last_celery_task_id = Column(Text, nullable=True)
    last_workflow_run_id = Column(UUID(as_uuid=True), nullable=True)

    pool = relationship("OpportunityScanPool", back_populates="entries")
    schedule_job = relationship("HuntScheduleJob")
