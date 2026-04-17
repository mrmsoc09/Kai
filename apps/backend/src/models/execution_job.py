from __future__ import annotations

from sqlalchemy import CheckConstraint, Column, Index, Integer, Text

from .base import Base
from .mixins import UTCAwareDatetime


class ExecutionJobRow(Base):
    """Persistent execution job record.

    Mirrors the in-memory ExecutionJob dataclass but survives restarts and is
    visible across Celery workers.  The job_id is a UUID string kept as TEXT
    to match the in-memory dataclass without requiring UUID column mapping.
    """

    __tablename__ = "execution_jobs"
    __table_args__ = (
        CheckConstraint(
            "state IN ('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'RETRYING', 'CANCELED')",
            name="execution_jobs_state_allowed",
        ),
        CheckConstraint("attempt >= 0", name="execution_jobs_attempt_non_negative"),
        CheckConstraint("max_attempts >= 1", name="execution_jobs_max_attempts_positive"),
        Index("ix_execution_jobs_campaign_id", "campaign_id"),
        Index("ix_execution_jobs_state", "state"),
    )

    id = Column(Text, primary_key=True)  # UUID string
    campaign_id = Column(Text, nullable=False)
    tool_name = Column(Text, nullable=False)
    target = Column(Text, nullable=False)
    state = Column(Text, nullable=False, default="PENDING")
    attempt = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    error = Column(Text, nullable=True)
    created_at = Column(UTCAwareDatetime, nullable=False)
    updated_at = Column(UTCAwareDatetime, nullable=False)
