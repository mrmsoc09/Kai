from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import CheckConstraint, Column, Enum as SAEnum, Index, JSON, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator

from .base import Base
from .enums import SeverityEnum
from .mixins import SoftDeleteMixin, TimestampMixin


class _PortableTextArray(TypeDecorator):
    """Text-array column that uses native ARRAY(Text) on PostgreSQL and JSON elsewhere.

    This allows SQLAlchemy models to use PostgreSQL ARRAY semantics while remaining
    schema-compatible with SQLite for test environments (where aiosqlite is used).
    """

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(ARRAY(Text))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value: Any, dialect: Dialect) -> Any:
        # PostgreSQL accepts lists natively; JSON backend wants the list serialised.
        return value

    def process_result_value(self, value: Any, dialect: Dialect) -> Any:
        return value


class ProgramScope(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "program_scopes"
    __table_args__ = (
        UniqueConstraint("program", name="uq_program_scopes_program"),
        CheckConstraint("btrim(program) <> ''", name="program_scopes_program_not_empty"),
        Index("ix_program_scopes_is_deleted", "is_deleted"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program = Column(Text, nullable=False)
    allowed_assets = Column(_PortableTextArray, nullable=True)
    excluded_assets = Column(_PortableTextArray, nullable=True)
    allowed_domains = Column(_PortableTextArray, nullable=True)
    excluded_domains = Column(_PortableTextArray, nullable=True)
    min_severity = Column(
        SAEnum(SeverityEnum, name="program_scope_min_severity_enum", native_enum=True, create_constraint=True),
        nullable=True,
    )
    notes = Column(Text, nullable=True)
