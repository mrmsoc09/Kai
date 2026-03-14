from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from apps.backend.src.core.approval_gate_service import ApprovalGateService
from apps.backend.src.core.branch_scheduler import BranchScheduler, SchedulerResult
from apps.backend.src.core.execution_result_service import ExecutionResultIngestionService
from apps.backend.src.core.finding_correlation_service import (
    CorrelationResult,
    FindingCorrelationService,
)
from apps.backend.src.models.campaign import (
    ApprovalGate,
    Artifact,
    AuditEvent,
    CampaignRun,
    ExecutionBranch,
    Observation,
    PhaseJob,
    ToolExecution,
)
from apps.backend.src.models.enums import (
    ApprovalGateStatusEnum,
    BranchStatusEnum,
    CampaignStatusEnum,
    PhaseJobStatusEnum,
    ToolExecutionStatusEnum,
)
from apps.backend.src.routers.campaigns import decide_campaign_approval_gate
from apps.backend.src.schemas.campaigns import (
    CampaignApprovalDecisionRequest,
    ExecutionResultIngestRequest,
)


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
        if isinstance(obj, ApprovalGate) and obj.status is None:
            obj.status = ApprovalGateStatusEnum.PENDING
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def execute(self, *_args, **_kwargs):
        raise AssertionError("Unexpected SQL execution in FakeDB test path")

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def _seed_execution_graph(
    *,
    adapter_name: str = "placeholder.dispatch",
    phase_status: PhaseJobStatusEnum = PhaseJobStatusEnum.QUEUED,
    tool_status: ToolExecutionStatusEnum = ToolExecutionStatusEnum.QUEUED,
) -> tuple[CampaignRun, ExecutionBranch, PhaseJob, ToolExecution, UUID]:
    intention_id = uuid4()
    campaign = CampaignRun(
        id=uuid4(),
        program_id=uuid4(),
        initiated_by="worker@test",
        declared_goal="Ingestion test",
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
        status=phase_status,
        input_payload_json={"seed_intention_id": str(intention_id)},
    )
    execution = ToolExecution(
        id=uuid4(),
        campaign_id=campaign.id,
        branch_id=branch.id,
        phase_job_id=phase.id,
        tool_name="phase::recon_discovery",
        adapter_name=adapter_name,
        status=tool_status,
        worker_task_id="task-1",
    )
    return campaign, branch, phase, execution, intention_id


@pytest.mark.asyncio
async def test_ingest_successful_placeholder_completion_updates_state_and_records_artifacts(
    monkeypatch: pytest.MonkeyPatch,
):
    db = FakeDB()
    campaign, branch, phase, execution, intention_id = _seed_execution_graph()
    svc = ExecutionResultIngestionService(db)  # type: ignore[arg-type]

    monkeypatch.setattr(svc, "_resolve_execution", AsyncMock(return_value=execution))
    monkeypatch.setattr(svc.campaigns.repo, "get_campaign", AsyncMock(return_value=campaign))
    monkeypatch.setattr(svc.campaigns.repo, "get_branch", AsyncMock(return_value=branch))
    monkeypatch.setattr(svc.campaigns.repo, "get_phase_job", AsyncMock(return_value=phase))
    monkeypatch.setattr(
        FindingCorrelationService,
        "process_observation",
        AsyncMock(
            return_value=CorrelationResult(
                observation_id=uuid4(),
                action="CONTEXT_ONLY",
            )
        ),
    )
    scheduler_summary = AsyncMock(
        return_value=SchedulerResult(
            campaign_id=campaign.id,
            considered_jobs=3,
            queued_jobs=1,
            blocked_jobs=0,
            waiting_approval_jobs=0,
            created_approval_gates=0,
            dispatched_tool_executions=0,
        )
    )
    monkeypatch.setattr(svc, "_scheduler_summary", scheduler_summary)

    response = await svc.ingest_result(
        ExecutionResultIngestRequest(
            worker_task_id=execution.worker_task_id,
            tool_status=ToolExecutionStatusEnum.COMPLETED,
            result_payload_json={"placeholder": True, "assets": ["example.com"]},
            stdout_ref="inline://stdout/test",
            stderr_ref="inline://stderr/test",
        ),
        actor="worker.test",
    )

    assert execution.status == ToolExecutionStatusEnum.COMPLETED
    assert phase.status == PhaseJobStatusEnum.COMPLETED
    assert response.scheduler is not None
    assert response.artifact_ids
    assert response.observation_ids
    assert scheduler_summary.await_count == 1
    audit_events = [obj for obj in db.added if isinstance(obj, AuditEvent)]
    assert any(event.event_type == "phase_job.result.ingested" for event in audit_events)
    assert any(event.intention_id == intention_id for event in audit_events)


