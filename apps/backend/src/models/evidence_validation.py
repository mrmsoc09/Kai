from __future__ import annotations

import uuid

from sqlalchemy import Column, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base
from .mixins import UTCAwareDatetime
from sqlalchemy import func


class EvidenceValidation(Base):
    """Human or operator validation record attached to a piece of StructuredEvidence.

    This is distinct from the legacy ``validation_status`` column on
    StructuredEvidence — each validation record captures one discrete
    review action (manual, automated, reproduction, peer-review) with a
    named actor and an outcome.  Multiple records can accumulate per evidence
    item over its lifecycle.
    """

    __tablename__ = "evidence_validations"
    __table_args__ = (
        Index("ix_evidence_validations_evidence_id", "evidence_id"),
        Index("ix_evidence_validations_campaign_id", "campaign_id"),
        Index("ix_evidence_validations_tenant_id", "tenant_id"),
        Index("ix_evidence_validations_validated_at", "validated_at"),
        Index("ix_evidence_validations_validation_outcome", "validation_outcome"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evidence_id = Column(
        UUID(as_uuid=True),
        ForeignKey("structured_evidence.id", ondelete="CASCADE"),
        nullable=False,
    )
    campaign_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaign_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    finding_id = Column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="SET NULL"),
        nullable=True,
    )
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor = Column(Text, nullable=False)
    # e.g. "manual_review", "automated_check", "reproduction", "peer_review"
    validation_method = Column(Text, nullable=False)
    # CHECK constraint enforced at DB level in migration; service layer also guards
    validation_outcome = Column(Text, nullable=False)
    notes = Column(Text, nullable=True)
    validated_at = Column(UTCAwareDatetime, nullable=False, server_default=func.now())

    evidence = relationship(
        "StructuredEvidence",
        back_populates="validations",
        foreign_keys=[evidence_id],
    )
    approval_links = relationship(
        "ApprovalEvidenceLink",
        back_populates="validation",
        cascade="all, delete-orphan",
        foreign_keys="ApprovalEvidenceLink.validation_id",
    )
