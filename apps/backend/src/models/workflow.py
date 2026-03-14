from __future__ import annotations

import uuid

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    Column,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Text,
    TIMESTAMP,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base
from .enums import CorrelationActionEnum, StageRunStatusEnum, WorkflowRunStatusEnum
from .mixins import TimestampMixin


class WorkflowRun(Base, TimestampMixin):
    __tablename__ = "workflow_runs"
    __table_args__ = (
        Index("ix_workflow_runs_campaign_run_id", "campaign_run_id"),
        Index("ix_workflow_runs_status", "status"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    campaign_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaign_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_target_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scope_targets.id", ondelete="SET NULL"),
        nullable=True,
    )
    template_name = Column(Text, nullable=False)
    target = Column(Text, nullable=False)
    safe_mode = Column(Boolean, nullable=False, server_default="true")
    dry_run = Column(Boolean, nullable=False, server_default="false")
    trigger_source = Column(Text, nullable=False, server_default="API")
    total_phases = Column(Integer, nullable=False, default=0)
    completed_phases = Column(Integer, nullable=False, server_default="0")
    status = Column(
        SAEnum(
            WorkflowRunStatusEnum,
            name="workflow_run_status_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
        server_default=WorkflowRunStatusEnum.PENDING.value,
    )
    artifact_manifest_path = Column(Text, nullable=True)
    plan_artifact_path = Column(Text, nullable=True)
    summary_artifact_path = Column(Text, nullable=True)
    duration_ms = Column(Float, nullable=True)
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    ended_at = Column(TIMESTAMP(timezone=True), nullable=True)

    campaign_run = relationship("CampaignRun", back_populates="workflow_runs")
    stage_runs = relationship(
        "StageRun",
        back_populates="workflow_run",
        cascade="all, delete-orphan",
    )
    phase_jobs = relationship(
        "PhaseJob",
        back_populates="workflow_run",
        foreign_keys="[PhaseJob.workflow_run_id]",
    )
    workflow_findings = relationship(
        "WorkflowFinding",
        back_populates="workflow_run",
        cascade="all, delete-orphan",
    )
    correlation_records = relationship(
        "CorrelationRecord",
        back_populates="workflow_run",
        foreign_keys="[CorrelationRecord.workflow_run_id]",
    )


class StageRun(Base, TimestampMixin):
    __tablename__ = "stage_runs"
    __table_args__ = (
        UniqueConstraint(
            "workflow_run_id",
            "stage_name",
            name="uq_stage_runs_workflow_stage",
        ),
        Index("ix_stage_runs_workflow_run_id", "workflow_run_id"),
        Index("ix_stage_runs_campaign_run_id", "campaign_run_id"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    campaign_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaign_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    stage_name = Column(Text, nullable=False)
    stage_order = Column(Integer, nullable=False, default=0)
    phase_count = Column(Integer, nullable=False, server_default="0")
    completed_count = Column(Integer, nullable=False, server_default="0")
    status = Column(
        SAEnum(
            StageRunStatusEnum,
            name="stage_run_status_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
        server_default=StageRunStatusEnum.PENDING.value,
    )
    failure_reason = Column(Text, nullable=True)
    duration_ms = Column(Float, nullable=True)
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    ended_at = Column(TIMESTAMP(timezone=True), nullable=True)

    workflow_run = relationship("WorkflowRun", back_populates="stage_runs")
    phase_jobs = relationship(
        "PhaseJob",
        back_populates="stage_run",
        foreign_keys="[PhaseJob.stage_run_id]",
    )
    tool_executions = relationship(
        "ToolExecution",
        back_populates="stage_run",
        foreign_keys="[ToolExecution.stage_run_id]",
    )


class WorkflowFinding(Base, TimestampMixin):
    __tablename__ = "workflow_findings"
    __table_args__ = (
        Index("ix_workflow_findings_workflow_run_id", "workflow_run_id"),
        Index("ix_workflow_findings_campaign_id", "campaign_id"),
        Index("ix_workflow_findings_asset_identifier", "asset_identifier"),
        Index("ix_workflow_findings_vulnerability_type", "vulnerability_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    campaign_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaign_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    stage_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("stage_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    tool_execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tool_executions.id", ondelete="SET NULL"),
        nullable=True,
    )
    asset_identifier = Column(Text, nullable=False)
    endpoint = Column(Text, nullable=True)
    parameter = Column(Text, nullable=True)
    vulnerability_type = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=True)
    severity_hint = Column(Text, nullable=True)
    evidence_artifact_path = Column(Text, nullable=True)
    details_json = Column(JSON, nullable=False, server_default="{}")

    workflow_run = relationship("WorkflowRun", back_populates="workflow_findings")


class CorrelationRecord(Base, TimestampMixin):
    __tablename__ = "correlation_records"
    __table_args__ = (
        Index("ix_correlation_records_finding_id", "finding_id"),
        Index("ix_correlation_records_observation_id", "observation_id"),
        Index("ix_correlation_records_campaign_id", "campaign_id"),
        Index("ix_correlation_records_workflow_run_id", "workflow_run_id"),
        Index("ix_correlation_records_asset_identifier", "asset_identifier"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_id = Column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="CASCADE"),
        nullable=True,
    )
    observation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("observations.id", ondelete="CASCADE"),
        nullable=True,
    )
    campaign_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaign_runs.id", ondelete="CASCADE"),
        nullable=True,
    )
    workflow_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    correlation_rule = Column(
        Text, nullable=False, server_default="deterministic_title_match"
    )
    asset_identifier = Column(Text, nullable=True)
    signal_sources_json = Column(JSON, nullable=False, server_default="[]")
    confidence = Column(Float, nullable=True)
    priority_rank = Column(Integer, nullable=True)
    explanation = Column(Text, nullable=True)
    action = Column(
        SAEnum(
            CorrelationActionEnum,
            name="correlation_action_enum",
            native_enum=True,
            create_constraint=True,
        ),
        nullable=False,
    )
    duplicate_of_finding_id = Column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="SET NULL"),
        nullable=True,
    )
    correlated_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    workflow_run = relationship(
        "WorkflowRun",
        back_populates="correlation_records",
        foreign_keys=[workflow_run_id],
    )
