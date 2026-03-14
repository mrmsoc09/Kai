from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.campaign import Artifact, Observation, ToolExecution
from ..models.enums import ToolExecutionStatusEnum
from ..schemas.campaigns import ArtifactCreate, ObservationCreate, ToolExecutionCreate
from .audit_events import record_transition_event


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


TOOL_ALLOWED_TRANSITIONS: dict[ToolExecutionStatusEnum, set[ToolExecutionStatusEnum]] = {
    ToolExecutionStatusEnum.CREATED: {
        ToolExecutionStatusEnum.QUEUED,
        ToolExecutionStatusEnum.RUNNING,
        ToolExecutionStatusEnum.WAITING_APPROVAL,
        ToolExecutionStatusEnum.COMPLETED,
        ToolExecutionStatusEnum.FAILED,
        ToolExecutionStatusEnum.CANCELED,
    },
    ToolExecutionStatusEnum.QUEUED: {
        ToolExecutionStatusEnum.RUNNING,
        ToolExecutionStatusEnum.WAITING_APPROVAL,
        ToolExecutionStatusEnum.COMPLETED,
        ToolExecutionStatusEnum.FAILED,
        ToolExecutionStatusEnum.CANCELED,
    },
    ToolExecutionStatusEnum.RUNNING: {
        ToolExecutionStatusEnum.WAITING_APPROVAL,
        ToolExecutionStatusEnum.COMPLETED,
        ToolExecutionStatusEnum.FAILED,
        ToolExecutionStatusEnum.CANCELED,
    },
    ToolExecutionStatusEnum.WAITING_APPROVAL: {
        ToolExecutionStatusEnum.QUEUED,
        ToolExecutionStatusEnum.RUNNING,
        ToolExecutionStatusEnum.FAILED,
        ToolExecutionStatusEnum.CANCELED,
    },
    ToolExecutionStatusEnum.COMPLETED: set(),
    ToolExecutionStatusEnum.FAILED: set(),
    ToolExecutionStatusEnum.CANCELED: set(),
}


def validate_tool_transition(current: ToolExecutionStatusEnum, target: ToolExecutionStatusEnum) -> None:
    if target not in TOOL_ALLOWED_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid tool execution transition {current.value} -> {target.value}")


class ToolExecutionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_execution(
        self,
        payload: ToolExecutionCreate,
        *,
        actor: str | None = None,
    ) -> ToolExecution:
        record = ToolExecution(
            campaign_id=payload.campaign_id,
            branch_id=payload.branch_id,
            phase_job_id=payload.phase_job_id,
            stage_run_id=payload.stage_run_id,
            approval_gate_id=payload.approval_gate_id,
            intention_id=payload.intention_id,
            tool_name=payload.tool_name,
            adapter_name=payload.adapter_name,
            execution_mode=payload.execution_mode,
            input_target=payload.input_target,
            input_payload_json=payload.input_payload_json,
            policy_class=payload.policy_class,
            max_retries=max(0, payload.max_retries),
            status=ToolExecutionStatusEnum.CREATED,
        )
        self.db.add(record)
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="tool_execution.created",
            actor=actor,
            message=f"Tool execution created for {record.tool_name}",
            campaign_id=record.campaign_id,
            branch_id=record.branch_id,
            phase_job_id=record.phase_job_id,
            tool_execution_id=record.id,
            approval_gate_id=record.approval_gate_id,
            intention_id=record.intention_id,
            payload={"status": record.status.value, "tool_name": record.tool_name},
        )
        return record

    async def get_execution(self, execution_id: UUID) -> ToolExecution | None:
        result = await self.db.execute(select(ToolExecution).where(ToolExecution.id == execution_id))
        return result.scalar_one_or_none()

    async def transition_execution(
        self,
        execution: ToolExecution,
        target_status: ToolExecutionStatusEnum,
        *,
        worker_task_id: str | None = None,
        exit_code: int | None = None,
        error_message: str | None = None,
        canceled_by: str | None = None,
        actor: str | None = None,
        intention_id: UUID | None = None,
        event_payload: dict | None = None,
    ) -> ToolExecution:
        previous = execution.status
        if previous == target_status:
            return execution
        validate_tool_transition(execution.status, target_status)
        execution.status = target_status
        if worker_task_id:
            execution.worker_task_id = worker_task_id
        if target_status == ToolExecutionStatusEnum.QUEUED:
            execution.queued_at = _utcnow()
        if target_status == ToolExecutionStatusEnum.RUNNING and execution.started_at is None:
            execution.started_at = _utcnow()
        if target_status in {ToolExecutionStatusEnum.COMPLETED, ToolExecutionStatusEnum.FAILED}:
            execution.ended_at = _utcnow()
            if execution.started_at is not None:
                execution.duration_ms = (
                    execution.ended_at - execution.started_at
                ).total_seconds() * 1000
        if target_status == ToolExecutionStatusEnum.CANCELED:
            execution.canceled_at = _utcnow()
            execution.canceled_by = canceled_by
            if execution.started_at is not None:
                execution.duration_ms = (
                    execution.canceled_at - execution.started_at
                ).total_seconds() * 1000
        if exit_code is not None:
            execution.exit_code = exit_code
        if error_message is not None:
            execution.error_message = error_message
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="tool_execution.status.changed",
            actor=actor,
            message=f"Tool execution status {previous.value} -> {target_status.value}",
            campaign_id=execution.campaign_id,
            branch_id=execution.branch_id,
            phase_job_id=execution.phase_job_id,
            tool_execution_id=execution.id,
            approval_gate_id=execution.approval_gate_id,
            intention_id=intention_id or execution.intention_id,
            payload={
                "from": previous.value,
                "to": target_status.value,
                "worker_task_id": execution.worker_task_id,
                **(event_payload or {}),
            },
        )
        return execution

    async def mark_retry(
        self,
        execution: ToolExecution,
        *,
        actor: str | None = None,
        intention_id: UUID | None = None,
    ) -> ToolExecution:
        execution.retry_count += 1
        execution.status = ToolExecutionStatusEnum.QUEUED
        execution.error_message = None
        execution.queued_at = _utcnow()
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="tool_execution.retry.queued",
            actor=actor,
            message="Tool execution queued for retry",
            campaign_id=execution.campaign_id,
            branch_id=execution.branch_id,
            phase_job_id=execution.phase_job_id,
            tool_execution_id=execution.id,
            approval_gate_id=execution.approval_gate_id,
            intention_id=intention_id or execution.intention_id,
            payload={"retry_count": execution.retry_count},
        )
        return execution

    async def record_output_refs(
        self,
        execution: ToolExecution,
        *,
        stdout_ref: str | None = None,
        stderr_ref: str | None = None,
        stdout_summary: str | None = None,
        stderr_summary: str | None = None,
    ) -> ToolExecution:
        if stdout_ref is not None:
            execution.stdout_ref = stdout_ref
        if stderr_ref is not None:
            execution.stderr_ref = stderr_ref
        if stdout_summary is not None:
            execution.stdout_summary = stdout_summary
        if stderr_summary is not None:
            execution.stderr_summary = stderr_summary
        await self.db.flush()
        return execution

    async def create_artifact(
        self,
        payload: ArtifactCreate,
        *,
        actor: str | None = None,
    ) -> Artifact:
        record = Artifact(
            campaign_id=payload.campaign_id,
            branch_id=payload.branch_id,
            phase_job_id=payload.phase_job_id,
            tool_execution_id=payload.tool_execution_id,
            finding_id=payload.finding_id,
            report_id=payload.report_id,
            intention_id=payload.intention_id,
            artifact_type=payload.artifact_type,
            uri=payload.uri,
            content_hash=payload.content_hash,
            mime_type=payload.mime_type,
            size_bytes=payload.size_bytes,
            description=payload.description,
            policy_class=payload.policy_class,
            details_json=payload.details_json,
        )
        self.db.add(record)
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="artifact.created",
            actor=actor,
            message=f"Artifact recorded ({record.artifact_type.value})",
            campaign_id=record.campaign_id,
            branch_id=record.branch_id,
            phase_job_id=record.phase_job_id,
            tool_execution_id=record.tool_execution_id,
            intention_id=record.intention_id,
            payload={"artifact_id": str(record.id), "uri": record.uri},
        )
        return record

    async def create_observation(
        self,
        payload: ObservationCreate,
        *,
        actor: str | None = None,
    ) -> Observation:
        record = Observation(
            campaign_id=payload.campaign_id,
            branch_id=payload.branch_id,
            phase_job_id=payload.phase_job_id,
            tool_execution_id=payload.tool_execution_id,
            source_artifact_id=payload.source_artifact_id,
            finding_id=payload.finding_id,
            intention_id=payload.intention_id,
            observation_type=payload.observation_type,
            category=payload.category,
            title=payload.title,
            summary=payload.summary,
            confidence=payload.confidence,
            policy_class=payload.policy_class,
            normalized_ref=payload.normalized_ref,
            payload_json=payload.payload_json,
        )
        self.db.add(record)
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="observation.created",
            actor=actor,
            message=f"Observation recorded ({record.observation_type.value})",
            campaign_id=record.campaign_id,
            branch_id=record.branch_id,
            phase_job_id=record.phase_job_id,
            tool_execution_id=record.tool_execution_id,
            intention_id=record.intention_id,
            payload={"observation_id": str(record.id), "category": record.category},
        )
        return record
