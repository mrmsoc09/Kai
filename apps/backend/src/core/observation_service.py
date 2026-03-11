from __future__ import annotations

from typing import Iterable

from sqlalchemy import select
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

    async def _existing_for_dedupe(
        self,
        *,
        execution_id,
        dedupe_key: str,
        ingestion_fingerprint: str | None,
    ) -> Observation | None:
        try:
            result = await self.db.execute(
                select(Observation)
                .where(Observation.tool_execution_id == execution_id)
                .order_by(Observation.created_at.desc())
                .limit(20)
            )
            for observation in result.scalars().all():
                payload = observation.payload_json if isinstance(observation.payload_json, dict) else {}
                if payload.get("dedupe_key") != dedupe_key:
                    continue
                if ingestion_fingerprint is None:
                    return observation
                if payload.get("ingestion_fingerprint") == ingestion_fingerprint:
                    return observation
        except Exception:
            return None
        return None

    async def _create_or_reuse_observation(
        self,
        *,
        execution: ToolExecution,
        phase_job: PhaseJob | None,
        source_artifact: Artifact | None,
        intention_id,
        actor: str | None,
        dedupe_key: str,
        ingestion_fingerprint: str | None,
        observation_type: ObservationTypeEnum,
        category: str | None,
        title: str | None,
        summary: str | None,
        confidence: float | None,
        normalized_ref: str | None = None,
        payload_json: dict | None = None,
    ) -> Observation:
        existing = await self._existing_for_dedupe(
            execution_id=execution.id,
            dedupe_key=dedupe_key,
            ingestion_fingerprint=ingestion_fingerprint,
        )
        if existing is not None:
            return existing

        payload = dict(payload_json) if isinstance(payload_json, dict) else {}
        payload.setdefault("dedupe_key", dedupe_key)
        if ingestion_fingerprint is not None:
            payload.setdefault("ingestion_fingerprint", ingestion_fingerprint)

        return await self.tool_exec.create_observation(
            ObservationCreate(
                campaign_id=execution.campaign_id,
                branch_id=execution.branch_id,
                phase_job_id=execution.phase_job_id,
                tool_execution_id=execution.id,
                source_artifact_id=source_artifact.id if source_artifact else None,
                intention_id=intention_id,
                observation_type=observation_type,
                category=category,
                title=title,
                summary=summary,
                confidence=confidence,
                policy_class=execution.policy_class,
                normalized_ref=normalized_ref,
                payload_json=payload,
            ),
            actor=actor,
        )

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
        ingestion_fingerprint: str | None = None,
    ) -> list[Observation]:
        created: list[Observation] = []

        for index, item in enumerate(explicit_observations):
            created.append(
                await self._create_or_reuse_observation(
                    execution=execution,
                    phase_job=phase_job,
                    source_artifact=source_artifact,
                    intention_id=intention_id,
                    actor=actor,
                    dedupe_key=(
                        f"explicit:{index}:{item.observation_type.value}:"
                        f"{item.category or ''}:{item.title or ''}"
                    ),
                    ingestion_fingerprint=ingestion_fingerprint,
                    observation_type=item.observation_type,
                    category=item.category,
                    title=item.title,
                    summary=item.summary,
                    confidence=item.confidence,
                    normalized_ref=item.normalized_ref,
                    payload_json=item.payload_json,
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
            await self._create_or_reuse_observation(
                execution=execution,
                phase_job=phase_job,
                source_artifact=source_artifact,
                intention_id=intention_id,
                actor=actor,
                dedupe_key=f"auto:default:{tool_status.value}:{default_category}",
                ingestion_fingerprint=ingestion_fingerprint,
                observation_type=default_type,
                category=default_category,
                title=title,
                summary=summary,
                confidence=None if tool_status != ToolExecutionStatusEnum.COMPLETED else 0.5,
                payload_json={
                    "placeholder": placeholder,
                    "phase_name": phase_job.phase_name if phase_job else None,
                    "tool_status": tool_status.value,
                    "result_payload_json": result_payload_json,
                },
            )
        )
        return created
