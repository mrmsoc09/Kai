from __future__ import annotations

import uuid

from sqlalchemy import Column, Integer, JSON, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID

from .base import Base
from .mixins import TimestampMixin, UTCAwareDatetime


class ProgramSchedule(Base, TimestampMixin):
    """Schedule descriptor for periodic program scanning.

    Created/upserted by ProgramIngestionService.schedule_program_db().
    Consumed by the Celery beat scheduler to dispatch hunt jobs.
    """

    __tablename__ = "program_schedules"
    __table_args__ = (
        UniqueConstraint("program_handle", name="uq_program_schedules_handle"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_handle = Column(Text, nullable=False)
    platform = Column(Text, nullable=False)
    # JSON list of normalized target strings
    targets = Column(JSON, nullable=False, default=list)
    interval_hours = Column(Integer, nullable=False, default=24)
    next_run_at = Column(UTCAwareDatetime, nullable=False)
    last_run_at = Column(UTCAwareDatetime, nullable=True)
