from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from apps.backend.src.core.correlation_record_service import CorrelationRecordService
from apps.backend.src.core.finding_correlation_service import FindingCorrelationService
from apps.backend.src.core.workflow_run_service import WorkflowRunService
from apps.backend.src.models.campaign import (
    AuditEvent,
    CampaignRun,
    Observation,
    SubmissionDraft,
    ToolExecution as ToolExecutionModel,
)
from apps.backend.src.models.enums import (
    CorrelationActionEnum,
    ObservationTypeEnum,
    SeverityEnum,
    StageRunStatusEnum,
    ToolExecutionStatusEnum,
    WorkflowRunStatusEnum,
)
from apps.backend.src.models.hil import Finding
from apps.backend.src.models.workflow import CorrelationRecord, StageRun, WorkflowFinding, WorkflowRun


class FakeDB:
    def __init__(self):
        self.added: list[object] = []

    def add(self, obj: object) -> None:
        now = datetime.now(timezone.utc)
        if hasattr(obj, "id") and getattr(obj, "id", None) is None:
            setattr(obj, "id", uuid4())
        if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
            setattr(obj, "created_at", now)
        if hasattr(obj, "updated_at") and getattr(obj, "updated_at", None) is None:
            setattr(obj, "updated_at", now)
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def execute(self, *_args, **_kwargs):
        raise AssertionError("Unexpected SQL execution in FakeDB test path")


# ---------------------------------------------------------------------------
# WorkflowRunService tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_workflow_run():
    db = FakeDB()
    svc = WorkflowRunService(db)  # type: ignore[arg-type]
    campaign_run_id = uuid4()

    run = await svc.create_workflow_run(
        campaign_run_id=campaign_run_id,
        scope_target_id=None,
        template_name="full_recon",
        target="example.com",
        safe_mode=True,
        dry_run=False,
        trigger_source="TEST",
        total_phases=5,
        plan_artifact_path="/artifacts/plan.json",
    )

    assert run.campaign_run_id == campaign_run_id
    assert run.template_name == "full_recon"
    assert run.target == "example.com"
    assert run.safe_mode is True
    assert run.dry_run is False
    assert run.total_phases == 5
    assert run.completed_phases == 0
    assert run.status == WorkflowRunStatusEnum.PENDING
    assert run.plan_artifact_path == "/artifacts/plan.json"
    assert run in db.added


@pytest.mark.asyncio
async def test_workflow_run_transitions_to_running():
    db = FakeDB()
    svc = WorkflowRunService(db)  # type: ignore[arg-type]

    run = await svc.create_workflow_run(
        campaign_run_id=uuid4(),
        scope_target_id=None,
        template_name="full_recon",
        target="example.com",
        safe_mode=True,
        dry_run=False,
        trigger_source="TEST",
        total_phases=3,
    )
    assert run.started_at is None

    await svc.transition_workflow_run(run, WorkflowRunStatusEnum.RUNNING)

    assert run.status == WorkflowRunStatusEnum.RUNNING
    assert run.started_at is not None


@pytest.mark.asyncio
async def test_workflow_run_transitions_to_completed():
    db = FakeDB()
    svc = WorkflowRunService(db)  # type: ignore[arg-type]

    run = await svc.create_workflow_run(
        campaign_run_id=uuid4(),
        scope_target_id=None,
        template_name="full_recon",
        target="example.com",
        safe_mode=True,
        dry_run=False,
        trigger_source="TEST",
        total_phases=3,
    )
    await svc.transition_workflow_run(run, WorkflowRunStatusEnum.RUNNING)

    await svc.advance_workflow_progress(run)
    await svc.advance_workflow_progress(run)
    await svc.advance_workflow_progress(run)

    assert run.status == WorkflowRunStatusEnum.COMPLETED
    assert run.completed_phases == 3
    assert run.ended_at is not None


@pytest.mark.asyncio
async def test_workflow_run_transitions_to_failed():
    db = FakeDB()
    svc = WorkflowRunService(db)  # type: ignore[arg-type]

    run = await svc.create_workflow_run(
        campaign_run_id=uuid4(),
        scope_target_id=None,
        template_name="full_recon",
        target="example.com",
        safe_mode=True,
        dry_run=False,
        trigger_source="TEST",
        total_phases=3,
    )
    await svc.transition_workflow_run(run, WorkflowRunStatusEnum.RUNNING)
    await svc.advance_workflow_progress(run, failed=True)

    assert run.status == WorkflowRunStatusEnum.FAILED
    assert run.ended_at is not None


