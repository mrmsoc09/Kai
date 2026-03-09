from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4
from unittest.mock import AsyncMock

import pytest

from apps.backend.src.core.branch_scheduler import BranchScheduler
from apps.backend.src.core.campaign_service import CampaignStartService
from apps.backend.src.models.campaign import ApprovalGate, AuditEvent, CampaignRun, ExecutionBranch, PhaseJob, ToolExecution
from apps.backend.src.models.enums import (
    ApprovalGateStatusEnum,
    BranchStatusEnum,
    CampaignStatusEnum,
    PhaseJobStatusEnum,
    ToolExecutionStatusEnum,
)
from apps.backend.src.schemas.campaigns import CampaignStartRequest, PhaseSeedSpec


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
        if hasattr(obj, "status") and getattr(obj, "status", None) is None:
            if isinstance(obj, ApprovalGate):
                obj.status = ApprovalGateStatusEnum.PENDING
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def execute(self, *_args, **_kwargs):
        raise AssertionError("Unexpected SQL execution in FakeDB test path")


def _wire_scheduler_with_seed(
    monkeypatch: pytest.MonkeyPatch,
    scheduler: BranchScheduler,
    *,
    campaign: CampaignRun,
    branches: list[ExecutionBranch],
    phase_jobs: list[PhaseJob],
    gates: dict[UUID, ApprovalGate] | None = None,
    active: dict[UUID, ToolExecution] | None = None,
) -> None:
    monkeypatch.setattr(scheduler.campaigns.repo, "get_campaign", AsyncMock(return_value=campaign))
    monkeypatch.setattr(scheduler.campaigns.repo, "list_branches", AsyncMock(return_value=branches))
    monkeypatch.setattr(scheduler.campaigns.repo, "list_phase_jobs", AsyncMock(return_value=phase_jobs))
    monkeypatch.setattr(scheduler, "_latest_phase_gate_map", AsyncMock(return_value=gates or {}))
    monkeypatch.setattr(scheduler, "_active_phase_execution_map", AsyncMock(return_value=active or {}))


