from __future__ import annotations

import uuid

from sqlalchemy import CheckConstraint, Column, Float, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID

from .base import Base
from .mixins import UTCAwareDatetime


class SignalScore(Base):
    __tablename__ = "signal_scores"
    __table_args__ = (
        Index("ix_signal_scores_campaign_id", "campaign_id"),
        Index("ix_signal_scores_finding_id", "finding_id"),
        Index("ix_signal_scores_scored_at", "scored_at"),
        Index("ix_signal_scores_tenant_id", "tenant_id"),
        CheckConstraint(
            "exploitability_score >= 0.0 AND exploitability_score <= 10.0",
            name="signal_scores_exploitability_range",
        ),
        CheckConstraint(
            "impact_score >= 0.0 AND impact_score <= 10.0",
            name="signal_scores_impact_range",
        ),
        CheckConstraint(
            "evidence_completeness >= 0.0 AND evidence_completeness <= 1.0",
            name="signal_scores_evidence_completeness_range",
        ),
        CheckConstraint(
            "novelty_score >= 0.0 AND novelty_score <= 1.0",
            name="signal_scores_novelty_range",
        ),
        CheckConstraint(
            "overall_priority >= 0.0 AND overall_priority <= 10.0",
            name="signal_scores_overall_priority_range",
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=True)
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
    exploitability_score = Column(Float, nullable=False)
    impact_score = Column(Float, nullable=False)
    evidence_completeness = Column(Float, nullable=False)
    novelty_score = Column(Float, nullable=False)
    overall_priority = Column(Float, nullable=False)
    score_rationale = Column(Text, nullable=True)
    scored_at = Column(UTCAwareDatetime, nullable=False)
    scored_by = Column(Text, nullable=False)
