from __future__ import annotations

from typing import Iterable

from sqlalchemy import select
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

    async def _existing_for_dedupe(
        self,
        *,
        execution_id,
        artifact_type: ArtifactTypeEnum,
        uri: str,
        dedupe_key: str,
        ingestion_fingerprint: str | None,
    ) -> Artifact | None:
        try:
            result = await self.db.execute(
                select(Artifact)
                .where(
                    Artifact.tool_execution_id == execution_id,
                    Artifact.artifact_type == artifact_type,
                    Artifact.uri == uri,
                )
                .order_by(Artifact.created_at.desc())
                .limit(10)
            )
            for artifact in result.scalars().all():
                details = artifact.details_json if isinstance(artifact.details_json, dict) else {}
                if details.get("dedupe_key") != dedupe_key:
                    continue
                if ingestion_fingerprint is None:
                    return artifact
                if details.get("ingestion_fingerprint") == ingestion_fingerprint:
                    return artifact
        except Exception:
            return None
        return None

    async def _create_or_reuse_artifact(
        self,
        *,
        execution: ToolExecution,
        artifact_type: ArtifactTypeEnum,
        uri: str,
        intention_id,
        actor: str | None,
        dedupe_key: str,
        ingestion_fingerprint: str | None,
        content_hash: str | None = None,
        mime_type: str | None = None,
        size_bytes: int | None = None,
        description: str | None = None,
        details_json: dict | None = None,
    ) -> Artifact:
        existing = await self._existing_for_dedupe(
            execution_id=execution.id,
            artifact_type=artifact_type,
            uri=uri,
            dedupe_key=dedupe_key,
            ingestion_fingerprint=ingestion_fingerprint,
        )
        if existing is not None:
            return existing

        details = dict(details_json) if isinstance(details_json, dict) else {}
        details.setdefault("dedupe_key", dedupe_key)
        if ingestion_fingerprint is not None:
            details.setdefault("ingestion_fingerprint", ingestion_fingerprint)

        return await self.tool_exec.create_artifact(
            ArtifactCreate(
                campaign_id=execution.campaign_id,
                branch_id=execution.branch_id,
                phase_job_id=execution.phase_job_id,
                tool_execution_id=execution.id,
                intention_id=intention_id,
                artifact_type=artifact_type,
                uri=uri,
                content_hash=content_hash,
                mime_type=mime_type,
                size_bytes=size_bytes,
                description=description,
                policy_class=execution.policy_class,
                details_json=details,
            ),
            actor=actor,
        )

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
        ingestion_fingerprint: str | None = None,
    ) -> list[Artifact]:
        created: list[Artifact] = []

        for index, item in enumerate(explicit_artifacts):
            uri = item.uri or self._inline_uri(execution, item.artifact_type.value.lower())
            created.append(
                await self._create_or_reuse_artifact(
                    execution=execution,
                    artifact_type=item.artifact_type,
                    uri=uri,
                    intention_id=intention_id,
                    actor=actor,
                    dedupe_key=f"explicit:{index}:{item.artifact_type.value}:{uri}",
                    ingestion_fingerprint=ingestion_fingerprint,
                    content_hash=item.content_hash,
                    mime_type=item.mime_type,
                    size_bytes=item.size_bytes,
                    description=item.description,
                    details_json=item.details_json,
                )
            )

        if result_payload_json:
            created.append(
                await self._create_or_reuse_artifact(
                    execution=execution,
                    artifact_type=ArtifactTypeEnum.RAW_OUTPUT,
                    uri=self._inline_uri(execution, "raw-result"),
                    intention_id=intention_id,
                    actor=actor,
                    dedupe_key="auto:raw-result",
                    ingestion_fingerprint=ingestion_fingerprint,
                    mime_type="application/json",
                    description=(
                        "Placeholder execution result payload"
                        if placeholder
                        else "Execution result payload"
                    ),
                    details_json={
                        "inline": True,
                        "placeholder": placeholder,
                        "phase_name": phase_job.phase_name if phase_job else None,
                        "result_payload_json": result_payload_json,
                    },
                )
            )

        for label, ref in (("stdout", stdout_ref), ("stderr", stderr_ref)):
            if not ref:
                continue
            created.append(
                await self._create_or_reuse_artifact(
                    execution=execution,
                    artifact_type=ArtifactTypeEnum.LOG,
                    uri=ref,
                    intention_id=intention_id,
                    actor=actor,
                    dedupe_key=f"auto:log:{label}:{ref}",
                    ingestion_fingerprint=ingestion_fingerprint,
                    mime_type="text/plain",
                    description=f"{label} reference for tool execution",
                    details_json={"stream": label, "placeholder": placeholder},
                )
            )

        return created
