from __future__ import annotations

import uuid

from sqlalchemy import Column, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base
from .mixins import UTCAwareDatetime
from sqlalchemy import func


class ApprovalEvidenceLink(Base):
    """Linkage record binding an ApprovalGate decision to evidence and/or
    validation records.

    Provides a durable audit trail: when an approval gate is decided, the
    operator (or system) can attach pointers to the evidence and validation
    records that justified the decision.  The ``reviewer_intention_snapshot``
    column copies the gate's ``reviewer_intention`` at link-creation time so
    the audit trail remains intact even if the gate record is later mutated.
    """

    __tablename__ = "approval_evidence_links"
    __table_args__ = (
        Index("ix_approval_evidence_links_approval_gate_id", "approval_gate_id"),
        Index("ix_approval_evidence_links_evidence_id", "evidence_id"),
        Index("ix_approval_evidence_links_validation_id", "validation_id"),
        Index("ix_approval_evidence_links_campaign_id", "campaign_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    approval_gate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("approval_gates.id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_id = Column(
        UUID(as_uuid=True),
        ForeignKey("structured_evidence.id", ondelete="CASCADE"),
        nullable=True,
    )
    validation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("evidence_validations.id", ondelete="CASCADE"),
        nullable=True,
    )
    campaign_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaign_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    linked_by = Column(Text, nullable=False)
    link_reason = Column(Text, nullable=True)
    # Snapshot of gate.reviewer_intention at link-creation time.  Immutable
    # after insert so the audit trail stays valid even if the gate is later edited.
    reviewer_intention_snapshot = Column(Text, nullable=True)
    created_at = Column(UTCAwareDatetime, nullable=False, server_default=func.now())

    approval_gate = relationship(
        "ApprovalGate",
        foreign_keys=[approval_gate_id],
    )
    evidence = relationship(
        "StructuredEvidence",
        back_populates="approval_links",
        foreign_keys=[evidence_id],
    )
    validation = relationship(
        "EvidenceValidation",
        back_populates="approval_links",
        foreign_keys=[validation_id],
    )
