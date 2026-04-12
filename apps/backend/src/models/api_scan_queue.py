"""API-Scan Queue model — tracks scan queue length and quota allocation.

Stores queue metrics and API key allocation state for each planning cycle.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, Float, Integer, Text, UUID, CheckConstraint, Index
from sqlalchemy.ext.declarative import declarative_base

from .mixins import TimestampMixin

Base = declarative_base()


class APIScanQueue(Base, TimestampMixin):
    """Tracks API-Scan Queue state and quota allocation metrics.

    One entry per daily planning cycle (6AM PT).
    Used to enforce queue length limits and prevent bottlenecks.
    """

    __tablename__ = "api_scan_queues"
    __table_args__ = (
        CheckConstraint(
            "queue_length >= 0",
            name="api_scan_queues_queue_length_ge_0",
        ),
        CheckConstraint(
            "queue_length <= max_queue_length",
            name="api_scan_queues_queue_length_le_max",
        ),
        CheckConstraint(
            "status IN ('active', 'paused', 'exhausted')",
            name="api_scan_queues_status_allowed",
        ),
        Index("idx_api_scan_queues_planning_date", "planning_date"),
        Index("idx_api_scan_queues_status", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Planning cycle metadata
    planning_date = Column(DateTime(timezone=True), nullable=False, doc="Date of planning cycle (6AM PT)")
    planning_cycle = Column(Integer, nullable=False, doc="Sequential cycle number (1, 2, 3, ...)")

    # Queue state
    queue_length = Column(Integer, nullable=False, default=0, doc="Current number of entries in scan queue")
    max_queue_length = Column(Integer, nullable=False, default=100, doc="Maximum allowed queue length")
    target_queue_length = Column(Integer, nullable=False, default=50, doc="Target queue length")
    min_queue_length = Column(Integer, nullable=False, default=5, doc="Minimum queue length")

    # Status
    status = Column(
        Text,
        nullable=False,
        default="active",
        doc="active=accepting new scans, paused=at max limit, exhausted=out of quota",
    )

    # API Key metrics
    api_keys_available = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of API keys with remaining quota",
    )
    api_keys_exhausted = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of API keys with zero remaining quota",
    )

    # Quota allocation
    total_quota_allocated = Column(
        Float,
        nullable=False,
        default=0.0,
        doc="Total API calls allocated across all scans",
    )
    quota_per_scan = Column(
        Float,
        nullable=False,
        default=0.0,
        doc="Average quota allocated per scan entry",
    )

    # Alerts and actions
    at_capacity = Column(
        Integer,
        nullable=False,
        default=0,
        doc="1 if queue is at/above max_queue_length, 0 otherwise",
    )
    bottleneck_detected = Column(
        Integer,
        nullable=False,
        default=0,
        doc="1 if quota allocation indicates bottleneck risk",
    )

    # Notes/metadata
    notes = Column(
        Text,
        nullable=True,
        doc="Human-readable summary of queue state and actions",
    )

    def __repr__(self) -> str:
        return (
            f"APIScanQueue(id={self.id}, "
            f"planning_date={self.planning_date}, "
            f"queue_length={self.queue_length}/{self.max_queue_length}, "
            f"status={self.status})"
        )


class APIKeyDailyQuota(Base, TimestampMixin):
    """Tracks daily quota usage for a single API key.

    One entry per API key per day.
    Updated throughout the day as tools make API calls.
    """

    __tablename__ = "api_key_daily_quotas"
    __table_args__ = (
        CheckConstraint(
            "allocated_quota >= 0",
            name="api_key_daily_quotas_allocated_ge_0",
        ),
        CheckConstraint(
            "used_quota >= 0 AND used_quota <= allocated_quota",
            name="api_key_daily_quotas_used_le_allocated",
        ),
        CheckConstraint(
            "status IN ('active', 'exhausted', 'error')",
            name="api_key_daily_quotas_status_allowed",
        ),
        Index("idx_api_key_daily_quotas_date_key", "quota_date", "api_key_name"),
        Index("idx_api_key_daily_quotas_status", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Date and key identification
    quota_date = Column(
        DateTime(timezone=True),
        nullable=False,
        doc="Date quota was allocated (6AM PT)",
    )
    api_key_name = Column(
        Text,
        nullable=False,
        doc="API key name (e.g., OPENAI_API_KEY, SHODAN_API_KEY)",
    )

    # Quota allocation
    allocated_quota = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Total quota allocated for this key today",
    )
    used_quota = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Quota used so far today",
    )
    remaining_quota = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Quota remaining = allocated - used",
    )

    # Status
    status = Column(
        Text,
        nullable=False,
        default="active",
        doc="active=available, exhausted=no quota left, error=unavailable",
    )

    # Service metrics
    scans_allocated = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of scan entries allocated quota for this key",
    )
    scans_using = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of scans currently using this key",
    )

    # Notes
    notes = Column(
        Text,
        nullable=True,
        doc="Notes on quota usage, errors, etc.",
    )

    def __repr__(self) -> str:
        return (
            f"APIKeyDailyQuota(key={self.api_key_name}, "
            f"date={self.quota_date}, "
            f"used={self.used_quota}/{self.allocated_quota})"
        )