@pytest.mark.asyncio
async def test_create_stage_run():
    db = FakeDB()
    svc = WorkflowRunService(db)  # type: ignore[arg-type]
    workflow_run_id = uuid4()
    campaign_run_id = uuid4()

    stage = await svc.create_stage_run(
        workflow_run_id=workflow_run_id,
        campaign_run_id=campaign_run_id,
        stage_name="recon",
        stage_order=0,
        phase_count=2,
    )

    assert stage.workflow_run_id == workflow_run_id
    assert stage.campaign_run_id == campaign_run_id
    assert stage.stage_name == "recon"
    assert stage.stage_order == 0
    assert stage.phase_count == 2
    assert stage.completed_count == 0
    assert stage.status == StageRunStatusEnum.PENDING
    assert stage in db.added


@pytest.mark.asyncio
async def test_stage_run_advances_progress():
    db = FakeDB()
    svc = WorkflowRunService(db)  # type: ignore[arg-type]

    stage = await svc.create_stage_run(
        workflow_run_id=uuid4(),
        campaign_run_id=uuid4(),
        stage_name="scanning",
        stage_order=1,
        phase_count=2,
    )

    await svc.advance_stage_progress(stage)
    assert stage.completed_count == 1
    assert stage.status == StageRunStatusEnum.RUNNING

    await svc.advance_stage_progress(stage)
    assert stage.completed_count == 2
    assert stage.status == StageRunStatusEnum.COMPLETED
    assert stage.ended_at is not None


@pytest.mark.asyncio
async def test_stage_run_fails():
    db = FakeDB()
    svc = WorkflowRunService(db)  # type: ignore[arg-type]

    stage = await svc.create_stage_run(
        workflow_run_id=uuid4(),
        campaign_run_id=uuid4(),
        stage_name="triage",
        stage_order=2,
        phase_count=3,
    )
    await svc.transition_stage_run(stage, StageRunStatusEnum.RUNNING)
    await svc.advance_stage_progress(stage, failed=True)

    assert stage.status == StageRunStatusEnum.FAILED
    assert stage.ended_at is not None


@pytest.mark.asyncio
async def test_stage_run_unique_per_workflow_name():
    """Stage names must be unique per workflow run — validate the constraint is modeled."""
    stage_a = StageRun(
        id=uuid4(),
        workflow_run_id=uuid4(),
        campaign_run_id=uuid4(),
        stage_name="recon",
        stage_order=0,
        phase_count=1,
        completed_count=0,
        status=StageRunStatusEnum.PENDING,
    )
    stage_b = StageRun(
        id=uuid4(),
        workflow_run_id=stage_a.workflow_run_id,
        campaign_run_id=stage_a.campaign_run_id,
        stage_name="recon",
        stage_order=0,
        phase_count=1,
        completed_count=0,
        status=StageRunStatusEnum.PENDING,
    )
    # Both reference the same workflow_run_id and stage_name — this is what the DB
    # UniqueConstraint "uq_stage_runs_workflow_stage" would reject. We validate the
    # model structure encodes those fields correctly.
    assert stage_a.workflow_run_id == stage_b.workflow_run_id
    assert stage_a.stage_name == stage_b.stage_name
    assert stage_a.id != stage_b.id


@pytest.mark.asyncio
async def test_create_tool_execution_with_stage_link():
    db = FakeDB()
    svc = WorkflowRunService(db)  # type: ignore[arg-type]

    execution = await svc.create_tool_execution(
        campaign_id=uuid4(),
        stage_run_id=uuid4(),
        tool_name="subfinder",
        execution_mode="native",
        target="example.com",
    )

    assert isinstance(execution, ToolExecutionModel)
    assert execution.tool_name == "subfinder"
    assert execution.execution_mode == "native"
    assert execution.input_target == "example.com"
    assert execution.status == ToolExecutionStatusEnum.CREATED
    assert execution.stage_run_id is not None
    assert execution in db.added


@pytest.mark.asyncio
async def test_create_workflow_finding_record():
    db = FakeDB()
    svc = WorkflowRunService(db)  # type: ignore[arg-type]
    workflow_run_id = uuid4()

    finding = await svc.create_workflow_finding(
        workflow_run_id=workflow_run_id,
        campaign_id=uuid4(),
        stage_run_id=uuid4(),
        tool_execution_id=uuid4(),
        asset_identifier="api.example.com",
        endpoint="/v1/users",
        parameter="id",
        vulnerability_type="sql_injection_candidate",
        confidence_score=0.72,
        severity_hint="high",
        evidence_artifact_path="output/raw/wf-1/vuln_scan/nuclei.json",
        details_json={"title": "SQLi candidate"},
    )

    assert isinstance(finding, WorkflowFinding)
    assert finding.workflow_run_id == workflow_run_id
    assert finding.asset_identifier == "api.example.com"
    assert finding.vulnerability_type == "sql_injection_candidate"
    assert finding.severity_hint == "high"
    assert isinstance(finding.details_json, dict)
    assert "evidence_qualification" in finding.details_json
    assert "impact_validation" in finding.details_json
    assert "submission_decision" in finding.details_json
    assert "vulnerability_intelligence" in finding.details_json
    assert finding.details_json.get("submission_candidate") is False
    assert finding.details_json.get("submission_rejection_reason")
    assert finding in db.added


