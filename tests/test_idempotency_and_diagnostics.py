from __future__ import annotations

import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

import apps.backend.src.routers.campaigns as campaigns_router
from apps.backend.src.core.approval_gate_service import ApprovalGateService
from apps.backend.src.core.branch_scheduler import BranchScheduler, SchedulerResult
from apps.backend.src.core.execution_result_service import ExecutionResultIngestionService
from apps.backend.src.core.finding_correlation_service import (
    CorrelationResult,
    FindingCorrelationService,
)
from apps.backend.src.core.finding_review_service import FindingReviewService
from apps.backend.src.core.metrics_service import MetricsService
from apps.backend.src.core.submission_export_service import SubmissionExportResult
from apps.backend.src.models.campaign import (
    ApprovalGate,
    Artifact,
    AuditEvent,
    CampaignRun,
    ExecutionBranch,
    Observation,
    PhaseJob,
    SubmissionDraft,
    ToolExecution,
)
from apps.backend.src.models.enums import (
    ApprovalGateStatusEnum,
    BranchStatusEnum,
    CampaignStatusEnum,
    FindingStatusEnum,
    PhaseJobStatusEnum,
    SeverityEnum,
    ToolExecutionStatusEnum,
)
from apps.backend.src.models.hil import Evidence, Finding
from apps.backend.src.schemas.campaigns import ApprovalGateDecision, ExecutionResultIngestRequest


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


class _Result:
    def __init__(self, *, rows: list[object] | None = None, scalar_value=None):
        self._rows = rows or []
        self._scalar_value = scalar_value

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def scalar(self):
        return self._scalar_value

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class SequenceDB(FakeDB):
    def __init__(self, results: list[_Result]):
        super().__init__()
        self._results = list(results)
        self._idx = 0

    async def execute(self, *_args, **_kwargs):
        result = self._results[self._idx]
        self._idx += 1
        return result


def _seed_execution_graph() -> tuple[CampaignRun, ExecutionBranch, PhaseJob, ToolExecution]:
    campaign = CampaignRun(
        id=uuid4(),
        program_id=uuid4(),
        initiated_by="worker@test",
        declared_goal="Replay safety",
        status=CampaignStatusEnum.RUNNING,
    )
    branch = ExecutionBranch(
        id=uuid4(),
        campaign_id=campaign.id,
        branch_key="root",
        status=BranchStatusEnum.RUNNING,
    )
    phase = PhaseJob(
        id=uuid4(),
        campaign_id=campaign.id,
        branch_id=branch.id,
        phase_name="recon_discovery",
        phase_order=10,
        status=PhaseJobStatusEnum.QUEUED,
        input_payload_json={"seed_intention_id": str(uuid4())},
    )
    execution = ToolExecution(
        id=uuid4(),
        campaign_id=campaign.id,
        branch_id=branch.id,
        phase_job_id=phase.id,
        tool_name="phase::recon_discovery",
        adapter_name="placeholder.dispatch",
        status=ToolExecutionStatusEnum.QUEUED,
        worker_task_id="task-replay-1",
    )
    return campaign, branch, phase, execution


