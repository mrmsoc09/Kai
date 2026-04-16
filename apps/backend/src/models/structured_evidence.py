from __future__ import annotations

import uuid

from sqlalchemy import Column, Float, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base
from .mixins import TimestampMixin, UTCAwareDatetime


class StructuredEvidence(Base, TimestampMixin):
    __tablename__ = "structured_evidence"
    __table_args__ = (
        Index("ix_structured_evidence_campaign_id", "campaign_id"),
        Index("ix_structured_evidence_finding_id", "finding_id"),
        Index("ix_structured_evidence_validation_status", "validation_status"),
        Index("ix_structured_evidence_collected_at", "collected_at"),
        Index("ix_structured_evidence_tenant_id", "tenant_id"),
        Index("ix_structured_evidence_lifecycle_status", "lifecycle_status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)
    campaign_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaign_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    # finding_id references hil.py Finding table (uuid PK)
    finding_id = Column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="SET NULL"),
        nullable=True,
    )
    evidence_type = Column(Text, nullable=False)
    source_phase = Column(Text, nullable=True)
    collected_at = Column(UTCAwareDatetime, nullable=False)
    collected_by = Column(Text, nullable=False)
    artifact_uri = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    # Phase 1 backward-compat status field
    validation_status = Column(Text, nullable=False, server_default="PENDING")

    # Phase 2 — evidence lifecycle state machine
    lifecycle_status = Column(Text, nullable=False, server_default="COLLECTED")
    lifecycle_transitioned_at = Column(UTCAwareDatetime, nullable=True)
    lifecycle_actor = Column(Text, nullable=True)

    # Phase 2 — replay artifact references (populated by replay engine or manually)
    replay_request_response_uri = Column(Text, nullable=True)
    replay_command_transcript_uri = Column(Text, nullable=True)
    replay_screen_recording_uri = Column(Text, nullable=True)
    replay_reproduction_steps = Column(Text, nullable=True)
    replay_terminal_ref = Column(Text, nullable=True)

    campaign = relationship("CampaignRun", foreign_keys=[campaign_id])
    finding = relationship("Finding", foreign_keys=[finding_id])
    validations = relationship(
        "EvidenceValidation",
        back_populates="evidence",
        cascade="all, delete-orphan",
        foreign_keys="EvidenceValidation.evidence_id",
    )
    approval_links = relationship(
        "ApprovalEvidenceLink",
        back_populates="evidence",
        cascade="all, delete-orphan",
        foreign_keys="ApprovalEvidenceLink.evidence_id",
    )