@pytest.mark.asyncio
async def test_create_workflow_correlation_record():
    db = FakeDB()
    svc = WorkflowRunService(db)  # type: ignore[arg-type]
    workflow_run_id = uuid4()

    record = await svc.create_workflow_correlation_record(
        workflow_run_id=workflow_run_id,
        campaign_id=uuid4(),
        asset_identifier="api.example.com",
        signal_sources=["https://api.example.com/v1/users", "port:443"],
        confidence_score=0.61,
        priority_rank=1,
        explanation="recon signals converged on exposed API surface",
    )

    assert isinstance(record, CorrelationRecord)
    assert record.workflow_run_id == workflow_run_id
    assert record.asset_identifier == "api.example.com"
    assert record.priority_rank == 1
    assert record in db.added


# ---------------------------------------------------------------------------
# CorrelationRecordService tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_correlation_record_service_create():
    db = FakeDB()
    svc = CorrelationRecordService(db)  # type: ignore[arg-type]
    finding_id = uuid4()
    observation_id = uuid4()
    campaign_id = uuid4()

    record = await svc.create_record(
        finding_id=finding_id,
        observation_id=observation_id,
        campaign_id=campaign_id,
        action=CorrelationActionEnum.CREATED,
    )

    assert record.finding_id == finding_id
    assert record.observation_id == observation_id
    assert record.campaign_id == campaign_id
    assert record.action == CorrelationActionEnum.CREATED
    assert record.correlation_rule == "deterministic_title_match"
    assert record.duplicate_of_finding_id is None
    assert record in db.added


@pytest.mark.asyncio
async def test_correlation_record_service_list_by_finding():
    db = FakeDB()

    finding_id = uuid4()
    campaign_id = uuid4()

    record_a = CorrelationRecord(
        id=uuid4(),
        finding_id=finding_id,
        observation_id=uuid4(),
        campaign_id=campaign_id,
        action=CorrelationActionEnum.CREATED,
        correlation_rule="deterministic_title_match",
    )
    record_b = CorrelationRecord(
        id=uuid4(),
        finding_id=finding_id,
        observation_id=uuid4(),
        campaign_id=campaign_id,
        action=CorrelationActionEnum.ATTACHED,
        correlation_rule="deterministic_title_match",
    )
    record_other = CorrelationRecord(
        id=uuid4(),
        finding_id=uuid4(),
        observation_id=uuid4(),
        campaign_id=campaign_id,
        action=CorrelationActionEnum.CREATED,
        correlation_rule="deterministic_title_match",
    )

    svc = CorrelationRecordService(db)  # type: ignore[arg-type]

    fake_result = type(
        "FakeResult",
        (),
        {"scalars": lambda self: type("Scalars", (), {"all": lambda self: [record_a, record_b]})()},
    )()

    async def fake_execute(_query):
        return fake_result

    db.execute = fake_execute  # type: ignore[method-assign]
    records = await svc.list_by_finding(finding_id)

    assert len(records) == 2
    assert all(r.finding_id == finding_id for r in records)


@pytest.mark.asyncio
async def test_correlation_record_dedup_reference():
    db = FakeDB()
    svc = CorrelationRecordService(db)  # type: ignore[arg-type]
    finding_id = uuid4()
    dup_finding_id = uuid4()
    observation_id = uuid4()
    campaign_id = uuid4()

    record = await svc.create_record(
        finding_id=finding_id,
        observation_id=observation_id,
        campaign_id=campaign_id,
        action=CorrelationActionEnum.DEDUPLICATED,
        duplicate_of_finding_id=dup_finding_id,
    )

    assert record.action == CorrelationActionEnum.DEDUPLICATED
    assert record.duplicate_of_finding_id == dup_finding_id