@pytest.mark.asyncio
async def test_replayed_ingestion_does_not_duplicate_artifacts_or_observations(
    monkeypatch: pytest.MonkeyPatch,
):
    db = FakeDB()
    campaign, branch, phase, execution = _seed_execution_graph()
    svc = ExecutionResultIngestionService(db)  # type: ignore[arg-type]

    monkeypatch.setattr(svc, "_resolve_execution", AsyncMock(return_value=execution))
    monkeypatch.setattr(svc.campaigns.repo, "get_campaign", AsyncMock(return_value=campaign))
    monkeypatch.setattr(svc.campaigns.repo, "get_branch", AsyncMock(return_value=branch))
    monkeypatch.setattr(svc.campaigns.repo, "get_phase_job", AsyncMock(return_value=phase))
    monkeypatch.setattr(
        FindingCorrelationService,
        "process_observation",
        AsyncMock(return_value=CorrelationResult(observation_id=uuid4(), action="CONTEXT_ONLY")),
    )
    monkeypatch.setattr(
        svc,
        "_scheduler_summary",
        AsyncMock(
            return_value=SchedulerResult(
                campaign_id=campaign.id,
                considered_jobs=1,
                queued_jobs=0,
                blocked_jobs=0,
                waiting_approval_jobs=0,
                created_approval_gates=0,
                dispatched_tool_executions=0,
            )
        ),
    )

    async def find_ingested_event(*, execution_id: UUID, ingestion_fingerprint: str):
        for item in db.added:
            if not isinstance(item, AuditEvent):
                continue
            if (
                item.tool_execution_id != execution_id
                or item.event_type != "phase_job.result.ingested"
            ):
                continue
            payload = item.event_payload_json if isinstance(item.event_payload_json, dict) else {}
            if payload.get("ingestion_fingerprint") == ingestion_fingerprint:
                return item
        return None

    async def load_side_effects(execution_id: UUID):
        artifacts = [
            item
            for item in db.added
            if isinstance(item, Artifact) and item.tool_execution_id == execution_id
        ]
        observations = [
            item
            for item in db.added
            if isinstance(item, Observation) and item.tool_execution_id == execution_id
        ]
        return artifacts, observations

    monkeypatch.setattr(svc, "_find_ingested_event", find_ingested_event)
    monkeypatch.setattr(svc, "_load_execution_side_effects", load_side_effects)

    request = ExecutionResultIngestRequest(
        worker_task_id=execution.worker_task_id,
        tool_status=ToolExecutionStatusEnum.COMPLETED,
        result_payload_json={"status": "completed", "assets": ["example.com"]},
        trigger_scheduler=False,
    )
    first = await svc.ingest_result(request, actor="worker.test")
    artifact_count = len([obj for obj in db.added if isinstance(obj, Artifact)])
    observation_count = len([obj for obj in db.added if isinstance(obj, Observation)])

    second = await svc.ingest_result(request, actor="worker.test")

    assert len([obj for obj in db.added if isinstance(obj, Artifact)]) == artifact_count
    assert len([obj for obj in db.added if isinstance(obj, Observation)]) == observation_count
    assert second.artifact_ids == first.artifact_ids
    assert second.observation_ids == first.observation_ids
    assert any(
        isinstance(obj, AuditEvent) and obj.event_type == "phase_job.result.replay_ignored"
        for obj in db.added
    )


