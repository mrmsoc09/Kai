from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.campaign import ApprovalGate, CampaignRun, ExecutionBranch, PhaseJob, ToolExecution
from ..models.enums import (
    ApprovalGateStatusEnum,
    BranchStatusEnum,
    CampaignStatusEnum,
    PhaseJobStatusEnum,
    ToolExecutionStatusEnum,
)
from ..schemas.campaigns import ApprovalGateCreate, ToolExecutionCreate
from ..worker.campaign_tasks import run_phase_job_placeholder_task
from ..worker.celery_app import run_tool_task
from .approval_gate_service import ApprovalGateService
from .audit_events import record_transition_event
from .campaign_service import CampaignService
from .tool_execution_service import ToolExecutionService

ACTIVE_TOOL_EXECUTION_STATUSES = {
    ToolExecutionStatusEnum.CREATED,
    ToolExecutionStatusEnum.QUEUED,
    ToolExecutionStatusEnum.RUNNING,
    ToolExecutionStatusEnum.WAITING_APPROVAL,
}
TERMINAL_PHASE_STATUSES = {
    PhaseJobStatusEnum.COMPLETED,
    PhaseJobStatusEnum.FAILED,
    PhaseJobStatusEnum.SKIPPED,
    PhaseJobStatusEnum.CANCELED,
}
TERMINAL_BRANCH_STATUSES = {
    BranchStatusEnum.COMPLETED,
    BranchStatusEnum.FAILED,
    BranchStatusEnum.CANCELED,
}
BRANCH_SUCCESS_PHASE_STATUSES = {
    PhaseJobStatusEnum.COMPLETED,
    PhaseJobStatusEnum.SKIPPED,
}
BRANCH_FAILURE_PHASE_STATUSES = {
    PhaseJobStatusEnum.FAILED,
    PhaseJobStatusEnum.CANCELED,
}
TERMINAL_CAMPAIGN_STATUSES = {
    CampaignStatusEnum.COMPLETED,
    CampaignStatusEnum.FAILED,
    CampaignStatusEnum.CANCELED,
}


def _maybe_uuid(raw: Any) -> UUID | None:
    if raw is None:
        return None
    if isinstance(raw, UUID):
        return raw
    if not isinstance(raw, str):
        return None
    try:
        return UUID(raw)
    except ValueError:
        return None


def _phase_intention_id(phase_job: PhaseJob, branch: ExecutionBranch | None) -> UUID | None:
    payload = phase_job.input_payload_json if isinstance(phase_job.input_payload_json, dict) else {}
    branch_payload = (
        branch.branch_config_json if branch and isinstance(branch.branch_config_json, dict) else {}
    )
    return _maybe_uuid(
        payload.get("intention_id")
        or payload.get("seed_intention_id")
        or branch_payload.get("intention_id")
        or branch_payload.get("seed_intention_id")
    )


@dataclass
class SchedulerResult:
    campaign_id: UUID
    considered_jobs: int = 0
    queued_jobs: int = 0
    blocked_jobs: int = 0
    waiting_approval_jobs: int = 0
    created_approval_gates: int = 0
    dispatched_tool_executions: int = 0


