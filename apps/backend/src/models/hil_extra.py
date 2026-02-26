from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, Column, Enum as SAEnum, Index, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from .base import Base
from .enums import SeverityEnum
from .mixins import SoftDeleteMixin, TimestampMixin


class ProgramScope(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "program_scopes"
    __table_args__ = (
        UniqueConstraint("program", name="uq_program_scopes_program"),
        CheckConstraint("btrim(program) <> ''", name="program_scopes_program_not_empty"),
        Index("ix_program_scopes_is_deleted", "is_deleted"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program = Column(Text, nullable=False)
    allowed_assets = Column(ARRAY(Text), nullable=True)
    excluded_assets = Column(ARRAY(Text), nullable=True)
    allowed_domains = Column(ARRAY(Text), nullable=True)
    excluded_domains = Column(ARRAY(Text), nullable=True)
    min_severity = Column(
        SAEnum(SeverityEnum, name="program_scope_min_severity_enum", native_enum=True, create_constraint=True),
        nullable=True,
    )
    notes = Column(Text, nullable=True)
