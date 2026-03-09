from __future__ import annotations

import asyncio
from dataclasses import asdict
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
from ..schemas.campaigns import (
    ApprovalGateCreate,
    CampaignScheduleSummary,
    ExecutionResultIngestRequest,
    ExecutionResultIngestResponse,
)
from .approval_gate_service import ApprovalGateService
from .artifact_service import ArtifactService
from .audit_events import record_transition_event
from .campaign_service import CampaignService
from .finding_correlation_service import FindingCorrelationService
from .hil_db import get_async_session_maker
from .observation_service import ObservationService
from .tool_execution_service import ToolExecutionService


TERMINAL_TOOL_STATUSES = {
    ToolExecutionStatusEnum.COMPLETED,
    ToolExecutionStatusEnum.FAILED,
    ToolExecutionStatusEnum.CANCELED,
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


class ExecutionResultIngestionService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.campaigns = CampaignService(db)
        self.tool_exec = ToolExecutionService(db)
        self.approvals = ApprovalGateService(db)
        self.artifacts = ArtifactService(db)
        self.observations = ObservationService(db)

    async def _resolve_execution(self, payload: ExecutionResultIngestRequest) -> ToolExecution | None:
        if payload.execution_id is not None:
            return await self.tool_exec.get_execution(payload.execution_id)
        if payload.worker_task_id:
            result = await self.db.execute(
                select(ToolExecution)
                .where(ToolExecution.worker_task_id == payload.worker_task_id)
                .order_by(ToolExecution.created_at.desc())
                .limit(1)
            )
            match = result.scalar_one_or_none()
            if match is not None:
                return match
        if payload.phase_job_id is not None:
            result = await self.db.execute(
                select(ToolExecution)
                .where(ToolExecution.phase_job_id == payload.phase_job_id)
                .order_by(ToolExecution.created_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
        return None

    @staticmethod
    def _phase_intention_id(phase_job: PhaseJob | None, branch: ExecutionBranch | None) -> UUID | None:
        if phase_job and isinstance(phase_job.input_payload_json, dict):
            resolved = _maybe_uuid(
                phase_job.input_payload_json.get("intention_id")
                or phase_job.input_payload_json.get("seed_intention_id")
            )
            if resolved:
                return resolved
        if branch and isinstance(branch.branch_config_json, dict):
            return _maybe_uuid(
                branch.branch_config_json.get("intention_id")
                or branch.branch_config_json.get("seed_intention_id")
            )
        return None

    async def _latest_phase_gate(self, phase_job_id: UUID) -> ApprovalGate | None:
        result = await self.db.execute(
            select(ApprovalGate)
            .where(ApprovalGate.phase_job_id == phase_job_id)
            .order_by(ApprovalGate.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def mark_execution_running(
        self,
        *,
        worker_task_id: str,
        actor: str = "system.worker",
    ) -> bool:
        payload = ExecutionResultIngestRequest(
            worker_task_id=worker_task_id,
            tool_status=ToolExecutionStatusEnum.RUNNING,
            trigger_scheduler=False,
            actor=actor,
        )
        execution = await self._resolve_execution(payload)
        if execution is None:
            return False
        if execution.status in TERMINAL_TOOL_STATUSES:
            return True

        phase_job = (
            await self.campaigns.repo.get_phase_job(execution.phase_job_id)
            if execution.phase_job_id is not None
            else None
        )
        branch = (
            await self.campaigns.repo.get_branch(execution.branch_id)
            if execution.branch_id is not None
            else None
        )
        intention_id = execution.intention_id or self._phase_intention_id(phase_job, branch)

        await self.tool_exec.transition_execution(
            execution,
            ToolExecutionStatusEnum.RUNNING,
            actor=actor,
            intention_id=intention_id,
        )

        if phase_job is not None and phase_job.status in {
            PhaseJobStatusEnum.QUEUED,
            PhaseJobStatusEnum.CREATED,
        }:
            await self.campaigns.transition_phase_status(
                phase_job,
                PhaseJobStatusEnum.RUNNING,
                actor=actor,
                intention_id=intention_id,
            )
        if branch is not None and branch.status in {
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
        return True

    async def _scheduler_summary(
        self,
        campaign_id: UUID,
        *,
        actor: str,
    ) -> CampaignScheduleSummary:
        from .branch_scheduler import BranchScheduler

        result = await BranchScheduler(self.db).schedule_campaign(campaign_id, actor=actor)
        return CampaignScheduleSummary(**asdict(result))

    async def ingest_result(
        self,
        payload: ExecutionResultIngestRequest,
        *,
        actor: str | None = None,
    ) -> ExecutionResultIngestResponse:
        execution = await self._resolve_execution(payload)
        if execution is None:
            raise ValueError("ToolExecution not found for the provided execution/task identifiers")

        campaign = await self.campaigns.repo.get_campaign(execution.campaign_id)
        if campaign is None:
            raise ValueError(f"Campaign not found for execution {execution.id}")

        phase_job = (
            await self.campaigns.repo.get_phase_job(execution.phase_job_id)
            if execution.phase_job_id is not None
            else None
        )
        branch = (
            await self.campaigns.repo.get_branch(execution.branch_id)
            if execution.branch_id is not None
            else None
        )

        resolved_actor = payload.actor or actor or "system.worker"
        intention_id = payload.intention_id or execution.intention_id or self._phase_intention_id(
            phase_job, branch
        )
        placeholder = (execution.adapter_name or "").startswith("placeholder")

        await self.tool_exec.record_output_refs(
            execution,
            stdout_ref=payload.stdout_ref,
            stderr_ref=payload.stderr_ref,
            stdout_summary=payload.stdout_summary,
            stderr_summary=payload.stderr_summary,
        )

        if payload.tool_status == ToolExecutionStatusEnum.RUNNING:
            await self.tool_exec.transition_execution(
                execution,
                ToolExecutionStatusEnum.RUNNING,
                actor=resolved_actor,
                intention_id=intention_id,
            )
            if phase_job is not None and phase_job.status in {
                PhaseJobStatusEnum.CREATED,
                PhaseJobStatusEnum.QUEUED,
            }:
                await self.campaigns.transition_phase_status(
                    phase_job,
                    PhaseJobStatusEnum.RUNNING,
                    actor=resolved_actor,
                    intention_id=intention_id,
                )
            if branch is not None and branch.status in {
                BranchStatusEnum.PENDING,
                BranchStatusEnum.READY,
                BranchStatusEnum.WAITING_APPROVAL,
                BranchStatusEnum.BLOCKED,
            }:
                await self.campaigns.transition_branch_status(
                    branch,
                    BranchStatusEnum.RUNNING,
                    actor=resolved_actor,
                    intention_id=intention_id,
                )
            return ExecutionResultIngestResponse(
                campaign_id=campaign.id,
                branch_id=branch.id if branch else None,
                phase_job_id=phase_job.id if phase_job else None,
                execution_id=execution.id,
                tool_status=execution.status,
                phase_status=phase_job.status if phase_job else None,
                branch_status=branch.status if branch else None,
                campaign_status=campaign.status,
            )

        if payload.tool_status not in TERMINAL_TOOL_STATUSES and payload.tool_status != ToolExecutionStatusEnum.WAITING_APPROVAL:
            raise ValueError(
                f"Unsupported ingestion status: {payload.tool_status.value}. "
                "Expected RUNNING, COMPLETED, FAILED, CANCELED, or WAITING_APPROVAL."
            )

        if payload.tool_status == ToolExecutionStatusEnum.WAITING_APPROVAL:
            await self.tool_exec.transition_execution(
                execution,
                ToolExecutionStatusEnum.WAITING_APPROVAL,
                actor=resolved_actor,
                intention_id=intention_id,
                event_payload={"approval_reason": payload.approval_reason},
            )
            gate = (
                await self._latest_phase_gate(phase_job.id)
                if phase_job is not None
                else None
            )
            if gate is None and phase_job is not None:
                gate = await self.approvals.create_gate(
                    ApprovalGateCreate(
                        campaign_id=campaign.id,
                        branch_id=phase_job.branch_id,
                        phase_job_id=phase_job.id,
                        intention_id=intention_id,
                        gate_reason=payload.approval_reason
                        or f"Worker requested approval for phase '{phase_job.phase_name}'",
                        requested_by=resolved_actor,
                        policy_basis=phase_job.policy_class.value if phase_job.policy_class else None,
                    ),
                    actor=resolved_actor,
                )
            if gate is not None:
                execution.approval_gate_id = gate.id
                await self.db.flush()
            if phase_job is not None:
                await self.campaigns.transition_phase_status(
                    phase_job,
                    PhaseJobStatusEnum.WAITING_APPROVAL,
                    reason=payload.approval_reason or "Worker requested approval",
                    actor=resolved_actor,
                    intention_id=intention_id,
                )
            if branch is not None:
                await self.campaigns.transition_branch_status(
                    branch,
                    BranchStatusEnum.WAITING_APPROVAL,
                    reason=payload.approval_reason or "Worker requested approval",
                    actor=resolved_actor,
                    intention_id=intention_id,
                )
        else:
            await self.tool_exec.transition_execution(
                execution,
                payload.tool_status,
                exit_code=payload.exit_code,
                error_message=payload.error_message,
                canceled_by=payload.canceled_by,
                actor=resolved_actor,
                intention_id=intention_id,
                event_payload={"result_payload_keys": sorted(payload.result_payload_json.keys())},
            )

            if phase_job is not None:
                if payload.tool_status == ToolExecutionStatusEnum.COMPLETED:
                    target_phase_status = PhaseJobStatusEnum.COMPLETED
                elif payload.tool_status == ToolExecutionStatusEnum.CANCELED:
                    target_phase_status = PhaseJobStatusEnum.CANCELED
                else:
                    target_phase_status = PhaseJobStatusEnum.FAILED
                await self.campaigns.transition_phase_status(
                    phase_job,
                    target_phase_status,
                    reason=payload.error_message,
                    canceled_by=payload.canceled_by,
                    actor=resolved_actor,
                    intention_id=intention_id,
                )
                phase_job.output_summary_json = {
                    "tool_execution_id": str(execution.id),
                    "tool_status": payload.tool_status.value,
                    "result_payload_json": payload.result_payload_json,
                    "placeholder": placeholder,
                }
                if payload.error_message:
                    phase_job.error_message = payload.error_message
                await self.db.flush()

        created_artifacts = await self.artifacts.create_result_artifacts(
            execution=execution,
            phase_job=phase_job,
            intention_id=intention_id,
            result_payload_json=payload.result_payload_json,
            explicit_artifacts=payload.artifacts,
            stdout_ref=payload.stdout_ref,
            stderr_ref=payload.stderr_ref,
            actor=resolved_actor,
            placeholder=placeholder,
        )
        primary_artifact = created_artifacts[0] if created_artifacts else None
        created_observations = await self.observations.create_result_observations(
            execution=execution,
            phase_job=phase_job,
            source_artifact=primary_artifact,
            intention_id=intention_id,
            tool_status=payload.tool_status,
            result_payload_json=payload.result_payload_json,
            explicit_observations=payload.observations,
            error_message=payload.error_message,
            placeholder=placeholder,
            actor=resolved_actor,
        )
        correlator = FindingCorrelationService(self.db)
        correlation_outcomes = []
        for observation in created_observations:
            correlation_outcomes.append(
                await correlator.process_observation(
                    observation,
                    actor=f"{resolved_actor}.correlation",
                )
            )

        await record_transition_event(
            self.db,
            event_type="phase_job.result.ingested",
            actor=resolved_actor,
            message="Execution result ingested into canonical campaign state",
            campaign_id=campaign.id,
            branch_id=branch.id if branch else None,
            phase_job_id=phase_job.id if phase_job else None,
            tool_execution_id=execution.id,
            intention_id=intention_id,
            payload={
                "tool_status": payload.tool_status.value,
                "artifact_count": len(created_artifacts),
                "observation_count": len(created_observations),
                "correlated_observations": len(correlation_outcomes),
                "placeholder": placeholder,
            },
        )

        scheduler_summary: CampaignScheduleSummary | None = None
        if payload.trigger_scheduler:
            scheduler_summary = await self._scheduler_summary(
                campaign.id,
                actor=f"{resolved_actor}.scheduler",
            )

        refreshed_campaign = await self.campaigns.repo.get_campaign(campaign.id) or campaign
        refreshed_branch = (
            await self.campaigns.repo.get_branch(branch.id)
            if branch is not None
            else None
        )
        refreshed_phase = (
            await self.campaigns.repo.get_phase_job(phase_job.id)
            if phase_job is not None
            else None
        )
        refreshed_execution = await self.tool_exec.get_execution(execution.id) or execution

        return ExecutionResultIngestResponse(
            campaign_id=refreshed_campaign.id,
            branch_id=refreshed_branch.id if refreshed_branch else None,
            phase_job_id=refreshed_phase.id if refreshed_phase else None,
            execution_id=refreshed_execution.id,
            tool_status=refreshed_execution.status,
            phase_status=refreshed_phase.status if refreshed_phase else None,
            branch_status=refreshed_branch.status if refreshed_branch else None,
            campaign_status=refreshed_campaign.status,
            artifact_ids=[artifact.id for artifact in created_artifacts],
            observation_ids=[observation.id for observation in created_observations],
            scheduler=scheduler_summary,
        )


def mark_worker_execution_running_sync(
    *,
    worker_task_id: str,
    actor: str = "system.worker",
) -> dict[str, Any]:
    async def _runner() -> dict[str, Any]:
        session_maker = get_async_session_maker()
        async with session_maker() as db:
            svc = ExecutionResultIngestionService(db)
            updated = await svc.mark_execution_running(worker_task_id=worker_task_id, actor=actor)
            if updated:
                await db.commit()
            else:
                await db.rollback()
            return {"updated": updated}

    try:
        return asyncio.run(_runner())
    except Exception as exc:  # pragma: no cover - best effort in worker path
        return {"updated": False, "error": str(exc)}


def ingest_worker_result_sync(
    *,
    worker_task_id: str,
    tool_status: ToolExecutionStatusEnum,
    result_payload_json: dict | None = None,
    exit_code: int | None = None,
    error_message: str | None = None,
    stdout_ref: str | None = None,
    stderr_ref: str | None = None,
    actor: str = "system.worker",
) -> dict[str, Any]:
    async def _runner() -> dict[str, Any]:
        session_maker = get_async_session_maker()
        async with session_maker() as db:
            svc = ExecutionResultIngestionService(db)
            try:
                response = await svc.ingest_result(
                    ExecutionResultIngestRequest(
                        worker_task_id=worker_task_id,
                        tool_status=tool_status,
                        result_payload_json=result_payload_json or {},
                        exit_code=exit_code,
                        error_message=error_message,
                        stdout_ref=stdout_ref,
                        stderr_ref=stderr_ref,
                        actor=actor,
                    ),
                    actor=actor,
                )
            except ValueError as exc:
                await db.rollback()
                return {"ingested": False, "reason": str(exc)}
            await db.commit()
            return {
                "ingested": True,
                "execution_id": str(response.execution_id),
                "campaign_id": str(response.campaign_id),
                "phase_job_id": str(response.phase_job_id) if response.phase_job_id else None,
                "tool_status": response.tool_status.value,
            }

    try:
        return asyncio.run(_runner())
    except Exception as exc:  # pragma: no cover - best effort in worker path
        return {"ingested": False, "error": str(exc)}
