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
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from .base import Base
from .mixins import TimestampMixin, UTCAwareDatetime


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
    last_run_started_at = Column(UTCAwareDatetime, nullable=True)
    last_run_finished_at = Column(UTCAwareDatetime, nullable=True)
    last_run_status = Column(Text, nullable=True)
    last_failure_reason = Column(Text, nullable=True)
    next_scheduled_run_at = Column(UTCAwareDatetime, nullable=True)
    paused_at = Column(UTCAwareDatetime, nullable=True)
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
        UTCAwareDatetime,
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
    last_transition_at = Column(UTCAwareDatetime, nullable=True)
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
        UTCAwareDatetime,
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
        UTCAwareDatetime,
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
        UTCAwareDatetime,
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
        UTCAwareDatetime,
        nullable=False,
        server_default=func.now(),
    )

    program = relationship("Program")
    scope_target = relationship("ScopeTarget")
    schedule_job = relationship("HuntScheduleJob")
    opportunity_inference = relationship("OpportunityInferenceRecord")


class TargetYieldScoreRecord(Base, TimestampMixin):
    __tablename__ = "target_yield_score_records"
    __table_args__ = (
        CheckConstraint(
            "signal_density_score >= 0.0 AND signal_density_score <= 1.0",
            name="target_yield_score_records_signal_density_bounds",
        ),
        CheckConstraint(
            "novelty_score >= 0.0 AND novelty_score <= 1.0",
            name="target_yield_score_records_novelty_bounds",
        ),
        CheckConstraint(
            "coverage_quality_score >= 0.0 AND coverage_quality_score <= 1.0",
            name="target_yield_score_records_coverage_bounds",
        ),
        CheckConstraint(
            "candidate_quality_score >= 0.0 AND candidate_quality_score <= 1.0",
            name="target_yield_score_records_candidate_quality_bounds",
        ),
        CheckConstraint(
            "duplicate_penalty_score >= 0.0 AND duplicate_penalty_score <= 1.0",
            name="target_yield_score_records_duplicate_penalty_bounds",
        ),
        CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="target_yield_score_records_confidence_bounds",
        ),
        CheckConstraint(
            "yield_score >= 0.0 AND yield_score <= 100.0",
            name="target_yield_score_records_yield_bounds",
        ),
        Index("ix_target_yield_score_records_program_id", "program_id"),
        Index("ix_target_yield_score_records_scope_target_id", "scope_target_id"),
        Index("ix_target_yield_score_records_workflow_run_id", "workflow_run_id"),
        Index("ix_target_yield_score_records_scored_at", "scored_at"),
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
    signal_density_score = Column(Float, nullable=False)
    novelty_score = Column(Float, nullable=False)
    coverage_quality_score = Column(Float, nullable=False)
    candidate_quality_score = Column(Float, nullable=False)
    duplicate_penalty_score = Column(Float, nullable=False)
    confidence_score = Column(Float, nullable=False, server_default="0.0")
    yield_score = Column(Float, nullable=False)
    details_json = Column(JSON, nullable=False, server_default="{}")
    scored_at = Column(
        UTCAwareDatetime,
        nullable=False,
        server_default=func.now(),
    )

    program = relationship("Program")
    scope_target = relationship("ScopeTarget")
    workflow_run = relationship("WorkflowRun")


