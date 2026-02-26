from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, TIMESTAMP, func


class TimestampMixin:
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    is_deleted = Column(Boolean, nullable=False, default=False, server_default="false")
    deleted_at = Column(TIMESTAMP(timezone=True), nullable=True)

    def soft_delete(self) -> None:
        self.is_deleted = True
        self.deleted_at = datetime.now(timezone.utc)
