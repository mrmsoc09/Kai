from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Enum as SAEnum,
    ForeignKey,
    Index,
    JSON,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base
from .enums import IntentionSourceEnum, IntentionTypeEnum, RiskPolicyClassEnum
from .mixins import TimestampMixin


class IntentionRecord(Base, TimestampMixin):
    __tablename__ = "intention_records"
    __table_args__ = (
        CheckConstraint("btrim(initiated_by) <> ''", name="intention_initiated_by_not_empty"),
        CheckConstraint("btrim(declared_goal) <> ''", name="intention_declared_goal_not_empty"),
        Index("ix_intention_records_campaign_id", "campaign_id"),
        Index("ix_intention_records_branch_id", "branch_id"),
        Index("ix_intention_records_phase_job_id", "phase_job_id"),
        Index("ix_intention_records_source", "source"),
        Index("ix_intention_records_intention_type", "intention_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_id = Column(UUID(as_uuid=True), ForeignKey("campaign_runs.id", ondelete="SET NULL"), nullable=True)
    branch_id = Column(UUID(as_uuid=True), ForeignKey("execution_branches.id", ondelete="SET NULL"), nullable=True)
    phase_job_id = Column(UUID(as_uuid=True), ForeignKey("phase_jobs.id", ondelete="SET NULL"), nullable=True)
    parent_intention_id = Column(
        UUID(as_uuid=True),
        ForeignKey("intention_records.id", ondelete="SET NULL"),
        nullable=True,
    )

    source = Column(
        SAEnum(
            IntentionSourceEnum,
            name="intention_source_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
    )
    intention_type = Column(
        SAEnum(
            IntentionTypeEnum,
            name="intention_type_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
    )
    initiated_by = Column(Text, nullable=False)
    declared_goal = Column(Text, nullable=False)
    declared_reason = Column(Text, nullable=True)
    policy_basis = Column(Text, nullable=True)
    risk_class = Column(
        SAEnum(
            RiskPolicyClassEnum,
            name="risk_policy_class_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=True,
    )
    risk_posture_changed = Column(Boolean, nullable=False, default=False, server_default="false")
    approval_required = Column(Boolean, nullable=False, default=False, server_default="false")
    approval_reason = Column(Text, nullable=True)
    context_json = Column(JSON, nullable=False, server_default="{}")

    campaign_run = relationship("CampaignRun", back_populates="intentions")
    branch = relationship("ExecutionBranch", back_populates="intentions")
    phase_job = relationship("PhaseJob", back_populates="intentions")
    approval_gates = relationship("ApprovalGate", back_populates="intention")
    tool_executions = relationship("ToolExecution", back_populates="intention")
    artifacts = relationship("Artifact", back_populates="intention")
    observations = relationship("Observation", back_populates="intention")
    scan_notes = relationship("ScanNote", back_populates="intention")
    submission_drafts = relationship("SubmissionDraft", back_populates="intention")
    audit_events = relationship("AuditEvent", back_populates="intention")
    parent_intention = relationship(
        "IntentionRecord",
        remote_side=[id],
        foreign_keys=[parent_intention_id],
        back_populates="child_intentions",
        post_update=True,
    )
    child_intentions = relationship(
        "IntentionRecord",
        foreign_keys=[parent_intention_id],
        back_populates="parent_intention",
    )