@pytest.mark.asyncio
async def test_ingest_failed_execution_updates_phase_failure_and_error(
    monkeypatch: pytest.MonkeyPatch,
):
    db = FakeDB()
    campaign, branch, phase, execution, _ = _seed_execution_graph(
        adapter_name="celery.run_tool_task"
    )
    svc = ExecutionResultIngestionService(db)  # type: ignore[arg-type]

    monkeypatch.setattr(svc, "_resolve_execution", AsyncMock(return_value=execution))
    monkeypatch.setattr(svc.campaigns.repo, "get_campaign", AsyncMock(return_value=campaign))
    monkeypatch.setattr(svc.campaigns.repo, "get_branch", AsyncMock(return_value=branch))
    monkeypatch.setattr(svc.campaigns.repo, "get_phase_job", AsyncMock(return_value=phase))
    monkeypatch.setattr(
        FindingCorrelationService,
        "process_observation",
        AsyncMock(
            return_value=CorrelationResult(
                observation_id=uuid4(),
                action="CONTEXT_ONLY",
            )
        ),
    )
    monkeypatch.setattr(
        svc,
        "_scheduler_summary",
        AsyncMock(
            return_value=SchedulerResult(
                campaign_id=campaign.id,
                considered_jobs=3,
                queued_jobs=0,
                blocked_jobs=1,
                waiting_approval_jobs=0,
                created_approval_gates=0,
                dispatched_tool_executions=0,
            )
        ),
    )

    response = await svc.ingest_result(
        ExecutionResultIngestRequest(
            execution_id=execution.id,
            tool_status=ToolExecutionStatusEnum.FAILED,
            result_payload_json={"status": "failed"},
            error_message="Tool adapter failed",
        ),
        actor="worker.test",
    )

    assert execution.status == ToolExecutionStatusEnum.FAILED
    assert phase.status == PhaseJobStatusEnum.FAILED
    assert phase.error_message == "Tool adapter failed"
    assert response.phase_status == PhaseJobStatusEnum.FAILED
    observations = [obj for obj in db.added if isinstance(obj, Observation)]
    assert any(ob.category == "EXECUTION_FAILURE" for ob in observations)


@pytest.mark.asyncio
async def test_waiting_approval_ingestion_creates_gate_and_waiting_states(
    monkeypatch: pytest.MonkeyPatch,
):
    db = FakeDB()
    campaign, branch, phase, execution, _ = _seed_execution_graph(
        phase_status=PhaseJobStatusEnum.RUNNING,
        tool_status=ToolExecutionStatusEnum.RUNNING,
    )
    svc = ExecutionResultIngestionService(db)  # type: ignore[arg-type]

    monkeypatch.setattr(svc, "_resolve_execution", AsyncMock(return_value=execution))
    monkeypatch.setattr(svc.campaigns.repo, "get_campaign", AsyncMock(return_value=campaign))
    monkeypatch.setattr(svc.campaigns.repo, "get_branch", AsyncMock(return_value=branch))
    monkeypatch.setattr(svc.campaigns.repo, "get_phase_job", AsyncMock(return_value=phase))
    monkeypatch.setattr(
        FindingCorrelationService,
        "process_observation",
        AsyncMock(
            return_value=CorrelationResult(
                observation_id=uuid4(),
                action="CONTEXT_ONLY",
            )
        ),
    )
    monkeypatch.setattr(svc, "_latest_phase_gate", AsyncMock(return_value=None))

    response = await svc.ingest_result(
        ExecutionResultIngestRequest(
            worker_task_id=execution.worker_task_id,
            tool_status=ToolExecutionStatusEnum.WAITING_APPROVAL,
            approval_reason="Escalate risky probe",
            trigger_scheduler=False,
        ),
        actor="worker.test",
    )

    assert execution.status == ToolExecutionStatusEnum.WAITING_APPROVAL
    assert phase.status == PhaseJobStatusEnum.WAITING_APPROVAL
    assert branch.status == BranchStatusEnum.WAITING_APPROVAL
    assert response.scheduler is None
    gates = [obj for obj in db.added if isinstance(obj, ApprovalGate)]
    assert gates
    assert gates[0].status == ApprovalGateStatusEnum.PENDING


