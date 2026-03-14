from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, Column, TIMESTAMP, func
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import TypeDecorator


class UTCAwareDatetime(TypeDecorator):
    """TIMESTAMP column that always returns UTC-aware ``datetime`` objects.

    PostgreSQL (via asyncpg) natively returns timezone-aware datetimes.
    SQLite (via aiosqlite) returns naive UTC datetimes because SQLite has no
    timezone concept.  This TypeDecorator adds ``timezone.utc`` to any naive
    value on read so that service-layer comparisons against
    ``datetime.now(timezone.utc)`` never raise ``TypeError``.

    The write path is unchanged: values are stored exactly as SQLAlchemy would
    have stored them without this decorator.
    """

    impl = TIMESTAMP(timezone=True)
    cache_ok = True

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class TimestampMixin:
    created_at = Column(UTCAwareDatetime, server_default=func.now(), nullable=False)
    updated_at = Column(
        UTCAwareDatetime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    is_deleted = Column(Boolean, nullable=False, default=False, server_default="false")
    deleted_at = Column(UTCAwareDatetime, nullable=True)

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