class DuplicateRiskRecord(Base, TimestampMixin):
    __tablename__ = "duplicate_risk_records"
    __table_args__ = (
        CheckConstraint(
            "duplicate_risk_score >= 0.0 AND duplicate_risk_score <= 1.0",
            name="duplicate_risk_records_score_bounds",
        ),
        CheckConstraint(
            "risk_band IN ('LOW', 'MEDIUM', 'HIGH')",
            name="duplicate_risk_records_band_allowed",
        ),
        CheckConstraint(
            "btrim(candidate_key) <> ''",
            name="duplicate_risk_records_candidate_key_not_empty",
        ),
        Index("ix_duplicate_risk_records_program_id", "program_id"),
        Index("ix_duplicate_risk_records_scope_target_id", "scope_target_id"),
        Index("ix_duplicate_risk_records_workflow_run_id", "workflow_run_id"),
        Index("ix_duplicate_risk_records_queue_item_id", "analyst_queue_item_id"),
        Index("ix_duplicate_risk_records_assessed_at", "assessed_at"),
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
    analyst_queue_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analyst_queue_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    candidate_key = Column(Text, nullable=False)
    duplicate_risk_score = Column(Float, nullable=False)
    risk_band = Column(Text, nullable=False)
    reasoning_summary = Column(Text, nullable=False)
    supporting_signal_ids_json = Column(JSON, nullable=False, server_default="[]")
    details_json = Column(JSON, nullable=False, server_default="{}")
    assessed_at = Column(
        UTCAwareDatetime,
        nullable=False,
        server_default=func.now(),
    )

    program = relationship("Program")
    scope_target = relationship("ScopeTarget")
    workflow_run = relationship("WorkflowRun")
    analyst_queue_item = relationship("AnalystQueueItem")


class EvidenceCompletenessRecord(Base, TimestampMixin):
    __tablename__ = "evidence_completeness_records"
    __table_args__ = (
        CheckConstraint(
            "evidence_completeness_score >= 0.0 AND evidence_completeness_score <= 1.0",
            name="evidence_completeness_records_score_bounds",
        ),
        CheckConstraint(
            "readiness_state IN ('INSUFFICIENT', 'PARTIAL', 'READY_FOR_REVIEW', 'READY_FOR_REPORT')",
            name="evidence_completeness_records_state_allowed",
        ),
        CheckConstraint(
            "btrim(candidate_key) <> ''",
            name="evidence_completeness_records_candidate_key_not_empty",
        ),
        Index("ix_evidence_completeness_records_program_id", "program_id"),
        Index("ix_evidence_completeness_records_scope_target_id", "scope_target_id"),
        Index("ix_evidence_completeness_records_workflow_run_id", "workflow_run_id"),
        Index("ix_evidence_completeness_records_queue_item_id", "analyst_queue_item_id"),
        Index("ix_evidence_completeness_records_assessed_at", "assessed_at"),
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
    analyst_queue_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analyst_queue_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    candidate_key = Column(Text, nullable=False)
    evidence_completeness_score = Column(Float, nullable=False)
    readiness_state = Column(Text, nullable=False)
    missing_fields_json = Column(JSON, nullable=False, server_default="[]")
    reasoning_summary = Column(Text, nullable=False)
    details_json = Column(JSON, nullable=False, server_default="{}")
    assessed_at = Column(
        UTCAwareDatetime,
        nullable=False,
        server_default=func.now(),
    )

    program = relationship("Program")
    scope_target = relationship("ScopeTarget")
    workflow_run = relationship("WorkflowRun")
    analyst_queue_item = relationship("AnalystQueueItem")


class VulnerabilityPredictionRecord(Base, TimestampMixin):
    __tablename__ = "vulnerability_prediction_records"
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="vulnerability_prediction_records_confidence_bounds",
        ),
        CheckConstraint(
            "novelty_score >= 0.0 AND novelty_score <= 1.0",
            name="vulnerability_prediction_records_novelty_bounds",
        ),
        CheckConstraint(
            "duplicate_risk_score >= 0.0 AND duplicate_risk_score <= 1.0",
            name="vulnerability_prediction_records_duplicate_bounds",
        ),
        CheckConstraint(
            "reportability_score >= 0.0 AND reportability_score <= 1.0",
            name="vulnerability_prediction_records_reportability_bounds",
        ),
        CheckConstraint(
            "evidence_completeness_score >= 0.0 AND evidence_completeness_score <= 1.0",
            name="vulnerability_prediction_records_evidence_bounds",
        ),
        CheckConstraint(
            "opportunity_score >= 0.0 AND opportunity_score <= 100.0",
            name="vulnerability_prediction_records_opportunity_bounds",
        ),
        CheckConstraint(
            "btrim(predicted_vulnerability_type) <> ''",
            name="vulnerability_prediction_records_type_not_empty",
        ),
        Index("ix_vulnerability_prediction_records_program_id", "program_id"),
        Index("ix_vulnerability_prediction_records_scope_target_id", "scope_target_id"),
        Index("ix_vulnerability_prediction_records_workflow_run_id", "workflow_run_id"),
        Index(
            "ix_vulnerability_prediction_records_queue_item_id",
            "analyst_queue_item_id",
        ),
        Index("ix_vulnerability_prediction_records_created_at", "predicted_at"),
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
    analyst_queue_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analyst_queue_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    predicted_vulnerability_type = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=False)
    novelty_score = Column(Float, nullable=False)
    duplicate_risk_score = Column(Float, nullable=False)
    reportability_score = Column(Float, nullable=False)
    evidence_completeness_score = Column(Float, nullable=False)
    opportunity_score = Column(Float, nullable=False)
    recommended_next_workflow = Column(Text, nullable=False)
    recommended_follow_up_action = Column(Text, nullable=False)
    reasoning_summary = Column(Text, nullable=False)
    supporting_signal_ids_json = Column(JSON, nullable=False, server_default="[]")
    details_json = Column(JSON, nullable=False, server_default="{}")
    predicted_at = Column(
        UTCAwareDatetime,
        nullable=False,
        server_default=func.now(),
    )

    program = relationship("Program")
    scope_target = relationship("ScopeTarget")
    workflow_run = relationship("WorkflowRun")
    analyst_queue_item = relationship("AnalystQueueItem")


class OpportunitySelectionRecord(Base, TimestampMixin):
    __tablename__ = "opportunity_selection_records"
    __table_args__ = (
        CheckConstraint(
            "subject_type IN ('PROGRAM', 'TARGET', 'CANDIDATE', 'CLUSTER')",
            name="opportunity_selection_records_subject_type_allowed",
        ),
        CheckConstraint(
            "btrim(subject_key) <> ''",
            name="opportunity_selection_records_subject_key_not_empty",
        ),
        CheckConstraint(
            "selection_score >= 0.0 AND selection_score <= 100.0",
            name="opportunity_selection_records_score_bounds",
        ),
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)",
            name="opportunity_selection_records_confidence_bounds",
        ),
        CheckConstraint(
            "duplicate_risk_score IS NULL OR (duplicate_risk_score >= 0.0 AND duplicate_risk_score <= 1.0)",
            name="opportunity_selection_records_duplicate_bounds",
        ),
        CheckConstraint(
            "evidence_completeness_score IS NULL OR (evidence_completeness_score >= 0.0 AND evidence_completeness_score <= 1.0)",
            name="opportunity_selection_records_evidence_bounds",
        ),
        CheckConstraint(
            "priority_rank IS NULL OR priority_rank >= 1",
            name="opportunity_selection_records_rank_positive",
        ),
        Index("ix_opportunity_selection_records_program_id", "program_id"),
        Index("ix_opportunity_selection_records_scope_target_id", "scope_target_id"),
        Index("ix_opportunity_selection_records_workflow_run_id", "workflow_run_id"),
        Index(
            "ix_opportunity_selection_records_queue_item_id",
            "analyst_queue_item_id",
        ),
        Index("ix_opportunity_selection_records_subject", "subject_type", "subject_key"),
        Index("ix_opportunity_selection_records_scored_at", "scored_at"),
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
    analyst_queue_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analyst_queue_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    subject_type = Column(Text, nullable=False)
    subject_key = Column(Text, nullable=False)
    selection_score = Column(Float, nullable=False)
    priority_rank = Column(Integer, nullable=True)
    confidence_score = Column(Float, nullable=True)
    duplicate_risk_score = Column(Float, nullable=True)
    evidence_completeness_score = Column(Float, nullable=True)
    reasoning_summary = Column(Text, nullable=False)
    details_json = Column(JSON, nullable=False, server_default="{}")
    scored_at = Column(
        UTCAwareDatetime,
        nullable=False,
        server_default=func.now(),
    )

    program = relationship("Program")
    scope_target = relationship("ScopeTarget")
    workflow_run = relationship("WorkflowRun")
    analyst_queue_item = relationship("AnalystQueueItem")