def _wire_scheduler(
    monkeypatch: pytest.MonkeyPatch,
    scheduler: BranchScheduler,
    *,
    campaign: CampaignRun,
    branches: list[ExecutionBranch],
    phase_jobs: list[PhaseJob],
) -> None:
    monkeypatch.setattr(scheduler.campaigns.repo, "get_campaign", AsyncMock(return_value=campaign))
    monkeypatch.setattr(scheduler.campaigns.repo, "list_branches", AsyncMock(return_value=branches))
    monkeypatch.setattr(
        scheduler.campaigns.repo, "list_phase_jobs", AsyncMock(return_value=phase_jobs)
    )
    monkeypatch.setattr(scheduler, "_latest_phase_gate_map", AsyncMock(return_value={}))
    monkeypatch.setattr(scheduler, "_active_phase_execution_map", AsyncMock(return_value={}))
    monkeypatch.setattr(
        scheduler.dispatcher,
        "dispatch_phase_job",
        AsyncMock(
            side_effect=AssertionError("No dispatch expected for terminal-state reconciliation")
        ),
    )


@pytest.mark.asyncio
async def test_scheduler_marks_branch_and_campaign_completed_when_all_phases_complete(
    monkeypatch: pytest.MonkeyPatch,
):
    db = FakeDB()
    campaign = CampaignRun(
        id=uuid4(),
        program_id=uuid4(),
        initiated_by="scheduler@test",
        declared_goal="terminal completion",
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
        status=PhaseJobStatusEnum.COMPLETED,
    )
    scheduler = BranchScheduler(db)  # type: ignore[arg-type]
    _wire_scheduler(
        monkeypatch,
        scheduler,
        campaign=campaign,
        branches=[branch],
        phase_jobs=[phase],
    )

    await scheduler.schedule_campaign(campaign.id, actor="scheduler@test")
    assert branch.status == BranchStatusEnum.COMPLETED
    assert campaign.status == CampaignStatusEnum.COMPLETED


@pytest.mark.asyncio
async def test_scheduler_marks_branch_and_campaign_failed_when_all_terminal_include_failure(
    monkeypatch: pytest.MonkeyPatch,
):
    db = FakeDB()
    campaign = CampaignRun(
        id=uuid4(),
        program_id=uuid4(),
        initiated_by="scheduler@test",
        declared_goal="terminal failure",
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
        status=PhaseJobStatusEnum.FAILED,
    )
    scheduler = BranchScheduler(db)  # type: ignore[arg-type]
    _wire_scheduler(
        monkeypatch,
        scheduler,
        campaign=campaign,
        branches=[branch],
        phase_jobs=[phase],
    )

    await scheduler.schedule_campaign(campaign.id, actor="scheduler@test")
    assert branch.status == BranchStatusEnum.FAILED
    assert campaign.status == CampaignStatusEnum.FAILED


@pytest.mark.asyncio
async def test_campaign_approval_decision_triggers_scheduler_rerun(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    gate = ApprovalGate(
        id=uuid4(),
        campaign_id=uuid4(),
        status=ApprovalGateStatusEnum.PENDING,
        gate_reason="Manual review required",
        requested_by="scheduler@test",
    )
    decided_at = datetime.now(timezone.utc)
    schedule_mock = AsyncMock(
        return_value=SchedulerResult(
            campaign_id=gate.campaign_id,
            considered_jobs=2,
            queued_jobs=1,
            blocked_jobs=0,
            waiting_approval_jobs=0,
            created_approval_gates=0,
            dispatched_tool_executions=1,
        )
    )

    monkeypatch.setattr(ApprovalGateService, "get_gate", AsyncMock(return_value=gate))

    async def _decide(_self, gate_obj, decision, **_kwargs):
        gate_obj.status = decision.status
        gate_obj.decided_by = decision.decided_by
        gate_obj.decided_at = decided_at
        return gate_obj

    monkeypatch.setattr(ApprovalGateService, "decide_gate", _decide)
    monkeypatch.setattr(BranchScheduler, "schedule_campaign", schedule_mock)

    response = await decide_campaign_approval_gate(
        gate.id,
        CampaignApprovalDecisionRequest(
            status=ApprovalGateStatusEnum.APPROVED,
            decided_by="operator@test",
            operator_notes="Looks safe",
        ),
        db=db,  # type: ignore[arg-type]
    )

    assert response.status == ApprovalGateStatusEnum.APPROVED
    assert response.decided_by == "operator@test"
    assert response.scheduler is not None
    assert schedule_mock.await_count == 1