@pytest.mark.asyncio
async def test_replayed_ingestion_does_not_duplicate_findings(
    monkeypatch: pytest.MonkeyPatch,
):
    db = FakeDB()
    campaign, branch, phase, execution = _seed_execution_graph()
    svc = ExecutionResultIngestionService(db)  # type: ignore[arg-type]

    monkeypatch.setattr(svc, "_resolve_execution", AsyncMock(return_value=execution))
    monkeypatch.setattr(svc.campaigns.repo, "get_campaign", AsyncMock(return_value=campaign))
    monkeypatch.setattr(svc.campaigns.repo, "get_branch", AsyncMock(return_value=branch))
    monkeypatch.setattr(svc.campaigns.repo, "get_phase_job", AsyncMock(return_value=phase))

    correlation_calls: list[UUID] = []

    async def correlate_once(
        observation: Observation, *, actor: str | None = None
    ) -> CorrelationResult:
        finding = Finding(
            id=uuid4(),
            program="Replay Program",
            asset="api.replay.test",
            title="Replay finding",
            description="Created only on first ingestion",
            severity=SeverityEnum.LOW,
            status=FindingStatusEnum.NEW,
            scope_json={"campaign_id": str(campaign.id), "actor": actor},
        )
        db.add(finding)
        observation.finding_id = finding.id
        correlation_calls.append(observation.id)
        return CorrelationResult(
            observation_id=observation.id,
            action="CREATED",
            finding_id=finding.id,
            evidence_created=0,
            draft_created=False,
            duplicate=False,
        )

    monkeypatch.setattr(
        FindingCorrelationService, "process_observation", AsyncMock(side_effect=correlate_once)
    )

    async def find_ingested_event(*, execution_id: UUID, ingestion_fingerprint: str):
        for item in db.added:
            if not isinstance(item, AuditEvent):
                continue
            if (
                item.tool_execution_id != execution_id
                or item.event_type != "phase_job.result.ingested"
            ):
                continue
            payload = item.event_payload_json if isinstance(item.event_payload_json, dict) else {}
            if payload.get("ingestion_fingerprint") == ingestion_fingerprint:
                return item
        return None

    async def load_side_effects(execution_id: UUID):
        artifacts = [
            item
            for item in db.added
            if isinstance(item, Artifact) and item.tool_execution_id == execution_id
        ]
        observations = [
            item
            for item in db.added
            if isinstance(item, Observation) and item.tool_execution_id == execution_id
        ]
        return artifacts, observations

    monkeypatch.setattr(svc, "_find_ingested_event", find_ingested_event)
    monkeypatch.setattr(svc, "_load_execution_side_effects", load_side_effects)

    request = ExecutionResultIngestRequest(
        worker_task_id=execution.worker_task_id,
        tool_status=ToolExecutionStatusEnum.COMPLETED,
        result_payload_json={"status": "completed", "assets": ["replay.test"]},
        trigger_scheduler=False,
    )
    await svc.ingest_result(request, actor="worker.test")
    await svc.ingest_result(request, actor="worker.test")

    created_findings = [obj for obj in db.added if isinstance(obj, Finding)]
    assert len(created_findings) == 1
    assert len(correlation_calls) == 1


