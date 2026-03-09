from __future__ import annotations

from apps.backend.src.models import Base
from apps.backend.src.models.campaign import (
    ApprovalGate,
    Artifact,
    AuditEvent,
    ExecutionBranch,
    Observation,
    PhaseJob,
    ScanNote,
    SubmissionDraft,
    ToolExecution,
)
from apps.backend.src.models.intention import IntentionRecord


def _fk_targets(table_name: str, column_name: str) -> set[str]:
    table = Base.metadata.tables[table_name]
    column = table.c[column_name]
    return {fk.target_fullname for fk in column.foreign_keys}


def test_canonical_execution_tables_exist():
    expected = {
        "programs",
        "scope_targets",
        "campaign_runs",
        "execution_branches",
        "phase_jobs",
        "approval_gates",
        "tool_executions",
        "artifacts",
        "observations",
        "scan_notes",
        "submission_drafts",
        "audit_events",
        "intention_records",
    }
    assert expected.issubset(set(Base.metadata.tables))


def test_campaign_branch_phase_tool_fk_chain():
    assert "campaign_runs.id" in _fk_targets("execution_branches", "campaign_id")
    assert "execution_branches.id" in _fk_targets("phase_jobs", "branch_id")
    assert "phase_jobs.id" in _fk_targets("tool_executions", "phase_job_id")
    assert "tool_executions.id" in _fk_targets("artifacts", "tool_execution_id")


def test_artifact_observation_finding_report_linkage():
    assert "findings.id" in _fk_targets("artifacts", "finding_id")
    assert "reports.id" in _fk_targets("artifacts", "report_id")
    assert "artifacts.id" in _fk_targets("observations", "source_artifact_id")
    assert "findings.id" in _fk_targets("observations", "finding_id")


def test_intention_linkage_columns_exist_on_action_tables():
    action_tables = [
        "approval_gates",
        "tool_executions",
        "artifacts",
        "observations",
        "scan_notes",
        "submission_drafts",
        "audit_events",
    ]
    for table_name in action_tables:
        assert "intention_id" in Base.metadata.tables[table_name].c


def test_downstream_intention_relationships_are_wired():
    assert ApprovalGate.intention.property.back_populates == "approval_gates"
    assert ToolExecution.intention.property.back_populates == "tool_executions"
    assert Artifact.intention.property.back_populates == "artifacts"
    assert Observation.intention.property.back_populates == "observations"
    assert ScanNote.intention.property.back_populates == "scan_notes"
    assert SubmissionDraft.intention.property.back_populates == "submission_drafts"
    assert AuditEvent.intention.property.back_populates == "audit_events"

    assert IntentionRecord.approval_gates.property.back_populates == "intention"
    assert IntentionRecord.tool_executions.property.back_populates == "intention"
    assert IntentionRecord.artifacts.property.back_populates == "intention"
    assert IntentionRecord.observations.property.back_populates == "intention"
    assert IntentionRecord.scan_notes.property.back_populates == "intention"
    assert IntentionRecord.submission_drafts.property.back_populates == "intention"
    assert IntentionRecord.audit_events.property.back_populates == "intention"


def test_self_referential_relationship_helpers_are_wired():
    assert ExecutionBranch.parent_branch.property.back_populates == "child_branches"
    assert ExecutionBranch.child_branches.property.back_populates == "parent_branch"
    assert ExecutionBranch.depends_on_branch.property.back_populates == "dependent_branches"
    assert ExecutionBranch.dependent_branches.property.back_populates == "depends_on_branch"

    assert PhaseJob.depends_on_job.property.back_populates == "dependent_jobs"
    assert PhaseJob.dependent_jobs.property.back_populates == "depends_on_job"

    assert IntentionRecord.parent_intention.property.back_populates == "child_intentions"
    assert IntentionRecord.child_intentions.property.back_populates == "parent_intention"
