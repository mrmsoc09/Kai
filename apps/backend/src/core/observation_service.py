from __future__ import annotations

from typing import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.campaign import Artifact, Observation, PhaseJob, ToolExecution
from ..models.enums import ObservationTypeEnum, ToolExecutionStatusEnum
from ..schemas.campaigns import ExecutionResultObservationInput, ObservationCreate
from .tool_execution_service import ToolExecutionService


DEFAULT_PHASE_OBSERVATION: dict[str, tuple[ObservationTypeEnum, str]] = {
    "recon_discovery": (ObservationTypeEnum.DISCOVERY, "DISCOVERY"),
    "target_validation": (ObservationTypeEnum.VALIDATION, "VALIDATION"),
    "lightweight_analysis": (ObservationTypeEnum.SIGNAL, "SIGNAL"),
}


class ObservationService:
    """First-pass observation normalization for phase execution results."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.tool_exec = ToolExecutionService(db)

    async def create_result_observations(
        self,
        *,
        execution: ToolExecution,
        phase_job: PhaseJob | None,
        source_artifact: Artifact | None,
        intention_id,
        tool_status: ToolExecutionStatusEnum,
        result_payload_json: dict,
        explicit_observations: Iterable[ExecutionResultObservationInput],
        error_message: str | None,
        placeholder: bool,
        actor: str | None,
    ) -> list[Observation]:
        created: list[Observation] = []

        for item in explicit_observations:
            created.append(
                await self.tool_exec.create_observation(
                    ObservationCreate(
                        campaign_id=execution.campaign_id,
                        branch_id=execution.branch_id,
                        phase_job_id=execution.phase_job_id,
                        tool_execution_id=execution.id,
                        source_artifact_id=source_artifact.id if source_artifact else None,
                        intention_id=intention_id,
                        observation_type=item.observation_type,
                        category=item.category,
                        title=item.title,
                        summary=item.summary,
                        confidence=item.confidence,
                        policy_class=execution.policy_class,
                        normalized_ref=item.normalized_ref,
                        payload_json=item.payload_json,
                    ),
                    actor=actor,
                )
            )

        if tool_status == ToolExecutionStatusEnum.COMPLETED:
            default_type, default_category = DEFAULT_PHASE_OBSERVATION.get(
                phase_job.phase_name if phase_job else "",
                (ObservationTypeEnum.CONTEXT, "CONTEXT"),
            )
            summary = (
                "Placeholder phase completed; no concrete tool adapter was configured."
                if placeholder
                else "Phase execution completed."
            )
            title = (
                f"{phase_job.phase_name} placeholder completion"
                if placeholder and phase_job
                else f"{phase_job.phase_name} completed" if phase_job else "Phase completed"
            )
        elif tool_status == ToolExecutionStatusEnum.FAILED:
            default_type = ObservationTypeEnum.DECISION
            default_category = "EXECUTION_FAILURE"
            summary = error_message or "Tool execution failed"
            title = f"{phase_job.phase_name} failed" if phase_job else "Phase execution failed"
        elif tool_status == ToolExecutionStatusEnum.CANCELED:
            default_type = ObservationTypeEnum.DECISION
            default_category = "EXECUTION_CANCELED"
            summary = "Tool execution was canceled."
            title = f"{phase_job.phase_name} canceled" if phase_job else "Phase execution canceled"
        else:
            default_type = ObservationTypeEnum.DECISION
            default_category = "APPROVAL_WAIT"
            summary = "Tool execution is waiting for approval to continue."
            title = (
                f"{phase_job.phase_name} waiting for approval"
                if phase_job
                else "Execution waiting for approval"
            )

        created.append(
            await self.tool_exec.create_observation(
                ObservationCreate(
                    campaign_id=execution.campaign_id,
                    branch_id=execution.branch_id,
                    phase_job_id=execution.phase_job_id,
                    tool_execution_id=execution.id,
                    source_artifact_id=source_artifact.id if source_artifact else None,
                    intention_id=intention_id,
                    observation_type=default_type,
                    category=default_category,
                    title=title,
                    summary=summary,
                    confidence=None if tool_status != ToolExecutionStatusEnum.COMPLETED else 0.5,
                    policy_class=execution.policy_class,
                    payload_json={
                        "placeholder": placeholder,
                        "phase_name": phase_job.phase_name if phase_job else None,
                        "tool_status": tool_status.value,
                        "result_payload_json": result_payload_json,
                    },
                ),
                actor=actor,
            )
        )
        return created
