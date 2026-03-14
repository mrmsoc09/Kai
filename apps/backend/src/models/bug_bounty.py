from __future__ import annotations

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
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
from .mixins import TimestampMixin


class HuntScheduleJob(Base, TimestampMixin):
    __tablename__ = "hunt_schedule_jobs"
    __table_args__ = (
        UniqueConstraint(
            "program_id",
            "scope_target_id",
            "workflow_template",
            name="uq_hunt_schedule_jobs_program_target_template",
        ),
        CheckConstraint(
            "btrim(workflow_template) <> ''",
            name="hunt_schedule_jobs_template_not_empty",
        ),
        CheckConstraint(
            "schedule_type IN ('interval', 'cron')",
            name="hunt_schedule_jobs_schedule_type_allowed",
        ),
        CheckConstraint(
            "status IN ('ACTIVE', 'PAUSED', 'DISABLED', 'ERROR')",
            name="hunt_schedule_jobs_status_allowed",
        ),
        CheckConstraint(
            "interval_minutes IS NULL OR interval_minutes > 0",
            name="hunt_schedule_jobs_interval_positive",
        ),
        CheckConstraint(
            "max_concurrency > 0",
            name="hunt_schedule_jobs_max_concurrency_positive",
        ),
        CheckConstraint(
            "cooldown_minutes >= 0",
            name="hunt_schedule_jobs_cooldown_non_negative",
        ),
        CheckConstraint(
            "failure_backoff_minutes >= 0",
            name="hunt_schedule_jobs_failure_backoff_non_negative",
        ),
        CheckConstraint(
            "failure_pause_threshold >= 1",
            name="hunt_schedule_jobs_failure_pause_threshold_positive",
        ),
        Index("ix_hunt_schedule_jobs_program_id", "program_id"),
        Index("ix_hunt_schedule_jobs_scope_target_id", "scope_target_id"),
        Index("ix_hunt_schedule_jobs_status", "status"),
        Index("ix_hunt_schedule_jobs_next_scheduled_run_at", "next_scheduled_run_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_id = Column(
        UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_target_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scope_targets.id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_template = Column(Text, nullable=False)
    schedule_type = Column(Text, nullable=False, server_default="interval")
    interval_minutes = Column(Integer, nullable=True)
    cron_expr = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default="ACTIVE")
    safe_mode = Column(Boolean, nullable=False, server_default="true")
    dry_run = Column(Boolean, nullable=False, server_default="false")
    priority_tier = Column(Integer, nullable=False, server_default="3")
    max_concurrency = Column(Integer, nullable=False, server_default="1")
    cooldown_minutes = Column(Integer, nullable=False, server_default="60")
    failure_backoff_minutes = Column(Integer, nullable=False, server_default="240")
    failure_pause_threshold = Column(Integer, nullable=False, server_default="3")
    consecutive_failures = Column(Integer, nullable=False, server_default="0")
    last_run_started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    last_run_finished_at = Column(TIMESTAMP(timezone=True), nullable=True)
    last_run_status = Column(Text, nullable=True)
    last_failure_reason = Column(Text, nullable=True)
    next_scheduled_run_at = Column(TIMESTAMP(timezone=True), nullable=True)
    paused_at = Column(TIMESTAMP(timezone=True), nullable=True)
    paused_reason = Column(Text, nullable=True)
    created_by = Column(Text, nullable=True)
    updated_by = Column(Text, nullable=True)
    config_json = Column(JSON, nullable=False, server_default="{}")

    program = relationship("Program")
    scope_target = relationship("ScopeTarget")
    readiness_records = relationship("HuntReadinessRecord", back_populates="schedule_job")
    deltas = relationship("WorkflowDeltaRecord", back_populates="schedule_job")


class HuntReadinessRecord(Base, TimestampMixin):
    __tablename__ = "hunt_readiness_records"
    __table_args__ = (
        CheckConstraint(
            "decision_status IN ("
            "'READY', "
            "'BLOCKED_BY_SCOPE', "
            "'BLOCKED_BY_PROGRAM_POLICY', "
            "'BLOCKED_BY_HEALTH', "
            "'BLOCKED_BY_CONFIG', "
            "'BLOCKED_BY_COOLDOWN', "
            "'BLOCKED_BY_DISABLED_TARGET', "
            "'BLOCKED_BY_SAFETY_POLICY'"
            ")",
            name="hunt_readiness_records_status_allowed",
        ),
        CheckConstraint(
            "btrim(workflow_template) <> ''",
            name="hunt_readiness_records_template_not_empty",
        ),
        CheckConstraint(
            "btrim(target_identifier) <> ''",
            name="hunt_readiness_records_target_not_empty",
        ),
        Index("ix_hunt_readiness_records_schedule_id", "schedule_job_id"),
        Index("ix_hunt_readiness_records_program_id", "program_id"),
        Index("ix_hunt_readiness_records_scope_target_id", "scope_target_id"),
        Index("ix_hunt_readiness_records_decision_status", "decision_status"),
        Index("ix_hunt_readiness_records_decided_at", "decided_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hunt_schedule_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    program_id = Column(
        UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_target_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scope_targets.id", ondelete="CASCADE"),
        nullable=False,
    )
    campaign_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaign_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    workflow_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    workflow_template = Column(Text, nullable=False)
    target_identifier = Column(Text, nullable=False)
    trigger_source = Column(Text, nullable=False, server_default="scheduler")
    decision_status = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    decided_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    details_json = Column(JSON, nullable=False, server_default="{}")

    schedule_job = relationship("HuntScheduleJob", back_populates="readiness_records")
    program = relationship("Program")
    scope_target = relationship("ScopeTarget")
    workflow_run = relationship("WorkflowRun")
    campaign_run = relationship("CampaignRun")


class WorkflowDeltaRecord(Base, TimestampMixin):
    __tablename__ = "workflow_delta_records"
    __table_args__ = (
        CheckConstraint(
            "btrim(delta_type) <> ''",
            name="workflow_delta_records_delta_type_not_empty",
        ),
        CheckConstraint(
            "change_type IN ('NEW', 'REMOVED', 'CHANGED', 'UNCHANGED', 'COVERAGE_GAP')",
            name="workflow_delta_records_change_type_allowed",
        ),
        CheckConstraint(
            "btrim(delta_key) <> ''",
            name="workflow_delta_records_delta_key_not_empty",
        ),
        Index("ix_workflow_delta_records_program_id", "program_id"),
        Index("ix_workflow_delta_records_scope_target_id", "scope_target_id"),
        Index("ix_workflow_delta_records_workflow_run_id", "workflow_run_id"),
        Index("ix_workflow_delta_records_previous_workflow_run_id", "previous_workflow_run_id"),
        Index("ix_workflow_delta_records_delta_type", "delta_type"),
        Index("ix_workflow_delta_records_change_type", "change_type"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    schedule_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hunt_schedule_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    program_id = Column(
        UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_target_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scope_targets.id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    previous_workflow_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    delta_type = Column(Text, nullable=False)
    delta_key = Column(Text, nullable=False)
    change_type = Column(Text, nullable=False)
    severity_hint = Column(Text, nullable=True)
    details_json = Column(JSON, nullable=False, server_default="{}")

    schedule_job = relationship("HuntScheduleJob", back_populates="deltas")
    program = relationship("Program")
    scope_target = relationship("ScopeTarget")
    workflow_run = relationship("WorkflowRun", foreign_keys=[workflow_run_id])
    previous_workflow_run = relationship("WorkflowRun", foreign_keys=[previous_workflow_run_id])


class AnalystQueueItem(Base, TimestampMixin):
    __tablename__ = "analyst_queue_items"
    __table_args__ = (
        UniqueConstraint(
            "workflow_finding_id",
            name="uq_analyst_queue_items_workflow_finding_id",
        ),
        CheckConstraint(
            "status IN ("
            "'new', "
            "'acknowledged', "
            "'triaged', "
            "'needs_manual_validation', "
            "'ready_for_report', "
            "'dismissed', "
            "'duplicate_suspected', "
            "'submitted_externally'"
            ")",
            name="analyst_queue_items_status_allowed",
        ),
        CheckConstraint(
            "btrim(vulnerability_type) <> ''",
            name="analyst_queue_items_vulnerability_type_not_empty",
        ),
        CheckConstraint(
            "btrim(affected_asset) <> ''",
            name="analyst_queue_items_affected_asset_not_empty",
        ),
        Index("ix_analyst_queue_items_program_id", "program_id"),
        Index("ix_analyst_queue_items_scope_target_id", "scope_target_id"),
        Index("ix_analyst_queue_items_workflow_run_id", "workflow_run_id"),
        Index("ix_analyst_queue_items_status", "status"),
        Index("ix_analyst_queue_items_reportability_score", "reportability_score"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_id = Column(
        UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_target_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scope_targets.id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_finding_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_findings.id", ondelete="SET NULL"),
        nullable=True,
    )
    finding_id = Column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="SET NULL"),
        nullable=True,
    )
    workflow_template = Column(Text, nullable=False)
    finding_type = Column(Text, nullable=True)
    vulnerability_type = Column(Text, nullable=False)
    affected_asset = Column(Text, nullable=False)
    affected_endpoint = Column(Text, nullable=True)
    parameter = Column(Text, nullable=True)
    evidence_summary = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=True)
    severity_hint = Column(Text, nullable=True)
    novelty_score = Column(Float, nullable=True)
    reportability_score = Column(Float, nullable=True)
    duplicate_risk_hint = Column(Text, nullable=True)
    policy_fit_status = Column(Text, nullable=True)
    status = Column(Text, nullable=False, server_default="new")
    artifact_ref = Column(Text, nullable=True)
    assigned_to = Column(Text, nullable=True)
    last_transition_at = Column(TIMESTAMP(timezone=True), nullable=True)
    details_json = Column(JSON, nullable=False, server_default="{}")

    program = relationship("Program")
    scope_target = relationship("ScopeTarget")
    workflow_run = relationship("WorkflowRun")
    workflow_finding = relationship("WorkflowFinding")


class SignalIntelligenceRecord(Base, TimestampMixin):
    __tablename__ = "signal_intelligence_records"
    __table_args__ = (
        UniqueConstraint(
            "signal_fingerprint",
            name="uq_signal_intelligence_records_fingerprint",
        ),
        CheckConstraint(
            "btrim(source) <> ''",
            name="signal_intelligence_records_source_not_empty",
        ),
        CheckConstraint(
            "btrim(signal_type) <> ''",
            name="signal_intelligence_records_type_not_empty",
        ),
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)",
            name="signal_intelligence_records_confidence_bounds",
        ),
        Index("ix_signal_intelligence_records_program_id", "program_id"),
        Index("ix_signal_intelligence_records_scope_target_id", "scope_target_id"),
        Index("ix_signal_intelligence_records_workflow_run_id", "workflow_run_id"),
        Index("ix_signal_intelligence_records_signal_type", "signal_type"),
        Index("ix_signal_intelligence_records_observed_at", "observed_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_id = Column(
        UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_target_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scope_targets.id", ondelete="SET NULL"),
        nullable=True,
    )
    workflow_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    source = Column(Text, nullable=False)
    source_record_id = Column(Text, nullable=True)
    signal_type = Column(Text, nullable=False)
    signal_key = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=True)
    severity_hint = Column(Text, nullable=True)
    signal_fingerprint = Column(Text, nullable=False)
    evidence_refs_json = Column(JSON, nullable=False, server_default="[]")
    correlation_refs_json = Column(JSON, nullable=False, server_default="[]")
    details_json = Column(JSON, nullable=False, server_default="{}")
    observed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    program = relationship("Program")
    scope_target = relationship("ScopeTarget")
    workflow_run = relationship("WorkflowRun")


class OpportunityInferenceRecord(Base, TimestampMixin):
    __tablename__ = "opportunity_inference_records"
    __table_args__ = (
        CheckConstraint(
            "opportunity_score >= 0.0 AND opportunity_score <= 100.0",
            name="opportunity_inference_records_opportunity_score_bounds",
        ),
        CheckConstraint(
            "target_priority_score >= 0.0 AND target_priority_score <= 100.0",
            name="opportunity_inference_records_target_priority_score_bounds",
        ),
        Index("ix_opportunity_inference_records_program_id", "program_id"),
        Index("ix_opportunity_inference_records_scope_target_id", "scope_target_id"),
        Index("ix_opportunity_inference_records_workflow_run_id", "workflow_run_id"),
        Index("ix_opportunity_inference_records_inferred_at", "inferred_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_id = Column(
        UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_target_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scope_targets.id", ondelete="SET NULL"),
        nullable=True,
    )
    workflow_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    recommended_workflow = Column(Text, nullable=False)
    next_best_action = Column(Text, nullable=False)
    opportunity_score = Column(Float, nullable=False)
    target_priority_score = Column(Float, nullable=False)
    reasoning_summary = Column(Text, nullable=False)
    supporting_evidence_json = Column(JSON, nullable=False, server_default="[]")
    details_json = Column(JSON, nullable=False, server_default="{}")
    inferred_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    program = relationship("Program")
    scope_target = relationship("ScopeTarget")
    workflow_run = relationship("WorkflowRun")


class SwarmReasoningRecord(Base, TimestampMixin):
    __tablename__ = "swarm_reasoning_records"
    __table_args__ = (
        CheckConstraint(
            "btrim(agent_role) <> ''",
            name="swarm_reasoning_records_agent_role_not_empty",
        ),
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)",
            name="swarm_reasoning_records_confidence_bounds",
        ),
        Index("ix_swarm_reasoning_records_program_id", "program_id"),
        Index("ix_swarm_reasoning_records_scope_target_id", "scope_target_id"),
        Index("ix_swarm_reasoning_records_workflow_run_id", "workflow_run_id"),
        Index("ix_swarm_reasoning_records_agent_role", "agent_role"),
        Index("ix_swarm_reasoning_records_reasoned_at", "reasoned_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_id = Column(
        UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_target_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scope_targets.id", ondelete="SET NULL"),
        nullable=True,
    )
    workflow_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    opportunity_inference_id = Column(
        UUID(as_uuid=True),
        ForeignKey("opportunity_inference_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    agent_role = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=True)
    output_json = Column(JSON, nullable=False, server_default="{}")
    details_json = Column(JSON, nullable=False, server_default="{}")
    reasoned_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    program = relationship("Program")
    scope_target = relationship("ScopeTarget")
    workflow_run = relationship("WorkflowRun")
    opportunity_inference = relationship("OpportunityInferenceRecord")


class AdaptiveScheduleActionRecord(Base, TimestampMixin):
    __tablename__ = "adaptive_schedule_action_records"
    __table_args__ = (
        CheckConstraint(
            "action_status IN ('APPLIED', 'BLOCKED', 'SKIPPED')",
            name="adaptive_schedule_action_records_status_allowed",
        ),
        CheckConstraint(
            "btrim(action_type) <> ''",
            name="adaptive_schedule_action_records_action_not_empty",
        ),
        Index("ix_adaptive_schedule_action_records_program_id", "program_id"),
        Index("ix_adaptive_schedule_action_records_scope_target_id", "scope_target_id"),
        Index("ix_adaptive_schedule_action_records_schedule_job_id", "schedule_job_id"),
        Index("ix_adaptive_schedule_action_records_action_status", "action_status"),
        Index("ix_adaptive_schedule_action_records_executed_at", "executed_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_id = Column(
        UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_target_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scope_targets.id", ondelete="SET NULL"),
        nullable=True,
    )
    schedule_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hunt_schedule_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    opportunity_inference_id = Column(
        UUID(as_uuid=True),
        ForeignKey("opportunity_inference_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    action_type = Column(Text, nullable=False)
    action_status = Column(Text, nullable=False)
    reason = Column(Text, nullable=False)
    details_json = Column(JSON, nullable=False, server_default="{}")
    executed_at = Column(
        TIMESTAMP(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    program = relationship("Program")
    scope_target = relationship("ScopeTarget")
    schedule_job = relationship("HuntScheduleJob")
    opportunity_inference = relationship("OpportunityInferenceRecord")