class PhaseDispatchAdapter:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.tool_exec = ToolExecutionService(db)

    async def _active_execution(self, phase_job_id: UUID) -> ToolExecution | None:
        result = await self.db.execute(
            select(ToolExecution)
            .where(
                ToolExecution.phase_job_id == phase_job_id,
                ToolExecution.status.in_(list(ACTIVE_TOOL_EXECUTION_STATUSES)),
            )
            .order_by(ToolExecution.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def dispatch_phase_job(
        self,
        *,
        campaign: CampaignRun,
        branch: ExecutionBranch,
        phase_job: PhaseJob,
        actor: str,
        intention_id: UUID | None,
    ) -> tuple[ToolExecution, bool]:
        existing = await self._active_execution(phase_job.id)
        if existing is not None:
            return existing, False

        payload = (
            phase_job.input_payload_json if isinstance(phase_job.input_payload_json, dict) else {}
        )
        dispatch = payload.get("dispatch") if isinstance(payload.get("dispatch"), dict) else {}

        tool_id = dispatch.get("tool_id")
        queue = str(dispatch.get("queue") or phase_job.queue_name or "campaigns")
        raw_delay = dispatch.get("dispatch_delay_seconds")
        try:
            dispatch_delay_seconds = max(0, int(raw_delay)) if raw_delay is not None else 1
        except (TypeError, ValueError):
            dispatch_delay_seconds = 1
        task_id: str
        tool_name: str
        adapter_name: str
        tool_input: dict[str, Any]

        if isinstance(tool_id, str) and tool_id.strip():
            tool_name = tool_id.strip()
            adapter_name = "celery.run_tool_task"
            tool_input = dispatch.get("params") if isinstance(dispatch.get("params"), dict) else {}
            tool_input = dict(tool_input)
            tool_input.setdefault("run_id", str(campaign.id))
            tool_input.setdefault("campaign_id", str(campaign.id))
            tool_input.setdefault("branch_id", str(branch.id))
            tool_input.setdefault("phase_job_id", str(phase_job.id))
            if intention_id is not None:
                tool_input.setdefault("intention_id", str(intention_id))
            if payload.get("target"):
                tool_input.setdefault("target", payload.get("target"))
            async_result = run_tool_task.apply_async(
                (tool_name, tool_input),
                queue=queue,
                countdown=dispatch_delay_seconds,
                kwargs={
                    "user_id": campaign.initiated_by or "",
                    "program_id": str(campaign.program_id),
                    "workflow_id": str(campaign.id),
                },
            )
            task_id = async_result.id
        else:
            tool_name = f"phase::{phase_job.phase_name}"
            adapter_name = "placeholder.dispatch"
            tool_input = payload
            async_result = run_phase_job_placeholder_task.apply_async(
                kwargs={
                    "campaign_id": str(campaign.id),
                    "branch_id": str(branch.id),
                    "phase_job_id": str(phase_job.id),
                    "phase_name": phase_job.phase_name,
                    "payload": payload,
                },
                queue=queue,
                countdown=dispatch_delay_seconds,
            )
            task_id = async_result.id

        execution = await self.tool_exec.create_execution(
            ToolExecutionCreate(
                campaign_id=campaign.id,
                branch_id=branch.id,
                phase_job_id=phase_job.id,
                intention_id=intention_id,
                tool_name=tool_name,
                adapter_name=adapter_name,
                input_target=str(payload.get("target") or ""),
                input_payload_json=tool_input,
                max_retries=phase_job.max_retries,
            ),
            actor=actor,
        )
        await self.tool_exec.transition_execution(
            execution,
            ToolExecutionStatusEnum.QUEUED,
            worker_task_id=task_id,
            actor=actor,
            intention_id=intention_id,
            event_payload={"phase_name": phase_job.phase_name, "queue": queue},
        )
        phase_job.worker_task_id = task_id
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="phase_job.dispatched",
            actor=actor,
            message=f"Phase job dispatched to worker queue {queue}",
            campaign_id=campaign.id,
            branch_id=branch.id,
            phase_job_id=phase_job.id,
            tool_execution_id=execution.id,
            intention_id=intention_id,
            payload={"queue": queue, "task_id": task_id, "tool_name": tool_name},
        )
        return execution, True


class BranchScheduler:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.campaigns = CampaignService(db)
        self.approvals = ApprovalGateService(db)
        self.dispatcher = PhaseDispatchAdapter(db)

    async def _latest_phase_gate_map(self, campaign_id: UUID) -> dict[UUID, ApprovalGate]:
        result = await self.db.execute(
            select(ApprovalGate)
            .where(ApprovalGate.campaign_id == campaign_id, ApprovalGate.phase_job_id.is_not(None))
            .order_by(ApprovalGate.created_at.desc())
        )
        gates: dict[UUID, ApprovalGate] = {}
        for gate in result.scalars().all():
            if gate.phase_job_id is not None and gate.phase_job_id not in gates:
                gates[gate.phase_job_id] = gate
        return gates

    async def _active_phase_execution_map(self, campaign_id: UUID) -> dict[UUID, ToolExecution]:
        result = await self.db.execute(
            select(ToolExecution)
            .where(
                ToolExecution.campaign_id == campaign_id,
                ToolExecution.phase_job_id.is_not(None),
                ToolExecution.status.in_(list(ACTIVE_TOOL_EXECUTION_STATUSES)),
            )
            .order_by(ToolExecution.created_at.desc())
        )
        executions: dict[UUID, ToolExecution] = {}
        for execution in result.scalars().all():
            if execution.phase_job_id is not None and execution.phase_job_id not in executions:
                executions[execution.phase_job_id] = execution
        return executions

    async def schedule_campaign(
        self,
        campaign_id: UUID,
        *,
        actor: str = "system.scheduler",
    ) -> SchedulerResult:
        campaign = await self.campaigns.repo.get_campaign(campaign_id)
        if campaign is None:
            raise ValueError(f"Campaign not found: {campaign_id}")

        summary = SchedulerResult(campaign_id=campaign.id)
        if campaign.status in TERMINAL_CAMPAIGN_STATUSES:
            return summary

        if campaign.status == CampaignStatusEnum.CREATED:
            await self.campaigns.transition_campaign_status(
                campaign,
                CampaignStatusEnum.READY,
                actor=actor,
            )

        branches = await self.campaigns.repo.list_branches(campaign.id)
        phase_jobs = await self.campaigns.repo.list_phase_jobs(campaign.id)
        branch_by_id = {branch.id: branch for branch in branches}
        phase_by_id = {phase.id: phase for phase in phase_jobs}
        gate_by_phase = await self._latest_phase_gate_map(campaign.id)
        active_exec_by_phase = await self._active_phase_execution_map(campaign.id)

        for branch in branches:
            if branch.status in TERMINAL_BRANCH_STATUSES:
                continue
            if branch.depends_on_branch_id:
                depends_on = branch_by_id.get(branch.depends_on_branch_id)
                if depends_on is None or depends_on.status != BranchStatusEnum.COMPLETED:
                    if branch.status != BranchStatusEnum.BLOCKED:
                        await self.campaigns.transition_branch_status(
                            branch,
                            BranchStatusEnum.BLOCKED,
                            reason="Waiting for upstream branch dependency",
                            actor=actor,
                        )
                    continue
            if branch.status == BranchStatusEnum.PENDING:
                await self.campaigns.transition_branch_status(
                    branch,
                    BranchStatusEnum.READY,
                    actor=actor,
                )

        for phase_job in phase_jobs:
            summary.considered_jobs += 1
            if phase_job.status in TERMINAL_PHASE_STATUSES:
                continue
            branch = branch_by_id.get(phase_job.branch_id)
            if branch is None or branch.status in TERMINAL_BRANCH_STATUSES:
                continue

            intention_id = _phase_intention_id(phase_job, branch)

            # Re-entry guard: avoid duplicate dispatch when phase is already active.
            if phase_job.status == PhaseJobStatusEnum.RUNNING:
                summary.queued_jobs += 1
                continue
            if phase_job.status == PhaseJobStatusEnum.QUEUED:
                if phase_job.id in active_exec_by_phase:
                    summary.queued_jobs += 1
                    continue
                if phase_job.worker_task_id:
                    await record_transition_event(
                        self.db,
                        event_type="phase_job.dispatch.skipped",
                        actor=actor,
                        message=(
                            "Phase is queued with worker_task_id but no active tool execution; "
                            "scheduler skipped duplicate dispatch"
                        ),
                        campaign_id=campaign.id,
                        branch_id=branch.id,
                        phase_job_id=phase_job.id,
                        intention_id=intention_id,
                        action="schedule_phase",
                        outcome="skipped_stale_queued",
                        dedupe_key=f"{phase_job.id}:queued-stale:{phase_job.worker_task_id}",
                        payload={
                            "phase_status": phase_job.status.value,
                            "worker_task_id": phase_job.worker_task_id,
                        },
                    )
                    summary.queued_jobs += 1
                    continue

            if branch.depends_on_branch_id:
                dep_branch = branch_by_id.get(branch.depends_on_branch_id)
                if dep_branch is None or dep_branch.status != BranchStatusEnum.COMPLETED:
                    if phase_job.status != PhaseJobStatusEnum.BLOCKED:
                        await self.campaigns.transition_phase_status(
                            phase_job,
                            PhaseJobStatusEnum.BLOCKED,
                            reason="Waiting for upstream branch dependency",
                            actor=actor,
                            intention_id=intention_id,
                        )
                    summary.blocked_jobs += 1
                    continue

            if phase_job.depends_on_job_id:
                dependency = phase_by_id.get(phase_job.depends_on_job_id)
                if dependency is None or dependency.status != PhaseJobStatusEnum.COMPLETED:
                    reason = "Waiting for upstream phase dependency"
                    if dependency is not None and dependency.status in TERMINAL_PHASE_STATUSES:
                        reason = (
                            f"Blocked by upstream phase {dependency.phase_name} "
                            f"ending in {dependency.status.value}"
                        )
                    if phase_job.status != PhaseJobStatusEnum.BLOCKED:
                        await self.campaigns.transition_phase_status(
                            phase_job,
                            PhaseJobStatusEnum.BLOCKED,
                            reason=reason,
                            actor=actor,
                            intention_id=intention_id,
                        )
                    summary.blocked_jobs += 1
                    continue

            approval_required = bool(
                phase_job.approval_required
                or branch.approval_required
                or campaign.approval_required
            )
            if approval_required:
                gate = gate_by_phase.get(phase_job.id)
                if gate is None:
                    gate = await self.approvals.create_gate(
                        ApprovalGateCreate(
                            campaign_id=campaign.id,
                            branch_id=branch.id,
                            phase_job_id=phase_job.id,
                            intention_id=intention_id,
                            gate_reason=(
                                f"Approval required before executing phase "
                                f"'{phase_job.phase_name}'"
                            ),
                            requested_by=actor,
                            policy_basis=(
                                phase_job.policy_class.value
                                if phase_job.policy_class
                                else campaign.policy_basis
                            ),
                        ),
                        actor=actor,
                    )
                    gate_by_phase[phase_job.id] = gate
                    summary.created_approval_gates += 1

                if gate.status in {
                    ApprovalGateStatusEnum.PENDING,
                    ApprovalGateStatusEnum.DEFERRED,
                }:
                    await self.campaigns.transition_phase_status(
                        phase_job,
                        PhaseJobStatusEnum.WAITING_APPROVAL,
                        reason=f"Approval gate {gate.id} is {gate.status.value}",
                        actor=actor,
                        intention_id=intention_id,
                    )
                    await self.campaigns.transition_branch_status(
                        branch,
                        BranchStatusEnum.WAITING_APPROVAL,
                        reason=f"Waiting on approval gate {gate.id}",
                        actor=actor,
                        intention_id=intention_id,
                    )
                    summary.waiting_approval_jobs += 1
                    continue
                if gate.status in {
                    ApprovalGateStatusEnum.REJECTED,
                    ApprovalGateStatusEnum.EXPIRED,
                    ApprovalGateStatusEnum.CANCELED,
                }:
                    await self.campaigns.transition_phase_status(
                        phase_job,
                        PhaseJobStatusEnum.BLOCKED,
                        reason=f"Approval gate {gate.id} is {gate.status.value}",
                        actor=actor,
                        intention_id=intention_id,
                    )
                    await self.campaigns.transition_branch_status(
                        branch,
                        BranchStatusEnum.BLOCKED,
                        reason=f"Approval gate {gate.id} is {gate.status.value}",
                        actor=actor,
                        intention_id=intention_id,
                    )
                    summary.blocked_jobs += 1
                    continue

            if branch.status in {
                BranchStatusEnum.READY,
                BranchStatusEnum.PENDING,
                BranchStatusEnum.WAITING_APPROVAL,
                BranchStatusEnum.BLOCKED,
            }:
                await self.campaigns.transition_branch_status(
                    branch,
                    BranchStatusEnum.RUNNING,
                    actor=actor,
                    intention_id=intention_id,
                )

            if phase_job.status != PhaseJobStatusEnum.QUEUED:
                await self.campaigns.transition_phase_status(
                    phase_job,
                    PhaseJobStatusEnum.QUEUED,
                    actor=actor,
                    intention_id=intention_id,
                )

            if phase_job.id in active_exec_by_phase:
                summary.queued_jobs += 1
                continue

            execution, created = await self.dispatcher.dispatch_phase_job(
                campaign=campaign,
                branch=branch,
                phase_job=phase_job,
                actor=actor,
                intention_id=intention_id,
            )
            active_exec_by_phase[phase_job.id] = execution
            summary.queued_jobs += 1
            if created:
                summary.dispatched_tool_executions += 1

        await self._reconcile_branch_states(
            campaign=campaign,
            branches=branches,
            phase_jobs=phase_jobs,
            actor=actor,
        )
        await self._reconcile_campaign_state(
            campaign=campaign,
            branches=branches,
            phase_jobs=phase_jobs,
            actor=actor,
        )

        return summary

    async def _reconcile_branch_states(
        self,
        *,
        campaign: CampaignRun,
        branches: list[ExecutionBranch],
        phase_jobs: list[PhaseJob],
        actor: str,
    ) -> None:
        phases_by_branch: dict[UUID, list[PhaseJob]] = {}
        for phase in phase_jobs:
            phases_by_branch.setdefault(phase.branch_id, []).append(phase)

        for branch in branches:
            if branch.status in TERMINAL_BRANCH_STATUSES:
                continue
            branch_phases = phases_by_branch.get(branch.id, [])
            if not branch_phases:
                continue

            intention_id = _phase_intention_id(branch_phases[0], branch)
            statuses = {phase.status for phase in branch_phases}

            if statuses and statuses.issubset(BRANCH_SUCCESS_PHASE_STATUSES):
                await self.campaigns.transition_branch_status(
                    branch,
                    BranchStatusEnum.COMPLETED,
                    actor=actor,
                    intention_id=intention_id,
                )
                continue

            if statuses.intersection(BRANCH_FAILURE_PHASE_STATUSES):
                failed_phase = next(
                    (
                        phase
                        for phase in branch_phases
                        if phase.status in BRANCH_FAILURE_PHASE_STATUSES
                    ),
                    None,
                )
                await self.campaigns.transition_branch_status(
                    branch,
                    BranchStatusEnum.FAILED,
                    reason=(
                        f"Phase {failed_phase.phase_name} ended as {failed_phase.status.value}"
                        if failed_phase is not None
                        else "One or more phase jobs failed"
                    ),
                    actor=actor,
                    intention_id=intention_id,
                )
                continue

            if PhaseJobStatusEnum.WAITING_APPROVAL in statuses:
                await self.campaigns.transition_branch_status(
                    branch,
                    BranchStatusEnum.WAITING_APPROVAL,
                    reason="Branch has phase jobs waiting for approval",
                    actor=actor,
                    intention_id=intention_id,
                )
                continue

            if statuses.intersection({PhaseJobStatusEnum.RUNNING, PhaseJobStatusEnum.QUEUED}):
                await self.campaigns.transition_branch_status(
                    branch,
                    BranchStatusEnum.RUNNING,
                    actor=actor,
                    intention_id=intention_id,
                )
                continue

            if PhaseJobStatusEnum.BLOCKED in statuses:
                await self.campaigns.transition_branch_status(
                    branch,
                    BranchStatusEnum.BLOCKED,
                    reason="Branch has blocked phase jobs",
                    actor=actor,
                    intention_id=intention_id,
                )
                continue

            if PhaseJobStatusEnum.CREATED in statuses:
                await self.campaigns.transition_branch_status(
                    branch,
                    BranchStatusEnum.READY,
                    actor=actor,
                    intention_id=intention_id,
                )

    async def _reconcile_campaign_state(
        self,
        *,
        campaign: CampaignRun,
        branches: list[ExecutionBranch],
        phase_jobs: list[PhaseJob],
        actor: str,
    ) -> None:
        branch_statuses = [branch.status for branch in branches]
        phase_statuses = [phase.status for phase in phase_jobs]

        has_active_work = any(
            status in {PhaseJobStatusEnum.QUEUED, PhaseJobStatusEnum.RUNNING}
            for status in phase_statuses
        )
        has_waiting_approval = any(
            status == PhaseJobStatusEnum.WAITING_APPROVAL for status in phase_statuses
        ) or any(status == BranchStatusEnum.WAITING_APPROVAL for status in branch_statuses)
        has_blocked = any(status == PhaseJobStatusEnum.BLOCKED for status in phase_statuses) or any(
            status == BranchStatusEnum.BLOCKED for status in branch_statuses
        )
        has_ready_or_pending = any(
            status in {BranchStatusEnum.READY, BranchStatusEnum.PENDING}
            for status in branch_statuses
        )
        all_branches_completed = bool(branches) and all(
            status == BranchStatusEnum.COMPLETED for status in branch_statuses
        )
        all_branches_terminal = bool(branches) and all(
            status in TERMINAL_BRANCH_STATUSES for status in branch_statuses
        )
        any_branch_failed = any(
            status in {BranchStatusEnum.FAILED, BranchStatusEnum.CANCELED}
            for status in branch_statuses
        )
        all_phases_success = bool(phase_jobs) and all(
            status in BRANCH_SUCCESS_PHASE_STATUSES for status in phase_statuses
        )
        any_phase_failed = any(status in BRANCH_FAILURE_PHASE_STATUSES for status in phase_statuses)

        if all_branches_completed and (all_phases_success or not phase_jobs):
            await self.campaigns.transition_campaign_status(
                campaign,
                CampaignStatusEnum.COMPLETED,
                actor=actor,
            )
            return

        if all_branches_terminal and (any_branch_failed or any_phase_failed):
            await self.campaigns.transition_campaign_status(
                campaign,
                CampaignStatusEnum.FAILED,
                reason="One or more branches ended in terminal failure states",
                actor=actor,
            )
            return

        if has_active_work or has_ready_or_pending:
            await self.campaigns.transition_campaign_status(
                campaign,
                CampaignStatusEnum.RUNNING,
                actor=actor,
            )
            return

        if has_waiting_approval or has_blocked:
            await self.campaigns.transition_campaign_status(
                campaign,
                CampaignStatusEnum.BLOCKED,
                reason="No runnable jobs due to approval/dependency constraints",
                actor=actor,
            )
            return

        if campaign.status == CampaignStatusEnum.CREATED:
            await self.campaigns.transition_campaign_status(
                campaign,
                CampaignStatusEnum.READY,
                actor=actor,
            )
