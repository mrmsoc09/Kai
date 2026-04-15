"""ORM model for immutable scope violation audit trail.

Records all out-of-scope detection events for compliance and debugging.
Violations are immutable once created — no update operations allowed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, Column, ForeignKey, String, Text, event, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID

from .base import Base
from .mixins import UTCAwareDatetime


class ScopeViolation(Base):
    """Immutable record of scope violations detected during scanning.

    Each violation represents an attempted out-of-scope request that was
    caught by ScopeValidator before execution. Records cannot be modified
    after creation (compliance requirement).
    """

    __tablename__ = "scope_violations"

    id = Column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    program_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    scan_id = Column(
        PGUUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Violation type (from ScopeViolationType enum)
    violation_type = Column(String(50), nullable=False, index=True)

    # Human-readable reason for violation
    reason = Column(Text, nullable=False)

    # The target that caused the violation (URL, endpoint, IP, etc.)
    target = Column(String(1000), nullable=True)

    # Timestamp of detection (server-set, immutable)
    detected_at = Column(
        UTCAwareDatetime,
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    # Who/what detected this violation
    created_by = Column(
        String(255),
        nullable=False,
        server_default="safety_system",
    )

    # Explicit immutable marker for compliance and query filtering.
    immutable = Column(
        Boolean,
        nullable=False,
        default=True,
        server_default=text("true"),
    )

    def __repr__(self) -> str:
        return (
            f"<ScopeViolation(id={self.id}, type={self.violation_type}, "
            f"target={self.target}, detected_at={self.detected_at})>"
        )


def _reject_scope_violation_mutation(*_args, **_kwargs) -> None:
    """Prevent updates/deletes to immutable scope audit records."""
    raise ValueError("ScopeViolation records are immutable and cannot be modified or deleted")


event.listen(ScopeViolation, "before_update", _reject_scope_violation_mutation)
event.listen(ScopeViolation, "before_delete", _reject_scope_violation_mutation)
