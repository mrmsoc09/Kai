from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from .evidence_qualification_engine import qualify_evidence
from .impact_validation_engine import validate_impact
from ..models.campaign import ToolExecution
from ..models.enums import (
    CorrelationActionEnum,
    StageRunStatusEnum,
    ToolExecutionStatusEnum,
    WorkflowRunStatusEnum,
)
from ..models.workflow import CorrelationRecord, StageRun, WorkflowFinding, WorkflowRun


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class WorkflowRunRepository:
    db: AsyncSession

    async def add(self, model: object) -> None:
        self.db.add(model)
        await self.db.flush()

    async def get_workflow_run(self, workflow_run_id: UUID) -> WorkflowRun | None:
        result = await self.db.execute(
            select(WorkflowRun).where(WorkflowRun.id == workflow_run_id)
        )
        return result.scalar_one_or_none()

    async def get_workflow_run_by_campaign(self, campaign_run_id: UUID) -> WorkflowRun | None:
        result = await self.db.execute(
            select(WorkflowRun)
            .where(WorkflowRun.campaign_run_id == campaign_run_id)
            .order_by(WorkflowRun.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_workflow_runs(
        self,
        *,
        campaign_run_id: UUID | None = None,
        status: WorkflowRunStatusEnum | None = None,
        template_name: str | None = None,
        limit: int = 100,
    ) -> list[WorkflowRun]:
        stmt: Select[tuple[WorkflowRun]] = select(WorkflowRun).order_by(
            WorkflowRun.created_at.desc()
        )
        if campaign_run_id is not None:
            stmt = stmt.where(WorkflowRun.campaign_run_id == campaign_run_id)
        if status is not None:
            stmt = stmt.where(WorkflowRun.status == status)
        if template_name:
            stmt = stmt.where(WorkflowRun.template_name == template_name)
        stmt = stmt.limit(max(1, min(limit, 500)))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_stage_run(self, stage_run_id: UUID) -> StageRun | None:
        result = await self.db.execute(
            select(StageRun).where(StageRun.id == stage_run_id)
        )
        return result.scalar_one_or_none()

    async def list_stage_runs(self, workflow_run_id: UUID) -> list[StageRun]:
        result = await self.db.execute(
            select(StageRun)
            .where(StageRun.workflow_run_id == workflow_run_id)
            .order_by(StageRun.stage_order.asc(), StageRun.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_tool_executions(self, workflow_run_id: UUID) -> list[ToolExecution]:
        result = await self.db.execute(
            select(ToolExecution)
            .join(StageRun, ToolExecution.stage_run_id == StageRun.id)
            .where(StageRun.workflow_run_id == workflow_run_id)
            .order_by(ToolExecution.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_workflow_findings(self, workflow_run_id: UUID) -> list[WorkflowFinding]:
        result = await self.db.execute(
            select(WorkflowFinding)
            .where(WorkflowFinding.workflow_run_id == workflow_run_id)
            .order_by(WorkflowFinding.created_at.asc())
        )
        return list(result.scalars().all())

    async def list_correlation_records(self, workflow_run_id: UUID) -> list[CorrelationRecord]:
        result = await self.db.execute(
            select(CorrelationRecord)
            .where(CorrelationRecord.workflow_run_id == workflow_run_id)
            .order_by(CorrelationRecord.created_at.asc())
        )
        return list(result.scalars().all())


class WorkflowRunService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = WorkflowRunRepository(db=db)

    async def create_workflow_run(
        self,
        *,
        campaign_run_id: UUID,
        scope_target_id: UUID | None,
        template_name: str,
        target: str,
        safe_mode: bool,
        dry_run: bool,
        trigger_source: str,
        total_phases: int,
        artifact_manifest_path: str | None = None,
        plan_artifact_path: str | None = None,
    ) -> WorkflowRun:
        record = WorkflowRun(
            campaign_run_id=campaign_run_id,
            scope_target_id=scope_target_id,
            template_name=template_name,
            target=target,
            safe_mode=safe_mode,
            dry_run=dry_run,
            trigger_source=trigger_source,
            total_phases=total_phases,
            completed_phases=0,
            status=WorkflowRunStatusEnum.PENDING,
            artifact_manifest_path=artifact_manifest_path,
            plan_artifact_path=plan_artifact_path,
        )
        await self.repo.add(record)
        return record

    async def create_stage_run(
        self,
        *,
        workflow_run_id: UUID,
        campaign_run_id: UUID,
        stage_name: str,
        stage_order: int,
        phase_count: int,
    ) -> StageRun:
        record = StageRun(
            workflow_run_id=workflow_run_id,
            campaign_run_id=campaign_run_id,
            stage_name=stage_name,
            stage_order=stage_order,
            phase_count=phase_count,
            completed_count=0,
            status=StageRunStatusEnum.PENDING,
        )
        await self.repo.add(record)
        return record

    async def transition_workflow_run(
        self,
        workflow_run: WorkflowRun,
        target_status: WorkflowRunStatusEnum,
        *,
        artifact_manifest_path: str | None = None,
        summary_artifact_path: str | None = None,
    ) -> WorkflowRun:
        if workflow_run.status == target_status:
            return workflow_run
        workflow_run.status = target_status
        if target_status == WorkflowRunStatusEnum.RUNNING and workflow_run.started_at is None:
            workflow_run.started_at = _utcnow()
        if target_status in {
            WorkflowRunStatusEnum.COMPLETED,
            WorkflowRunStatusEnum.FAILED,
            WorkflowRunStatusEnum.CANCELED,
        }:
            workflow_run.ended_at = _utcnow()
            if workflow_run.started_at is not None:
                workflow_run.duration_ms = (
                    workflow_run.ended_at - workflow_run.started_at
                ).total_seconds() * 1000
        if artifact_manifest_path is not None:
            workflow_run.artifact_manifest_path = artifact_manifest_path
        if summary_artifact_path is not None:
            workflow_run.summary_artifact_path = summary_artifact_path
        await self.db.flush()
        return workflow_run

    async def transition_stage_run(
        self,
        stage_run: StageRun,
        target_status: StageRunStatusEnum,
        *,
        failure_reason: str | None = None,
    ) -> StageRun:
        if stage_run.status == target_status:
            return stage_run
        stage_run.status = target_status
        if target_status == StageRunStatusEnum.RUNNING and stage_run.started_at is None:
            stage_run.started_at = _utcnow()
        if target_status in {
            StageRunStatusEnum.COMPLETED,
            StageRunStatusEnum.FAILED,
            StageRunStatusEnum.BLOCKED,
        }:
            stage_run.ended_at = _utcnow()
            if stage_run.started_at is not None:
                stage_run.duration_ms = (
                    stage_run.ended_at - stage_run.started_at
                ).total_seconds() * 1000
        if failure_reason:
            stage_run.failure_reason = failure_reason
        await self.db.flush()
        return stage_run

    async def advance_stage_progress(
        self,
        stage_run: StageRun,
        *,
        failed: bool = False,
    ) -> StageRun:
        """Increment completed_count; transition status if all phases done."""
        if not failed:
            stage_run.completed_count = min(
                stage_run.completed_count + 1, stage_run.phase_count
            )
        await self.db.flush()
        if failed:
            return await self.transition_stage_run(
                stage_run,
                StageRunStatusEnum.FAILED,
                failure_reason="stage failed due to one or more tool execution failures",
            )
        if stage_run.phase_count > 0 and stage_run.completed_count >= stage_run.phase_count:
            return await self.transition_stage_run(stage_run, StageRunStatusEnum.COMPLETED)
        if stage_run.status == StageRunStatusEnum.PENDING:
            return await self.transition_stage_run(stage_run, StageRunStatusEnum.RUNNING)
        return stage_run

    async def advance_workflow_progress(
        self,
        workflow_run: WorkflowRun,
        *,
        failed: bool = False,
    ) -> WorkflowRun:
        """Increment completed_phases; transition status if all phases done."""
        if not failed:
            workflow_run.completed_phases = min(
                workflow_run.completed_phases + 1, workflow_run.total_phases
            )
        await self.db.flush()
        if failed:
            return await self.transition_workflow_run(workflow_run, WorkflowRunStatusEnum.FAILED)
        if (
            workflow_run.total_phases > 0
            and workflow_run.completed_phases >= workflow_run.total_phases
        ):
            return await self.transition_workflow_run(
                workflow_run, WorkflowRunStatusEnum.COMPLETED
            )
        if workflow_run.status == WorkflowRunStatusEnum.PENDING:
            return await self.transition_workflow_run(workflow_run, WorkflowRunStatusEnum.RUNNING)
        return workflow_run

    async def create_tool_execution(
        self,
        *,
        campaign_id: UUID,
        stage_run_id: UUID,
        tool_name: str,
        execution_mode: str | None,
        target: str | None,
        retry_count: int = 0,
        max_retries: int = 0,
    ) -> ToolExecution:
        record = ToolExecution(
            campaign_id=campaign_id,
            stage_run_id=stage_run_id,
            tool_name=tool_name,
            execution_mode=execution_mode,
            input_target=target,
            retry_count=max(0, retry_count),
            max_retries=max(0, max_retries),
            status=ToolExecutionStatusEnum.CREATED,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def transition_tool_execution(
        self,
        execution: ToolExecution,
        target_status: ToolExecutionStatusEnum,
        *,
        exit_code: int | None = None,
        stdout_summary: str | None = None,
        stderr_summary: str | None = None,
        artifact_path: str | None = None,
        error_message: str | None = None,
    ) -> ToolExecution:
        execution.status = target_status
        now = _utcnow()
        if target_status == ToolExecutionStatusEnum.RUNNING and execution.started_at is None:
            execution.started_at = now
        if target_status in {
            ToolExecutionStatusEnum.COMPLETED,
            ToolExecutionStatusEnum.FAILED,
            ToolExecutionStatusEnum.CANCELED,
        }:
            execution.ended_at = now
            if execution.started_at is not None:
                execution.duration_ms = (execution.ended_at - execution.started_at).total_seconds() * 1000
        if exit_code is not None:
            execution.exit_code = exit_code
        if stdout_summary is not None:
            execution.stdout_summary = stdout_summary
        if stderr_summary is not None:
            execution.stderr_summary = stderr_summary
        if artifact_path is not None:
            execution.artifact_path = artifact_path
        if error_message is not None:
            execution.error_message = error_message
        await self.db.flush()
        return execution

    async def create_workflow_finding(
        self,
        *,
        workflow_run_id: UUID,
        campaign_id: UUID | None,
        stage_run_id: UUID | None,
        tool_execution_id: UUID | None,
        asset_identifier: str,
        endpoint: str | None,
        parameter: str | None,
        vulnerability_type: str,
        confidence_score: float | None,
        severity_hint: str | None,
        evidence_artifact_path: str | None,
        details_json: dict | None = None,
    ) -> WorkflowFinding:
        detail_payload = dict(details_json or {})
        qualification = qualify_evidence(
            {
                **detail_payload,
                "finding_id": str(workflow_run_id),
                "vulnerability_type": vulnerability_type,
                "severity": severity_hint,
                "target": asset_identifier,
                "endpoint": endpoint,
                "parameter": parameter,
                "confidence_score": confidence_score,
                "evidence": [evidence_artifact_path] if evidence_artifact_path else [],
            },
            scope_metadata={
                "target": asset_identifier,
                "in_scope": True,
            },
            mission_id=str(workflow_run_id),
            stage_id="workflow_finding_creation",
            report_id=str(tool_execution_id or ""),
            persist=True,
            update_duplicate_history=True,
        )
        detail_payload["evidence_qualification"] = qualification.to_dict()
        detail_payload["impact_validation"] = validate_impact(
            finding={
                **detail_payload,
                "finding_id": str(workflow_run_id),
                "vulnerability_type": vulnerability_type,
                "severity": severity_hint,
                "target": asset_identifier,
                "endpoint": endpoint,
                "parameter": parameter,
                "confidence_score": confidence_score,
            },
            qualification=qualification.to_dict(),
            baseline_response=detail_payload.get("baseline_response"),
            exploit_response=detail_payload.get("exploit_response"),
            scope_metadata={
                "target": asset_identifier,
                "in_scope": True,
            },
            mission_id=str(workflow_run_id),
            stage_id="workflow_finding_impact_validation",
            report_id=str(tool_execution_id or ""),
            persist=True,
        ).to_dict()

        record = WorkflowFinding(
            workflow_run_id=workflow_run_id,
            campaign_id=campaign_id,
            stage_run_id=stage_run_id,
            tool_execution_id=tool_execution_id,
            asset_identifier=asset_identifier,
            endpoint=endpoint,
            parameter=parameter,
            vulnerability_type=vulnerability_type,
            confidence_score=confidence_score,
            severity_hint=severity_hint,
            evidence_artifact_path=evidence_artifact_path,
            details_json=detail_payload,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def create_workflow_correlation_record(
        self,
        *,
        workflow_run_id: UUID,
        campaign_id: UUID | None,
        asset_identifier: str,
        signal_sources: list[str],
        confidence_score: float | None,
        priority_rank: int | None,
        explanation: str | None,
    ) -> CorrelationRecord:
        record = CorrelationRecord(
            workflow_run_id=workflow_run_id,
            campaign_id=campaign_id,
            asset_identifier=asset_identifier,
            signal_sources_json=signal_sources,
            confidence=confidence_score,
            priority_rank=priority_rank,
            explanation=explanation,
            correlation_rule="workflow_signal_graph",
            action=CorrelationActionEnum.CREATED,
        )
        self.db.add(record)
        await self.db.flush()
        return record

    async def get_workflow_run(self, workflow_run_id: UUID) -> WorkflowRun | None:
        return await self.repo.get_workflow_run(workflow_run_id)

    async def get_workflow_run_by_campaign(self, campaign_run_id: UUID) -> WorkflowRun | None:
        return await self.repo.get_workflow_run_by_campaign(campaign_run_id)

    async def list_workflow_runs(
        self,
        *,
        campaign_run_id: UUID | None = None,
        status: WorkflowRunStatusEnum | None = None,
        template_name: str | None = None,
        limit: int = 100,
    ) -> list[WorkflowRun]:
        return await self.repo.list_workflow_runs(
            campaign_run_id=campaign_run_id,
            status=status,
            template_name=template_name,
            limit=limit,
        )

    async def list_stage_runs(self, workflow_run_id: UUID) -> list[StageRun]:
        return await self.repo.list_stage_runs(workflow_run_id)

    async def list_tool_executions(self, workflow_run_id: UUID) -> list[ToolExecution]:
        return await self.repo.list_tool_executions(workflow_run_id)

    async def list_workflow_findings(self, workflow_run_id: UUID) -> list[WorkflowFinding]:
        return await self.repo.list_workflow_findings(workflow_run_id)

    async def list_correlation_records(self, workflow_run_id: UUID) -> list[CorrelationRecord]:
        return await self.repo.list_correlation_records(workflow_run_id)