@pytest.mark.asyncio
async def test_terminal_replay_conflict_is_deterministic(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    campaign, branch, phase, execution = _seed_execution_graph()
    svc = ExecutionResultIngestionService(db)  # type: ignore[arg-type]

    monkeypatch.setattr(svc, "_resolve_execution", AsyncMock(return_value=execution))
    monkeypatch.setattr(svc.campaigns.repo, "get_campaign", AsyncMock(return_value=campaign))
    monkeypatch.setattr(svc.campaigns.repo, "get_branch", AsyncMock(return_value=branch))
    monkeypatch.setattr(svc.campaigns.repo, "get_phase_job", AsyncMock(return_value=phase))
    monkeypatch.setattr(
        FindingCorrelationService,
        "process_observation",
        AsyncMock(return_value=CorrelationResult(observation_id=uuid4(), action="CONTEXT_ONLY")),
    )

    async def find_ingested_event(*, execution_id: UUID, ingestion_fingerprint: str):
        for item in db.added:
            if not isinstance(item, AuditEvent):
                continue
            if (
                item.tool_execution_id != execution_id
                or item.event_type != "phase_job.result.ingested"
            ):
                continue
            payload = item.event_payload_json if isinstance(item.event_payload_json, dict) else {}
            if payload.get("ingestion_fingerprint") == ingestion_fingerprint:
                return item
        return None

    async def latest_ingested_event(execution_id: UUID):
        events = [
            item
            for item in db.added
            if isinstance(item, AuditEvent)
            and item.tool_execution_id == execution_id
            and item.event_type == "phase_job.result.ingested"
        ]
        return events[-1] if events else None

    monkeypatch.setattr(svc, "_find_ingested_event", find_ingested_event)
    monkeypatch.setattr(svc, "_latest_ingested_event", latest_ingested_event)

    await svc.ingest_result(
        ExecutionResultIngestRequest(
            worker_task_id=execution.worker_task_id,
            tool_status=ToolExecutionStatusEnum.COMPLETED,
            result_payload_json={"status": "completed"},
            trigger_scheduler=False,
        ),
        actor="worker.test",
    )

    with pytest.raises(ValueError):
        await svc.ingest_result(
            ExecutionResultIngestRequest(
                worker_task_id=execution.worker_task_id,
                tool_status=ToolExecutionStatusEnum.FAILED,
                result_payload_json={"status": "failed"},
                error_message="conflicting replay",
                trigger_scheduler=False,
            ),
            actor="worker.test",
        )

    assert any(
        isinstance(obj, AuditEvent) and obj.event_type == "phase_job.result.replay_conflict"
        for obj in db.added
    )


def _wire_scheduler(
    monkeypatch: pytest.MonkeyPatch,
    scheduler: BranchScheduler,
    *,
    campaign: CampaignRun,
    branches: list[ExecutionBranch],
    phase_jobs: list[PhaseJob],
    gates_sequence: list[dict[UUID, ApprovalGate]],
    active_sequence: list[dict[UUID, ToolExecution]],
) -> None:
    monkeypatch.setattr(scheduler.campaigns.repo, "get_campaign", AsyncMock(return_value=campaign))
    monkeypatch.setattr(scheduler.campaigns.repo, "list_branches", AsyncMock(return_value=branches))
    monkeypatch.setattr(
        scheduler.campaigns.repo, "list_phase_jobs", AsyncMock(return_value=phase_jobs)
    )
    monkeypatch.setattr(
        scheduler,
        "_latest_phase_gate_map",
        AsyncMock(side_effect=gates_sequence),
    )
    monkeypatch.setattr(
        scheduler,
        "_active_phase_execution_map",
        AsyncMock(side_effect=active_sequence),
    )


@pytest.mark.asyncio
async def test_repeated_scheduler_runs_avoid_duplicate_dispatch_and_gate_creation(
    monkeypatch: pytest.MonkeyPatch,
):
    db = FakeDB()
    campaign = CampaignRun(
        id=uuid4(),
        program_id=uuid4(),
        initiated_by="scheduler@test",
        declared_goal="scheduler idempotency",
        status=CampaignStatusEnum.RUNNING,
    )
    branch = ExecutionBranch(
        id=uuid4(),
        campaign_id=campaign.id,
        branch_key="root",
        status=BranchStatusEnum.READY,
    )
    phase = PhaseJob(
        id=uuid4(),
        campaign_id=campaign.id,
        branch_id=branch.id,
        phase_name="lightweight_analysis",
        phase_order=30,
        approval_required=True,
        status=PhaseJobStatusEnum.CREATED,
        input_payload_json={"seed_intention_id": str(uuid4())},
    )
    gate = ApprovalGate(
        id=uuid4(),
        campaign_id=campaign.id,
        branch_id=branch.id,
        phase_job_id=phase.id,
        gate_reason="Approval required",
        requested_by="scheduler@test",
        status=ApprovalGateStatusEnum.PENDING,
    )
    active_execution = ToolExecution(
        id=uuid4(),
        campaign_id=campaign.id,
        branch_id=branch.id,
        phase_job_id=phase.id,
        tool_name="phase::lightweight_analysis",
        status=ToolExecutionStatusEnum.QUEUED,
    )

    scheduler = BranchScheduler(db)  # type: ignore[arg-type]
    _wire_scheduler(
        monkeypatch,
        scheduler,
        campaign=campaign,
        branches=[branch],
        phase_jobs=[phase],
        gates_sequence=[{}, {phase.id: gate}],
        active_sequence=[{}, {phase.id: active_execution}],
    )
    monkeypatch.setattr(scheduler.approvals, "create_gate", AsyncMock(return_value=gate))
    monkeypatch.setattr(
        scheduler.dispatcher,
        "dispatch_phase_job",
        AsyncMock(return_value=(active_execution, True)),
    )

    first = await scheduler.schedule_campaign(campaign.id, actor="scheduler@test")
    phase.approval_required = False
    second = await scheduler.schedule_campaign(campaign.id, actor="scheduler@test")

    assert first.created_approval_gates == 1
    assert second.created_approval_gates == 0
    assert scheduler.approvals.create_gate.await_count == 1
    # A pending gate remains the controlling state signal; scheduler must not dispatch.
    assert scheduler.dispatcher.dispatch_phase_job.await_count == 0


@pytest.mark.asyncio
async def test_repeated_review_action_is_handled_safely(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    service = FindingReviewService(db)  # type: ignore[arg-type]
    campaign_id = uuid4()
    finding = Finding(
        id=uuid4(),
        program="Example Program",
        asset="api.example.com",
        title="validated issue",
        description="desc",
        severity=SeverityEnum.LOW,
        status=FindingStatusEnum.IN_REVIEW,
        scope_json={"campaign_id": str(campaign_id)},
    )
    draft = SubmissionDraft(
        id=uuid4(),
        campaign_id=campaign_id,
        finding_id=finding.id,
        status="NEEDS_REVIEW",
        details_json={},
    )
    monkeypatch.setattr(service, "_get_finding", AsyncMock(return_value=finding))
    monkeypatch.setattr(service, "_latest_draft", AsyncMock(return_value=draft))

    first = await service.review_finding(
        finding_id=finding.id,
        action="APPROVE",
        reviewer_id="reviewer@example.com",
    )
    second = await service.review_finding(
        finding_id=finding.id,
        action="APPROVE",
        reviewer_id="reviewer@example.com",
    )

    assert first.finding_status == FindingStatusEnum.HIL_APPROVED
    assert second.finding_status == FindingStatusEnum.HIL_APPROVED
    assert any(
        isinstance(obj, AuditEvent) and obj.event_type == "finding.review.duplicate_ignored"
        for obj in db.added
    )


@pytest.mark.asyncio
async def test_repeated_approval_decision_is_handled_safely():
    db = FakeDB()
    service = ApprovalGateService(db)  # type: ignore[arg-type]
    gate = ApprovalGate(
        id=uuid4(),
        campaign_id=uuid4(),
        gate_reason="Decision test",
        requested_by="operator@example.com",
        status=ApprovalGateStatusEnum.PENDING,
    )
    decision = ApprovalGateDecision(
        status=ApprovalGateStatusEnum.APPROVED,
        decided_by="operator@example.com",
    )

    await service.decide_gate(gate, decision, actor="operator@example.com")
    await service.decide_gate(gate, decision, actor="operator@example.com")

    assert gate.status == ApprovalGateStatusEnum.APPROVED
    assert any(
        isinstance(obj, AuditEvent) and obj.event_type == "approval_gate.decision.duplicate"
        for obj in db.added
    )


@pytest.mark.asyncio
async def test_approval_after_rejection_is_rejected_with_conflict_audit():
    db = FakeDB()
    service = ApprovalGateService(db)  # type: ignore[arg-type]
    gate = ApprovalGate(
        id=uuid4(),
        campaign_id=uuid4(),
        gate_reason="Conflict test",
        requested_by="operator@example.com",
        status=ApprovalGateStatusEnum.PENDING,
    )
    reject = ApprovalGateDecision(
        status=ApprovalGateStatusEnum.REJECTED,
        decided_by="operator@example.com",
    )
    approve = ApprovalGateDecision(
        status=ApprovalGateStatusEnum.APPROVED,
        decided_by="operator@example.com",
    )

    await service.decide_gate(gate, reject, actor="operator@example.com")
    with pytest.raises(ValueError):
        await service.decide_gate(gate, approve, actor="operator@example.com")

    assert gate.status == ApprovalGateStatusEnum.REJECTED
    assert any(
        isinstance(obj, AuditEvent) and obj.event_type == "approval_gate.decision.conflict"
        for obj in db.added
    )


@pytest.mark.asyncio
async def test_approval_after_completion_is_rejected_with_conflict_audit():
    db = FakeDB()
    service = ApprovalGateService(db)  # type: ignore[arg-type]
    gate = ApprovalGate(
        id=uuid4(),
        campaign_id=uuid4(),
        gate_reason="Completion conflict test",
        requested_by="operator@example.com",
        status=ApprovalGateStatusEnum.PENDING,
    )
    approve = ApprovalGateDecision(
        status=ApprovalGateStatusEnum.APPROVED,
        decided_by="operator@example.com",
    )
    reject = ApprovalGateDecision(
        status=ApprovalGateStatusEnum.REJECTED,
        decided_by="operator@example.com",
    )

    await service.decide_gate(gate, approve, actor="operator@example.com")
    with pytest.raises(ValueError):
        await service.decide_gate(gate, reject, actor="operator@example.com")

    assert gate.status == ApprovalGateStatusEnum.APPROVED
    assert any(
        isinstance(obj, AuditEvent) and obj.event_type == "approval_gate.decision.conflict"
        for obj in db.added
    )


@pytest.mark.asyncio
async def test_export_endpoint_returns_422_for_not_ready_payload_without_state_corruption(
    monkeypatch: pytest.MonkeyPatch,
):
    finding_id = uuid4()
    draft_id = uuid4()
    not_ready = SubmissionExportResult(
        provider="hackerone",
        finding_id=finding_id,
        submission_draft_id=draft_id,
        ready=False,
        state="not_ready",
        missing_fields=["finding.status:HIL_APPROVED", "finding.evidence"],
        warnings=["no_artifacts_linked"],
        payload={"provider": "hackerone", "title": "Incomplete"},
        stored=True,
    )
    fake_service = SimpleNamespace(
        export_payload=AsyncMock(return_value=not_ready),
    )
    monkeypatch.setattr(campaigns_router, "SubmissionExportService", lambda _db: fake_service)

    response = await campaigns_router.export_finding_submission_payload(
        finding_id=finding_id,
        provider="hackerone",
        body=None,
        db=FakeDB(),  # type: ignore[arg-type]
    )

    assert response.status_code == 422
    payload = json.loads(response.body.decode("utf-8"))
    assert payload["ready"] is False
    assert payload["state"] == "not_ready"
    assert payload["provider"] == "hackerone"
    assert payload["submission_draft_id"] == str(draft_id)


@pytest.mark.asyncio
async def test_metrics_summary_and_diagnostics_endpoints_shapes(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    service = MetricsService(db)  # type: ignore[arg-type]
    monkeypatch.setattr(
        service,
        "_count_total",
        AsyncMock(side_effect=[1, 2, 3, 4, 5, 6, 7]),
    )
    monkeypatch.setattr(
        service,
        "_count_by_status",
        AsyncMock(
            side_effect=[
                {"RUNNING": 1},
                {"RUNNING": 2},
                {"QUEUED": 3},
                {"PENDING": 4},
                {"COMPLETED": 5},
                {"IN_REVIEW": 6},
                {"NEEDS_REVIEW": 7},
            ]
        ),
    )
    summary = await service.summary_counts()
    assert summary["campaigns"]["total"] == 1
    assert "findings" in summary
    assert "submission_drafts" in summary

    expected = {"campaigns": {"total": 1}, "generated_at": "now"}
    monkeypatch.setattr(MetricsService, "summary_counts", AsyncMock(return_value=expected))
    endpoint_summary = await campaigns_router.diagnostics_summary(db=FakeDB())  # type: ignore[arg-type]
    assert endpoint_summary == expected


@pytest.mark.asyncio
async def test_campaign_and_finding_diagnostics_endpoints_return_expected_structure(
    monkeypatch: pytest.MonkeyPatch,
):
    campaign = CampaignRun(
        id=uuid4(),
        program_id=uuid4(),
        initiated_by="diag@test",
        declared_goal="diag",
        status=CampaignStatusEnum.RUNNING,
    )
    branch = ExecutionBranch(
        id=uuid4(),
        campaign_id=campaign.id,
        branch_key="root",
        status=BranchStatusEnum.RUNNING,
    )
    phase = PhaseJob(
        id=uuid4(),
        campaign_id=campaign.id,
        branch_id=branch.id,
        phase_name="recon_discovery",
        phase_order=10,
        status=PhaseJobStatusEnum.RUNNING,
    )
    tool = ToolExecution(
        id=uuid4(),
        campaign_id=campaign.id,
        branch_id=branch.id,
        phase_job_id=phase.id,
        tool_name="phase::recon_discovery",
        status=ToolExecutionStatusEnum.RUNNING,
    )
    gate = ApprovalGate(
        id=uuid4(),
        campaign_id=campaign.id,
        branch_id=branch.id,
        phase_job_id=phase.id,
        gate_reason="diag",
        requested_by="diag@test",
        status=ApprovalGateStatusEnum.PENDING,
    )
    draft = SubmissionDraft(
        id=uuid4(),
        campaign_id=campaign.id,
        branch_id=branch.id,
        finding_id=uuid4(),
        status="NEEDS_REVIEW",
        details_json={},
    )
    event = AuditEvent(
        id=uuid4(),
        campaign_id=campaign.id,
        event_type="diag.event",
        event_payload_json={},
    )

    fake_service = SimpleNamespace(
        repo=SimpleNamespace(
            get_campaign=AsyncMock(return_value=campaign),
            list_branches=AsyncMock(return_value=[branch]),
            list_phase_jobs=AsyncMock(return_value=[phase]),
        )
    )
    monkeypatch.setattr(campaigns_router, "CampaignStartService", lambda _db: fake_service)

    campaign_db = SequenceDB(
        [
            _Result(rows=[tool]),
            _Result(rows=[gate]),
            _Result(scalar_value=2),
            _Result(scalar_value=3),
            _Result(rows=[draft]),
            _Result(rows=[event]),
        ]
    )
    campaign_diag = await campaigns_router.campaign_diagnostics(campaign.id, db=campaign_db)  # type: ignore[arg-type]
    assert "counts" in campaign_diag
    assert "status_breakdown" in campaign_diag
    assert "recent_audit_events" in campaign_diag

    finding = Finding(
        id=uuid4(),
        program="Example Program",
        asset="api.example.com",
        title="diag finding",
        description="desc",
        severity=SeverityEnum.LOW,
        status=FindingStatusEnum.IN_REVIEW,
        scope_json={},
    )
    evidence = Evidence(
        id=uuid4(),
        finding_id=finding.id,
        kind="raw_output",
        uri="inline://artifact",
        sha256=b"x" * 32,
        meta={},
    )
    observation = Observation(
        id=uuid4(),
        campaign_id=campaign.id,
        finding_id=finding.id,
        category="VALIDATION",
    )
    artifact = Artifact(
        id=uuid4(),
        campaign_id=campaign.id,
        finding_id=finding.id,
        uri="inline://artifact",
    )
    finding_draft = SubmissionDraft(
        id=uuid4(),
        campaign_id=campaign.id,
        finding_id=finding.id,
        status="READY_FOR_REVIEW",
        details_json={},
    )
    finding_event = AuditEvent(
        id=uuid4(),
        finding_id=finding.id,
        event_type="finding.diag",
        event_payload_json={},
    )
    finding_db = SequenceDB(
        [
            _Result(rows=[finding]),
            _Result(rows=[evidence]),
            _Result(rows=[observation]),
            _Result(rows=[artifact]),
            _Result(rows=[finding_draft]),
            _Result(rows=[finding_event]),
        ]
    )
    finding_diag = await campaigns_router.finding_diagnostics(finding.id, db=finding_db)  # type: ignore[arg-type]
    assert "finding" in finding_diag
    assert "counts" in finding_diag
    assert "recent_audit_events" in finding_diag
