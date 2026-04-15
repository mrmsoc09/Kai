"""Immutable audit model for analyst finding override decisions."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Column, ForeignKey, String, Text, event, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from .base import Base
from .mixins import UTCAwareDatetime


class FindingOverride(Base):
    """Immutable record of analyst include/exclude decisions."""

    __tablename__ = "finding_overrides"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    finding_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("scan_findings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    override_decision = Column(String(50), nullable=False, index=True)
    reason = Column(String(255), nullable=False)
    analyst_notes = Column(Text, nullable=True)
    overridden_by = Column(String(255), nullable=False, index=True)
    overridden_at = Column(
        UTCAwareDatetime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    immutable = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    def __repr__(self) -> str:
        return (
            "FindingOverride("
            f"id={self.id}, finding_id={self.finding_id}, decision={self.override_decision}, "
            f"overridden_by={self.overridden_by})"
        )


def _reject_override_mutation(*_args, **_kwargs) -> None:
    raise ValueError("FindingOverride records are immutable and cannot be modified or deleted")


event.listen(FindingOverride, "before_update", _reject_override_mutation)
event.listen(FindingOverride, "before_delete", _reject_override_mutation)

