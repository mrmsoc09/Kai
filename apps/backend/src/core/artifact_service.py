from __future__ import annotations

from typing import Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from ..models.campaign import Artifact, PhaseJob, ToolExecution
from ..models.enums import ArtifactTypeEnum
from ..schemas.campaigns import ArtifactCreate, ExecutionResultArtifactInput
from .tool_execution_service import ToolExecutionService


class ArtifactService:
    """Canonical artifact creation helpers for execution-result ingestion."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.tool_exec = ToolExecutionService(db)

    @staticmethod
    def _inline_uri(execution: ToolExecution, label: str) -> str:
        return f"inline://tool-execution/{execution.id}/{label}"

    async def create_result_artifacts(
        self,
        *,
        execution: ToolExecution,
        phase_job: PhaseJob | None,
        intention_id,
        result_payload_json: dict,
        explicit_artifacts: Iterable[ExecutionResultArtifactInput],
        stdout_ref: str | None,
        stderr_ref: str | None,
        actor: str | None,
        placeholder: bool,
    ) -> list[Artifact]:
        created: list[Artifact] = []

        for item in explicit_artifacts:
            created.append(
                await self.tool_exec.create_artifact(
                    ArtifactCreate(
                        campaign_id=execution.campaign_id,
                        branch_id=execution.branch_id,
                        phase_job_id=execution.phase_job_id,
                        tool_execution_id=execution.id,
                        intention_id=intention_id,
                        artifact_type=item.artifact_type,
                        uri=item.uri or self._inline_uri(execution, item.artifact_type.value.lower()),
                        content_hash=item.content_hash,
                        mime_type=item.mime_type,
                        size_bytes=item.size_bytes,
                        description=item.description,
                        policy_class=execution.policy_class,
                        details_json=item.details_json,
                    ),
                    actor=actor,
                )
            )

        if result_payload_json:
            created.append(
                await self.tool_exec.create_artifact(
                    ArtifactCreate(
                        campaign_id=execution.campaign_id,
                        branch_id=execution.branch_id,
                        phase_job_id=execution.phase_job_id,
                        tool_execution_id=execution.id,
                        intention_id=intention_id,
                        artifact_type=ArtifactTypeEnum.RAW_OUTPUT,
                        uri=self._inline_uri(execution, "raw-result"),
                        mime_type="application/json",
                        description=(
                            "Placeholder execution result payload"
                            if placeholder
                            else "Execution result payload"
                        ),
                        policy_class=execution.policy_class,
                        details_json={
                            "inline": True,
                            "placeholder": placeholder,
                            "phase_name": phase_job.phase_name if phase_job else None,
                            "result_payload_json": result_payload_json,
                        },
                    ),
                    actor=actor,
                )
            )

        for label, ref in (("stdout", stdout_ref), ("stderr", stderr_ref)):
            if not ref:
                continue
            created.append(
                await self.tool_exec.create_artifact(
                    ArtifactCreate(
                        campaign_id=execution.campaign_id,
                        branch_id=execution.branch_id,
                        phase_job_id=execution.phase_job_id,
                        tool_execution_id=execution.id,
                        intention_id=intention_id,
                        artifact_type=ArtifactTypeEnum.LOG,
                        uri=ref,
                        mime_type="text/plain",
                        description=f"{label} reference for tool execution",
                        policy_class=execution.policy_class,
                        details_json={"stream": label, "placeholder": placeholder},
                    ),
                    actor=actor,
                )
            )

        return created