class WorkflowRecommendationRecord(Base, TimestampMixin):
    __tablename__ = "workflow_recommendation_records"
    __table_args__ = (
        CheckConstraint(
            "recommendation_status IN ('PROPOSED', 'APPLIED', 'BLOCKED', 'DEFERRED')",
            name="workflow_recommendation_records_status_allowed",
        ),
        CheckConstraint(
            "action_priority >= 1",
            name="workflow_recommendation_records_priority_positive",
        ),
        CheckConstraint(
            "btrim(recommended_workflow) <> ''",
            name="workflow_recommendation_records_workflow_not_empty",
        ),
        CheckConstraint(
            "btrim(recommended_action) <> ''",
            name="workflow_recommendation_records_action_not_empty",
        ),
        Index("ix_workflow_recommendation_records_program_id", "program_id"),
        Index("ix_workflow_recommendation_records_scope_target_id", "scope_target_id"),
        Index("ix_workflow_recommendation_records_workflow_run_id", "workflow_run_id"),
        Index(
            "ix_workflow_recommendation_records_queue_item_id",
            "analyst_queue_item_id",
        ),
        Index(
            "ix_workflow_recommendation_records_prediction_id",
            "prediction_record_id",
        ),
        Index(
            "ix_workflow_recommendation_records_selection_id",
            "selection_record_id",
        ),
        Index("ix_workflow_recommendation_records_status", "recommendation_status"),
        Index("ix_workflow_recommendation_records_recommended_at", "recommended_at"),
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
    analyst_queue_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analyst_queue_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    prediction_record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("vulnerability_prediction_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    selection_record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("opportunity_selection_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    target_yield_score_id = Column(
        UUID(as_uuid=True),
        ForeignKey("target_yield_score_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    recommended_workflow = Column(Text, nullable=False)
    recommended_action = Column(Text, nullable=False)
    action_priority = Column(Integer, nullable=False, server_default="3")
    recommendation_status = Column(Text, nullable=False, server_default="PROPOSED")
    reasoning_summary = Column(Text, nullable=False)
    supporting_record_ids_json = Column(JSON, nullable=False, server_default="[]")
    details_json = Column(JSON, nullable=False, server_default="{}")
    recommended_at = Column(
        UTCAwareDatetime,
        nullable=False,
        server_default=func.now(),
    )

    program = relationship("Program")
    scope_target = relationship("ScopeTarget")
    workflow_run = relationship("WorkflowRun")
    analyst_queue_item = relationship("AnalystQueueItem")
    prediction_record = relationship("VulnerabilityPredictionRecord")
    selection_record = relationship("OpportunitySelectionRecord")
    target_yield_score = relationship("TargetYieldScoreRecord")


class NotificationAlertRecord(Base, TimestampMixin):
    __tablename__ = "notification_alert_records"
    __table_args__ = (
        CheckConstraint(
            "btrim(alert_type) <> ''",
            name="notification_alert_records_alert_type_not_empty",
        ),
        CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="notification_alert_records_severity_allowed",
        ),
        CheckConstraint(
            "urgency IN ('LOW', 'MEDIUM', 'HIGH', 'IMMEDIATE')",
            name="notification_alert_records_urgency_allowed",
        ),
        CheckConstraint(
            "status IN ('OPEN', 'ACKNOWLEDGED', 'SUPPRESSED', 'RESOLVED')",
            name="notification_alert_records_status_allowed",
        ),
        CheckConstraint(
            "occurrence_count >= 1",
            name="notification_alert_records_occurrence_positive",
        ),
        CheckConstraint(
            "btrim(alert_fingerprint) <> ''",
            name="notification_alert_records_fingerprint_not_empty",
        ),
        Index("ix_notification_alert_records_program_id", "program_id"),
        Index("ix_notification_alert_records_scope_target_id", "scope_target_id"),
        Index("ix_notification_alert_records_queue_item_id", "analyst_queue_item_id"),
        Index("ix_notification_alert_records_prediction_id", "prediction_record_id"),
        Index("ix_notification_alert_records_recommendation_id", "recommendation_record_id"),
        Index("ix_notification_alert_records_status", "status"),
        Index("ix_notification_alert_records_severity", "severity"),
        Index("ix_notification_alert_records_urgency", "urgency"),
        Index("ix_notification_alert_records_fingerprint", "alert_fingerprint"),
        Index("ix_notification_alert_records_last_seen_at", "last_seen_at"),
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
    analyst_queue_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analyst_queue_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    prediction_record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("vulnerability_prediction_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    recommendation_record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_recommendation_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    submission_draft_id = Column(
        UUID(as_uuid=True),
        ForeignKey("submission_drafts.id", ondelete="SET NULL"),
        nullable=True,
    )
    alert_type = Column(Text, nullable=False)
    severity = Column(Text, nullable=False)
    urgency = Column(Text, nullable=False)
    alert_fingerprint = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    reasoning_summary = Column(Text, nullable=True)
    supporting_signal_ids_json = Column(JSON, nullable=False, server_default="[]")
    supporting_record_ids_json = Column(JSON, nullable=False, server_default="[]")
    status = Column(Text, nullable=False, server_default="OPEN")
    occurrence_count = Column(Integer, nullable=False, server_default="1")
    first_seen_at = Column(
        UTCAwareDatetime,
        nullable=False,
        server_default=func.now(),
    )
    last_seen_at = Column(
        UTCAwareDatetime,
        nullable=False,
        server_default=func.now(),
    )
    acknowledged_at = Column(UTCAwareDatetime, nullable=True)
    acknowledged_by = Column(Text, nullable=True)
    resolved_at = Column(UTCAwareDatetime, nullable=True)
    resolved_by = Column(Text, nullable=True)
    details_json = Column(JSON, nullable=False, server_default="{}")

    program = relationship("Program")
    scope_target = relationship("ScopeTarget")
    workflow_run = relationship("WorkflowRun")
    analyst_queue_item = relationship("AnalystQueueItem")
    prediction_record = relationship("VulnerabilityPredictionRecord")
    recommendation_record = relationship("WorkflowRecommendationRecord")
    submission_draft = relationship("SubmissionDraft")


class AnalystCaseRecord(Base, TimestampMixin):
    __tablename__ = "analyst_case_records"
    __table_args__ = (
        CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="analyst_case_records_priority_allowed",
        ),
        CheckConstraint(
            "status IN ("
            "'new', "
            "'acknowledged', "
            "'triaging', "
            "'needs_manual_validation', "
            "'ready_for_report', "
            "'dismissed', "
            "'duplicate', "
            "'escalated', "
            "'submitted', "
            "'closed'"
            ")",
            name="analyst_case_records_status_allowed",
        ),
        CheckConstraint(
            "btrim(title) <> ''",
            name="analyst_case_records_title_not_empty",
        ),
        Index("ix_analyst_case_records_program_id", "program_id"),
        Index("ix_analyst_case_records_scope_target_id", "scope_target_id"),
        Index("ix_analyst_case_records_alert_id", "alert_id"),
        Index("ix_analyst_case_records_queue_item_id", "analyst_queue_item_id"),
        Index("ix_analyst_case_records_prediction_id", "prediction_record_id"),
        Index("ix_analyst_case_records_recommendation_id", "recommendation_record_id"),
        Index("ix_analyst_case_records_owner", "owner"),
        Index("ix_analyst_case_records_priority", "priority"),
        Index("ix_analyst_case_records_status", "status"),
        Index("ix_analyst_case_records_last_transition_at", "last_transition_at"),
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
    alert_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notification_alert_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    analyst_queue_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analyst_queue_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    prediction_record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("vulnerability_prediction_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    recommendation_record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_recommendation_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    submission_draft_id = Column(
        UUID(as_uuid=True),
        ForeignKey("submission_drafts.id", ondelete="SET NULL"),
        nullable=True,
    )
    title = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    reasoning_summary = Column(Text, nullable=True)
    priority = Column(Text, nullable=False, server_default="MEDIUM")
    status = Column(Text, nullable=False, server_default="new")
    owner = Column(Text, nullable=True)
    last_actor = Column(Text, nullable=True)
    assigned_at = Column(UTCAwareDatetime, nullable=True)
    last_transition_at = Column(UTCAwareDatetime, nullable=True)
    closed_at = Column(UTCAwareDatetime, nullable=True)
    closure_reason = Column(Text, nullable=True)
    evidence_refs_json = Column(JSON, nullable=False, server_default="[]")
    triage_notes_json = Column(JSON, nullable=False, server_default="[]")
    details_json = Column(JSON, nullable=False, server_default="{}")

    program = relationship("Program")
    scope_target = relationship("ScopeTarget")
    workflow_run = relationship("WorkflowRun")
    alert = relationship("NotificationAlertRecord")
    analyst_queue_item = relationship("AnalystQueueItem")
    prediction_record = relationship("VulnerabilityPredictionRecord")
    recommendation_record = relationship("WorkflowRecommendationRecord")
    submission_draft = relationship("SubmissionDraft")


class FeedbackSignalRecord(Base, TimestampMixin):
    __tablename__ = "feedback_signal_records"
    __table_args__ = (
        UniqueConstraint(
            "signal_fingerprint",
            name="uq_feedback_signal_records_fingerprint",
        ),
        CheckConstraint(
            "btrim(source_entity_type) <> ''",
            name="feedback_signal_records_source_type_not_empty",
        ),
        CheckConstraint(
            "btrim(source_entity_id) <> ''",
            name="feedback_signal_records_source_id_not_empty",
        ),
        CheckConstraint(
            "btrim(outcome_classification) <> ''",
            name="feedback_signal_records_outcome_not_empty",
        ),
        CheckConstraint(
            "confidence_score IS NULL OR (confidence_score >= 0.0 AND confidence_score <= 1.0)",
            name="feedback_signal_records_confidence_bounds",
        ),
        Index("ix_feedback_signal_records_program_id", "program_id"),
        Index("ix_feedback_signal_records_scope_target_id", "scope_target_id"),
        Index("ix_feedback_signal_records_workflow_run_id", "workflow_run_id"),
        Index("ix_feedback_signal_records_case_id", "analyst_case_id"),
        Index("ix_feedback_signal_records_alert_id", "alert_id"),
        Index("ix_feedback_signal_records_recommendation_id", "recommendation_record_id"),
        Index("ix_feedback_signal_records_outcome_classification", "outcome_classification"),
        Index("ix_feedback_signal_records_observed_at", "observed_at"),
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
    analyst_case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analyst_case_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    alert_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notification_alert_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    analyst_queue_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analyst_queue_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    recommendation_record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_recommendation_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_entity_type = Column(Text, nullable=False)
    source_entity_id = Column(Text, nullable=False)
    outcome_classification = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=True)
    reasoning_summary = Column(Text, nullable=True)
    signal_fingerprint = Column(Text, nullable=False)
    details_json = Column(JSON, nullable=False, server_default="{}")
    observed_at = Column(
        UTCAwareDatetime,
        nullable=False,
        server_default=func.now(),
    )

    program = relationship("Program")
    scope_target = relationship("ScopeTarget")
    workflow_run = relationship("WorkflowRun")
    analyst_case = relationship("AnalystCaseRecord")
    alert = relationship("NotificationAlertRecord")
    analyst_queue_item = relationship("AnalystQueueItem")
    recommendation_record = relationship("WorkflowRecommendationRecord")


class DecisionOutcomeRecord(Base, TimestampMixin):
    __tablename__ = "decision_outcome_records"
    __table_args__ = (
        UniqueConstraint(
            "outcome_fingerprint",
            name="uq_decision_outcome_records_fingerprint",
        ),
        CheckConstraint(
            "decision_type IN ('CASE', 'ALERT', 'RECOMMENDATION')",
            name="decision_outcome_records_type_allowed",
        ),
        CheckConstraint(
            "btrim(decision_status) <> ''",
            name="decision_outcome_records_status_not_empty",
        ),
        CheckConstraint(
            "btrim(outcome_classification) <> ''",
            name="decision_outcome_records_outcome_not_empty",
        ),
        Index("ix_decision_outcome_records_program_id", "program_id"),
        Index("ix_decision_outcome_records_scope_target_id", "scope_target_id"),
        Index("ix_decision_outcome_records_workflow_run_id", "workflow_run_id"),
        Index("ix_decision_outcome_records_case_id", "analyst_case_id"),
        Index("ix_decision_outcome_records_alert_id", "alert_id"),
        Index("ix_decision_outcome_records_recommendation_id", "recommendation_record_id"),
        Index("ix_decision_outcome_records_decision_type", "decision_type"),
        Index("ix_decision_outcome_records_decided_at", "decided_at"),
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
    analyst_case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analyst_case_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    alert_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notification_alert_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    recommendation_record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_recommendation_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    decision_type = Column(Text, nullable=False)
    decision_status = Column(Text, nullable=False)
    outcome_classification = Column(Text, nullable=False)
    decided_by = Column(Text, nullable=True)
    reasoning_summary = Column(Text, nullable=True)
    outcome_fingerprint = Column(Text, nullable=False)
    details_json = Column(JSON, nullable=False, server_default="{}")
    decided_at = Column(
        UTCAwareDatetime,
        nullable=False,
        server_default=func.now(),
    )

    program = relationship("Program")
    scope_target = relationship("ScopeTarget")
    workflow_run = relationship("WorkflowRun")
    analyst_case = relationship("AnalystCaseRecord")
    alert = relationship("NotificationAlertRecord")
    recommendation_record = relationship("WorkflowRecommendationRecord")


class WorkflowPerformanceRecord(Base, TimestampMixin):
    __tablename__ = "workflow_performance_records"
    __table_args__ = (
        CheckConstraint(
            "btrim(workflow_template) <> ''",
            name="workflow_performance_records_template_not_empty",
        ),
        CheckConstraint(
            "signals_generated >= 0",
            name="workflow_performance_records_signals_non_negative",
        ),
        CheckConstraint(
            "candidates_produced >= 0",
            name="workflow_performance_records_candidates_non_negative",
        ),
        CheckConstraint(
            "cases_created >= 0",
            name="workflow_performance_records_cases_non_negative",
        ),
        CheckConstraint(
            "reportable_outcomes >= 0",
            name="workflow_performance_records_reportable_non_negative",
        ),
        CheckConstraint(
            "duplicate_outcomes >= 0",
            name="workflow_performance_records_duplicate_non_negative",
        ),
        CheckConstraint(
            "dismissed_outcomes >= 0",
            name="workflow_performance_records_dismissed_non_negative",
        ),
        CheckConstraint(
            "workflow_signal_value >= 0.0 AND workflow_signal_value <= 100.0",
            name="workflow_performance_records_signal_value_bounds",
        ),
        CheckConstraint(
            "workflow_reportability_rate >= 0.0 AND workflow_reportability_rate <= 1.0",
            name="workflow_performance_records_reportability_bounds",
        ),
        CheckConstraint(
            "workflow_noise_rate >= 0.0 AND workflow_noise_rate <= 1.0",
            name="workflow_performance_records_noise_bounds",
        ),
        Index("ix_workflow_performance_records_program_id", "program_id"),
        Index("ix_workflow_performance_records_template", "workflow_template"),
        Index("ix_workflow_performance_records_window_end", "window_end"),
        Index("ix_workflow_performance_records_computed_at", "computed_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_id = Column(
        UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_template = Column(Text, nullable=False)
    window_start = Column(UTCAwareDatetime, nullable=False)
    window_end = Column(UTCAwareDatetime, nullable=False)
    signals_generated = Column(Integer, nullable=False, server_default="0")
    candidates_produced = Column(Integer, nullable=False, server_default="0")
    cases_created = Column(Integer, nullable=False, server_default="0")
    reportable_outcomes = Column(Integer, nullable=False, server_default="0")
    duplicate_outcomes = Column(Integer, nullable=False, server_default="0")
    dismissed_outcomes = Column(Integer, nullable=False, server_default="0")
    workflow_signal_value = Column(Float, nullable=False, server_default="0.0")
    workflow_reportability_rate = Column(Float, nullable=False, server_default="0.0")
    workflow_noise_rate = Column(Float, nullable=False, server_default="0.0")
    details_json = Column(JSON, nullable=False, server_default="{}")
    computed_at = Column(
        UTCAwareDatetime,
        nullable=False,
        server_default=func.now(),
    )

    program = relationship("Program")


class TargetPerformanceRecord(Base, TimestampMixin):
    __tablename__ = "target_performance_records"
    __table_args__ = (
        CheckConstraint(
            "signal_count >= 0",
            name="target_performance_records_signal_count_non_negative",
        ),
        CheckConstraint(
            "candidate_count >= 0",
            name="target_performance_records_candidate_count_non_negative",
        ),
        CheckConstraint(
            "case_count >= 0",
            name="target_performance_records_case_count_non_negative",
        ),
        CheckConstraint(
            "reportable_count >= 0",
            name="target_performance_records_reportable_count_non_negative",
        ),
        CheckConstraint(
            "duplicate_count >= 0",
            name="target_performance_records_duplicate_count_non_negative",
        ),
        CheckConstraint(
            "dismissed_count >= 0",
            name="target_performance_records_dismissed_count_non_negative",
        ),
        CheckConstraint(
            "target_signal_rate >= 0.0 AND target_signal_rate <= 1.0",
            name="target_performance_records_signal_rate_bounds",
        ),
        CheckConstraint(
            "target_duplicate_rate >= 0.0 AND target_duplicate_rate <= 1.0",
            name="target_performance_records_duplicate_rate_bounds",
        ),
        CheckConstraint(
            "target_reportability_rate >= 0.0 AND target_reportability_rate <= 1.0",
            name="target_performance_records_reportability_rate_bounds",
        ),
        CheckConstraint(
            "target_yield_score >= 0.0 AND target_yield_score <= 100.0",
            name="target_performance_records_yield_score_bounds",
        ),
        Index("ix_target_performance_records_program_id", "program_id"),
        Index("ix_target_performance_records_scope_target_id", "scope_target_id"),
        Index("ix_target_performance_records_window_end", "window_end"),
        Index("ix_target_performance_records_computed_at", "computed_at"),
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
    window_start = Column(UTCAwareDatetime, nullable=False)
    window_end = Column(UTCAwareDatetime, nullable=False)
    signal_count = Column(Integer, nullable=False, server_default="0")
    candidate_count = Column(Integer, nullable=False, server_default="0")
    case_count = Column(Integer, nullable=False, server_default="0")
    reportable_count = Column(Integer, nullable=False, server_default="0")
    duplicate_count = Column(Integer, nullable=False, server_default="0")
    dismissed_count = Column(Integer, nullable=False, server_default="0")
    target_signal_rate = Column(Float, nullable=False, server_default="0.0")
    target_duplicate_rate = Column(Float, nullable=False, server_default="0.0")
    target_reportability_rate = Column(Float, nullable=False, server_default="0.0")
    target_yield_score = Column(Float, nullable=False, server_default="0.0")
    details_json = Column(JSON, nullable=False, server_default="{}")
    computed_at = Column(
        UTCAwareDatetime,
        nullable=False,
        server_default=func.now(),
    )

    program = relationship("Program")
    scope_target = relationship("ScopeTarget")


class RecommendationOutcomeRecord(Base, TimestampMixin):
    __tablename__ = "recommendation_outcome_records"
    __table_args__ = (
        UniqueConstraint(
            "outcome_fingerprint",
            name="uq_recommendation_outcome_records_fingerprint",
        ),
        CheckConstraint(
            "outcome_status IN ('SUCCEEDED', 'USED', 'ABANDONED', 'BLOCKED', 'FAILED')",
            name="recommendation_outcome_records_status_allowed",
        ),
        CheckConstraint(
            "success_score >= 0.0 AND success_score <= 1.0",
            name="recommendation_outcome_records_success_bounds",
        ),
        Index("ix_recommendation_outcome_records_program_id", "program_id"),
        Index("ix_recommendation_outcome_records_recommendation_id", "recommendation_record_id"),
        Index("ix_recommendation_outcome_records_scope_target_id", "scope_target_id"),
        Index("ix_recommendation_outcome_records_outcome_status", "outcome_status"),
        Index("ix_recommendation_outcome_records_decided_at", "decided_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_id = Column(
        UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
    )
    recommendation_record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_recommendation_records.id", ondelete="CASCADE"),
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
    analyst_case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analyst_case_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    outcome_status = Column(Text, nullable=False)
    success_score = Column(Float, nullable=False, server_default="0.0")
    reasoning_summary = Column(Text, nullable=True)
    outcome_fingerprint = Column(Text, nullable=False)
    details_json = Column(JSON, nullable=False, server_default="{}")
    decided_at = Column(
        UTCAwareDatetime,
        nullable=False,
        server_default=func.now(),
    )

    program = relationship("Program")
    recommendation_record = relationship("WorkflowRecommendationRecord")
    scope_target = relationship("ScopeTarget")
    workflow_run = relationship("WorkflowRun")
    analyst_case = relationship("AnalystCaseRecord")


class AlertOutcomeRecord(Base, TimestampMixin):
    __tablename__ = "alert_outcome_records"
    __table_args__ = (
        UniqueConstraint(
            "outcome_fingerprint",
            name="uq_alert_outcome_records_fingerprint",
        ),
        CheckConstraint(
            "outcome_status IN ('ESCALATED', 'ACKNOWLEDGED', 'IGNORED', 'RESOLVED_ACTIONABLE', 'RESOLVED_NOISE', 'OPEN_TRACKING')",
            name="alert_outcome_records_status_allowed",
        ),
        CheckConstraint(
            "acknowledgement_latency_seconds IS NULL OR acknowledgement_latency_seconds >= 0",
            name="alert_outcome_records_latency_non_negative",
        ),
        Index("ix_alert_outcome_records_program_id", "program_id"),
        Index("ix_alert_outcome_records_alert_id", "alert_id"),
        Index("ix_alert_outcome_records_scope_target_id", "scope_target_id"),
        Index("ix_alert_outcome_records_outcome_status", "outcome_status"),
        Index("ix_alert_outcome_records_evaluated_at", "evaluated_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    program_id = Column(
        UUID(as_uuid=True),
        ForeignKey("programs.id", ondelete="CASCADE"),
        nullable=False,
    )
    alert_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notification_alert_records.id", ondelete="CASCADE"),
        nullable=False,
    )
    scope_target_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scope_targets.id", ondelete="SET NULL"),
        nullable=True,
    )
    analyst_case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analyst_case_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    outcome_status = Column(Text, nullable=False)
    acknowledgement_latency_seconds = Column(Integer, nullable=True)
    led_to_case = Column(Boolean, nullable=False, server_default="false")
    led_to_reportable = Column(Boolean, nullable=False, server_default="false")
    reasoning_summary = Column(Text, nullable=True)
    outcome_fingerprint = Column(Text, nullable=False)
    details_json = Column(JSON, nullable=False, server_default="{}")
    evaluated_at = Column(
        UTCAwareDatetime,
        nullable=False,
        server_default=func.now(),
    )

    program = relationship("Program")
    alert = relationship("NotificationAlertRecord")
    scope_target = relationship("ScopeTarget")
    analyst_case = relationship("AnalystCaseRecord")


class AgentRegistryRecord(Base, TimestampMixin):
    __tablename__ = "agent_registry_records"
    __table_args__ = (
        UniqueConstraint("agent_id", name="uq_agent_registry_records_agent_id"),
        CheckConstraint(
            "btrim(agent_id) <> ''",
            name="agent_registry_records_agent_id_not_empty",
        ),
        CheckConstraint(
            "btrim(agent_name) <> ''",
            name="agent_registry_records_agent_name_not_empty",
        ),
        CheckConstraint(
            "btrim(agent_role) <> ''",
            name="agent_registry_records_agent_role_not_empty",
        ),
        CheckConstraint(
            "btrim(category) <> ''",
            name="agent_registry_records_category_not_empty",
        ),
        CheckConstraint(
            "btrim(model_runtime) <> ''",
            name="agent_registry_records_model_runtime_not_empty",
        ),
        CheckConstraint(
            "confidence_threshold >= 0.0 AND confidence_threshold <= 1.0",
            name="agent_registry_records_confidence_bounds",
        ),
        CheckConstraint(
            "max_runtime_seconds >= 1",
            name="agent_registry_records_runtime_positive",
        ),
        Index("ix_agent_registry_records_enabled", "enabled"),
        Index("ix_agent_registry_records_agent_role", "agent_role"),
        Index("ix_agent_registry_records_category", "category"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(Text, nullable=False)
    agent_name = Column(Text, nullable=False)
    agent_role = Column(Text, nullable=False)
    category = Column(Text, nullable=False)
    purpose = Column(Text, nullable=False)
    allowed_tools_json = Column(JSON, nullable=False, server_default="[]")
    forbidden_tools_json = Column(JSON, nullable=False, server_default="[]")
    input_schema_reference = Column(Text, nullable=False)
    output_schema_reference = Column(Text, nullable=False)
    model_preference = Column(Text, nullable=False)
    model_runtime = Column(Text, nullable=False, server_default="self_hosted")
    confidence_threshold = Column(Float, nullable=False, server_default="0.65")
    max_runtime_seconds = Column(Integer, nullable=False, server_default="120")
    retry_policy_json = Column(JSON, nullable=False, server_default="{}")
    escalation_agent_id = Column(Text, nullable=True)
    enabled = Column(Boolean, nullable=False, server_default="true")
    safety_notes = Column(Text, nullable=True)
    observability_tags_json = Column(JSON, nullable=False, server_default="[]")
    details_json = Column(JSON, nullable=False, server_default="{}")


class AgentExecutionRecord(Base, TimestampMixin):
    __tablename__ = "agent_execution_records"
    __table_args__ = (
        CheckConstraint(
            "btrim(agent_id) <> ''",
            name="agent_execution_records_agent_id_not_empty",
        ),
        CheckConstraint(
            "btrim(model_used) <> ''",
            name="agent_execution_records_model_used_not_empty",
        ),
        CheckConstraint(
            "execution_status IN ('SUCCEEDED', 'FAILED', 'ESCALATED', 'DEFERRED', 'RETRIED')",
            name="agent_execution_records_status_allowed",
        ),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)",
            name="agent_execution_records_confidence_bounds",
        ),
        CheckConstraint(
            "duration_ms IS NULL OR duration_ms >= 0",
            name="agent_execution_records_duration_non_negative",
        ),
        Index("ix_agent_execution_records_program_id", "program_id"),
        Index("ix_agent_execution_records_scope_target_id", "scope_target_id"),
        Index("ix_agent_execution_records_workflow_run_id", "workflow_run_id"),
        Index("ix_agent_execution_records_case_id", "analyst_case_id"),
        Index("ix_agent_execution_records_queue_item_id", "analyst_queue_item_id"),
        Index("ix_agent_execution_records_registry_id", "agent_registry_id"),
        Index("ix_agent_execution_records_agent_id", "agent_id"),
        Index("ix_agent_execution_records_status", "execution_status"),
        Index("ix_agent_execution_records_started_at", "started_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_registry_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_registry_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    agent_id = Column(Text, nullable=False)
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
    analyst_case_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analyst_case_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    analyst_queue_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("analyst_queue_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    input_ref = Column(Text, nullable=True)
    input_hash = Column(Text, nullable=True)
    output_json = Column(JSON, nullable=False, server_default="{}")
    model_used = Column(Text, nullable=False)
    routing_policy = Column(Text, nullable=False, server_default="self_hosted_first")
    confidence = Column(Float, nullable=True)
    execution_status = Column(Text, nullable=False)
    failure_reason = Column(Text, nullable=True)
    escalation_taken = Column(Boolean, nullable=False, server_default="false")
    escalation_agent_id = Column(Text, nullable=True)
    started_at = Column(
        UTCAwareDatetime,
        nullable=False,
        server_default=func.now(),
    )
    finished_at = Column(UTCAwareDatetime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    log_path = Column(Text, nullable=True)
    artifact_refs_json = Column(JSON, nullable=False, server_default="[]")
    details_json = Column(JSON, nullable=False, server_default="{}")

    agent_registry = relationship("AgentRegistryRecord")
    program = relationship("Program")
    scope_target = relationship("ScopeTarget")
    workflow_run = relationship("WorkflowRun")
    analyst_case = relationship("AnalystCaseRecord")
    analyst_queue_item = relationship("AnalystQueueItem")


class AgentEvaluationRecord(Base, TimestampMixin):
    __tablename__ = "agent_evaluation_records"
    __table_args__ = (
        CheckConstraint(
            "btrim(agent_id) <> ''",
            name="agent_evaluation_records_agent_id_not_empty",
        ),
        CheckConstraint(
            "btrim(benchmark_name) <> ''",
            name="agent_evaluation_records_benchmark_not_empty",
        ),
        CheckConstraint(
            "btrim(model_used) <> ''",
            name="agent_evaluation_records_model_used_not_empty",
        ),
        CheckConstraint(
            "status IN ('PASSED', 'FAILED', 'PARTIAL')",
            name="agent_evaluation_records_status_allowed",
        ),
        CheckConstraint(
            "fixture_count >= 0",
            name="agent_evaluation_records_fixture_non_negative",
        ),
        CheckConstraint(
            "passed_count >= 0",
            name="agent_evaluation_records_passed_non_negative",
        ),
        CheckConstraint(
            "failed_count >= 0",
            name="agent_evaluation_records_failed_non_negative",
        ),
        CheckConstraint(
            "avg_confidence IS NULL OR (avg_confidence >= 0.0 AND avg_confidence <= 1.0)",
            name="agent_evaluation_records_confidence_bounds",
        ),
        CheckConstraint(
            "avg_latency_ms IS NULL OR avg_latency_ms >= 0",
            name="agent_evaluation_records_latency_non_negative",
        ),
        CheckConstraint(
            "success_rate >= 0.0 AND success_rate <= 1.0",
            name="agent_evaluation_records_success_rate_bounds",
        ),
        Index("ix_agent_evaluation_records_agent_id", "agent_id"),
        Index("ix_agent_evaluation_records_status", "status"),
        Index("ix_agent_evaluation_records_executed_at", "executed_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_registry_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_registry_records.id", ondelete="SET NULL"),
        nullable=True,
    )
    agent_id = Column(Text, nullable=False)
    benchmark_name = Column(Text, nullable=False)
    model_used = Column(Text, nullable=False)
    fixture_count = Column(Integer, nullable=False, server_default="0")
    passed_count = Column(Integer, nullable=False, server_default="0")
    failed_count = Column(Integer, nullable=False, server_default="0")
    avg_confidence = Column(Float, nullable=True)
    avg_latency_ms = Column(Integer, nullable=True)
    success_rate = Column(Float, nullable=False, server_default="0.0")
    status = Column(Text, nullable=False)
    results_json = Column(JSON, nullable=False, server_default="{}")
    run_by = Column(Text, nullable=True)
    run_reason = Column(Text, nullable=True)
    executed_at = Column(
        UTCAwareDatetime,
        nullable=False,
        server_default=func.now(),
    )

    agent_registry = relationship("AgentRegistryRecord")