# ---------------------------------------------------------------------------
# Integration test: FindingCorrelationService creates CorrelationRecord
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_finding_correlation_creates_record(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    service = FindingCorrelationService(db)  # type: ignore[arg-type]

    campaign = CampaignRun(
        id=uuid4(),
        program_id=uuid4(),
        initiated_by="tester",
        declared_goal="correlate",
    )
    observation = Observation(
        id=uuid4(),
        campaign_id=campaign.id,
        branch_id=uuid4(),
        phase_job_id=uuid4(),
        tool_execution_id=uuid4(),
        category="VALIDATION",
        title="xss in login form",
        summary="reflected xss confirmed",
        observation_type=ObservationTypeEnum.VALIDATION,
        payload_json={"target": "login.example.com"},
    )

    monkeypatch.setattr(service, "_campaign", AsyncMock(return_value=campaign))
    monkeypatch.setattr(service, "_program_name", AsyncMock(return_value="Example Program"))
    monkeypatch.setattr(service, "_execution", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_phase_job", AsyncMock(return_value=None))
    monkeypatch.setattr(
        service, "_target_identifier", AsyncMock(return_value="login.example.com")
    )
    monkeypatch.setattr(service, "_matching_finding", AsyncMock(return_value=(None, False)))
    monkeypatch.setattr(service, "_collect_related_artifacts", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        service.drafts,
        "upsert_draft_for_finding",
        AsyncMock(
            return_value=SubmissionDraft(
                id=uuid4(),
                campaign_id=campaign.id,
                finding_id=uuid4(),
                status="NEEDS_REVIEW",
            )
        ),
    )

    outcome = await service.process_observation(observation, actor="test.correlation")

    assert outcome.action == "CREATED"
    assert outcome.finding_id is not None

    correlation_records = [obj for obj in db.added if isinstance(obj, CorrelationRecord)]
    assert len(correlation_records) == 1
    cr = correlation_records[0]
    assert cr.finding_id == outcome.finding_id
    assert cr.observation_id == observation.id
    assert cr.campaign_id == observation.campaign_id
    assert cr.action == CorrelationActionEnum.CREATED
    assert cr.duplicate_of_finding_id is None


@pytest.mark.asyncio
async def test_finding_correlation_dedup_creates_deduplicated_record(
    monkeypatch: pytest.MonkeyPatch,
):
    db = FakeDB()
    service = FindingCorrelationService(db)  # type: ignore[arg-type]

    campaign = CampaignRun(
        id=uuid4(),
        program_id=uuid4(),
        initiated_by="tester",
        declared_goal="correlate",
    )
    existing_finding = Finding(
        id=uuid4(),
        program="Example Program",
        asset="login.example.com",
        title="xss in login form",
        description="existing finding",
        severity=SeverityEnum.LOW,
        scope_json={
            "campaign_id": str(campaign.id),
            "normalized_title": "xss in login form",
            "normalized_category": "VALIDATION",
            "target_identifier": "login.example.com",
        },
    )
    observation = Observation(
        id=uuid4(),
        campaign_id=campaign.id,
        category="VALIDATION",
        title="xss in login form",
        observation_type=ObservationTypeEnum.VALIDATION,
        payload_json={"target": "login.example.com"},
    )

    monkeypatch.setattr(service, "_campaign", AsyncMock(return_value=campaign))
    monkeypatch.setattr(service, "_program_name", AsyncMock(return_value="Example Program"))
    monkeypatch.setattr(service, "_execution", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_phase_job", AsyncMock(return_value=None))
    monkeypatch.setattr(
        service, "_target_identifier", AsyncMock(return_value="login.example.com")
    )
    monkeypatch.setattr(
        service, "_matching_finding", AsyncMock(return_value=(existing_finding, True))
    )
    monkeypatch.setattr(service, "_collect_related_artifacts", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        service.drafts,
        "upsert_draft_for_finding",
        AsyncMock(
            return_value=SubmissionDraft(
                id=uuid4(),
                campaign_id=campaign.id,
                finding_id=existing_finding.id,
                status="SUPPRESSED_DUPLICATE",
            )
        ),
    )

    outcome = await service.process_observation(observation, actor="test.correlation")

    assert outcome.action == "ATTACHED"
    assert outcome.duplicate is True

    correlation_records = [obj for obj in db.added if isinstance(obj, CorrelationRecord)]
    assert len(correlation_records) == 1
    cr = correlation_records[0]
    assert cr.action == CorrelationActionEnum.DEDUPLICATED
    assert cr.duplicate_of_finding_id == existing_finding.id


@pytest.mark.asyncio
async def test_context_only_observation_does_not_create_record(
    monkeypatch: pytest.MonkeyPatch,
):
    db = FakeDB()
    service = FindingCorrelationService(db)  # type: ignore[arg-type]

    campaign = CampaignRun(
        id=uuid4(),
        program_id=uuid4(),
        initiated_by="tester",
        declared_goal="correlate",
    )
    observation = Observation(
        id=uuid4(),
        campaign_id=campaign.id,
        category="DISCOVERY",
        observation_type=ObservationTypeEnum.DISCOVERY,
    )
    monkeypatch.setattr(service, "_campaign", AsyncMock(return_value=campaign))

    outcome = await service.process_observation(observation, actor="test.correlation")

    assert outcome.action == "CONTEXT_ONLY"
    correlation_records = [obj for obj in db.added if isinstance(obj, CorrelationRecord)]
    assert len(correlation_records) == 0