@pytest.mark.asyncio
async def test_campaign_start_and_scheduler_seed_and_queue(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    starter = CampaignStartService(db)  # type: ignore[arg-type]
    request = CampaignStartRequest(
        program_name="Example Program",
        initiated_by="operator@example.com",
        declared_goal="Seed campaign and queue first phase",
    )
    seeded = await starter.start_campaign(request)

    assert seeded.campaign.status == CampaignStatusEnum.READY
    assert seeded.root_branch.status == BranchStatusEnum.READY
    assert [job.phase_name for job in seeded.phase_jobs] == [
        "recon_discovery",
        "target_validation",
        "lightweight_analysis",
    ]

    scheduler = BranchScheduler(db)  # type: ignore[arg-type]
    _wire_scheduler_with_seed(
        monkeypatch,
        scheduler,
        campaign=seeded.campaign,
        branches=[seeded.root_branch],
        phase_jobs=seeded.phase_jobs,
    )

    async def fake_dispatch_phase_job(**kwargs):
        phase = kwargs["phase_job"]
        execution = ToolExecution(
            id=uuid4(),
            campaign_id=kwargs["campaign"].id,
            branch_id=kwargs["branch"].id,
            phase_job_id=phase.id,
            tool_name=f"phase::{phase.phase_name}",
            status=ToolExecutionStatusEnum.QUEUED,
            intention_id=kwargs["intention_id"],
        )
        return execution, True

    monkeypatch.setattr(scheduler.dispatcher, "dispatch_phase_job", fake_dispatch_phase_job)

    summary = await scheduler.schedule_campaign(seeded.campaign.id, actor=request.initiated_by)

    assert summary.queued_jobs == 1
    assert summary.dispatched_tool_executions == 1
    assert seeded.phase_jobs[0].status == PhaseJobStatusEnum.QUEUED
    assert seeded.phase_jobs[1].status == PhaseJobStatusEnum.BLOCKED
    assert seeded.root_branch.status == BranchStatusEnum.RUNNING
    assert seeded.campaign.status == CampaignStatusEnum.RUNNING


@pytest.mark.asyncio
async def test_scheduler_creates_approval_gate_for_approval_required_job(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    starter = CampaignStartService(db)  # type: ignore[arg-type]
    request = CampaignStartRequest(
        program_name="Approval Program",
        initiated_by="operator@example.com",
        declared_goal="Approval gate creation check",
        phases=[
            PhaseSeedSpec(
                phase_name="recon_discovery",
                phase_order=10,
                approval_required=True,
                input_payload_json={"dispatch": {"mode": "placeholder"}},
            )
        ],
    )
    seeded = await starter.start_campaign(request)

    scheduler = BranchScheduler(db)  # type: ignore[arg-type]
    _wire_scheduler_with_seed(
        monkeypatch,
        scheduler,
        campaign=seeded.campaign,
        branches=[seeded.root_branch],
        phase_jobs=seeded.phase_jobs,
    )
    monkeypatch.setattr(
        scheduler.dispatcher,
        "dispatch_phase_job",
        AsyncMock(side_effect=AssertionError("Dispatch should not occur before approval")),
    )

    summary = await scheduler.schedule_campaign(seeded.campaign.id, actor=request.initiated_by)

    assert summary.created_approval_gates == 1
    assert summary.waiting_approval_jobs == 1
    assert seeded.phase_jobs[0].status == PhaseJobStatusEnum.WAITING_APPROVAL
    assert seeded.root_branch.status == BranchStatusEnum.WAITING_APPROVAL
    assert seeded.campaign.status == CampaignStatusEnum.BLOCKED
    assert any(isinstance(obj, ApprovalGate) for obj in db.added)


@pytest.mark.asyncio
async def test_scheduler_blocks_only_dependent_branch_paths(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    campaign = CampaignRun(
        id=uuid4(),
        program_id=uuid4(),
        initiated_by="scheduler@test",
        declared_goal="Branch-local blocking",
        status=CampaignStatusEnum.READY,
    )
    branch_a = ExecutionBranch(
        id=uuid4(),
        campaign_id=campaign.id,
        branch_key="branch-a",
        status=BranchStatusEnum.READY,
    )
    branch_b = ExecutionBranch(
        id=uuid4(),
        campaign_id=campaign.id,
        branch_key="branch-b",
        status=BranchStatusEnum.READY,
    )
    phase_a = PhaseJob(
        id=uuid4(),
        campaign_id=campaign.id,
        branch_id=branch_a.id,
        phase_name="recon_discovery",
        phase_order=10,
        approval_required=True,
        input_payload_json={"dispatch": {"mode": "placeholder"}, "seed_intention_id": str(uuid4())},
        status=PhaseJobStatusEnum.CREATED,
    )
    phase_b = PhaseJob(
        id=uuid4(),
        campaign_id=campaign.id,
        branch_id=branch_b.id,
        phase_name="recon_discovery",
        phase_order=10,
        approval_required=False,
        input_payload_json={"dispatch": {"mode": "placeholder"}, "seed_intention_id": str(uuid4())},
        status=PhaseJobStatusEnum.CREATED,
    )

    scheduler = BranchScheduler(db)  # type: ignore[arg-type]
    _wire_scheduler_with_seed(
        monkeypatch,
        scheduler,
        campaign=campaign,
        branches=[branch_a, branch_b],
        phase_jobs=[phase_a, phase_b],
    )

    async def fake_dispatch_phase_job(**kwargs):
        execution = ToolExecution(
            id=uuid4(),
            campaign_id=kwargs["campaign"].id,
            branch_id=kwargs["branch"].id,
            phase_job_id=kwargs["phase_job"].id,
            tool_name=f"phase::{kwargs['phase_job'].phase_name}",
            status=ToolExecutionStatusEnum.QUEUED,
            intention_id=kwargs["intention_id"],
        )
        return execution, True

    monkeypatch.setattr(scheduler.dispatcher, "dispatch_phase_job", fake_dispatch_phase_job)

    summary = await scheduler.schedule_campaign(campaign.id, actor="scheduler@test")

    assert summary.waiting_approval_jobs == 1
    assert summary.queued_jobs == 1
    assert phase_a.status == PhaseJobStatusEnum.WAITING_APPROVAL
    assert phase_b.status == PhaseJobStatusEnum.QUEUED
    assert branch_a.status == BranchStatusEnum.WAITING_APPROVAL
    assert branch_b.status == BranchStatusEnum.RUNNING
    assert campaign.status == CampaignStatusEnum.RUNNING


@pytest.mark.asyncio
async def test_scheduler_rerun_safe_does_not_duplicate_dispatch(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    campaign = CampaignRun(
        id=uuid4(),
        program_id=uuid4(),
        initiated_by="scheduler@test",
        declared_goal="Rerun idempotency",
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
        approval_required=False,
        status=PhaseJobStatusEnum.QUEUED,
        input_payload_json={"dispatch": {"mode": "placeholder"}},
    )
    active_execution = ToolExecution(
        id=uuid4(),
        campaign_id=campaign.id,
        branch_id=branch.id,
        phase_job_id=phase.id,
        tool_name="phase::recon_discovery",
        status=ToolExecutionStatusEnum.QUEUED,
    )

    scheduler = BranchScheduler(db)  # type: ignore[arg-type]
    _wire_scheduler_with_seed(
        monkeypatch,
        scheduler,
        campaign=campaign,
        branches=[branch],
        phase_jobs=[phase],
        active={phase.id: active_execution},
    )
    monkeypatch.setattr(
        scheduler.dispatcher,
        "dispatch_phase_job",
        AsyncMock(side_effect=AssertionError("Should not re-dispatch active queued phase")),
    )

    summary = await scheduler.schedule_campaign(campaign.id, actor="scheduler@test")

    assert summary.queued_jobs == 1
    assert summary.dispatched_tool_executions == 0
    assert phase.status == PhaseJobStatusEnum.QUEUED


@pytest.mark.asyncio
async def test_start_and_dispatch_preserve_intention_and_audit_linkage(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    starter = CampaignStartService(db)  # type: ignore[arg-type]
    request = CampaignStartRequest(
        program_name="Intent Program",
        initiated_by="operator@example.com",
        declared_goal="Ensure intention and audit linkage",
    )
    seeded = await starter.start_campaign(request)
    assert seeded.intention is not None

    scheduler = BranchScheduler(db)  # type: ignore[arg-type]
    _wire_scheduler_with_seed(
        monkeypatch,
        scheduler,
        campaign=seeded.campaign,
        branches=[seeded.root_branch],
        phase_jobs=seeded.phase_jobs,
    )

    captured_intention_ids: list[UUID | None] = []

    async def fake_dispatch_phase_job(**kwargs):
        captured_intention_ids.append(kwargs.get("intention_id"))
        return (
            ToolExecution(
                id=uuid4(),
                campaign_id=kwargs["campaign"].id,
                branch_id=kwargs["branch"].id,
                phase_job_id=kwargs["phase_job"].id,
                tool_name=f"phase::{kwargs['phase_job'].phase_name}",
                status=ToolExecutionStatusEnum.QUEUED,
                intention_id=kwargs.get("intention_id"),
            ),
            True,
        )

    monkeypatch.setattr(scheduler.dispatcher, "dispatch_phase_job", fake_dispatch_phase_job)
    await scheduler.schedule_campaign(seeded.campaign.id, actor=request.initiated_by)

    assert captured_intention_ids
    assert captured_intention_ids[0] == seeded.intention.id
    audit_events = [obj for obj in db.added if isinstance(obj, AuditEvent)]
    assert any(
        event.event_type == "campaign.created" and event.intention_id == seeded.intention.id
        for event in audit_events
    )
    assert any(
        event.event_type == "phase_job.status.changed" and event.intention_id == seeded.intention.id
        for event in audit_events
    )
