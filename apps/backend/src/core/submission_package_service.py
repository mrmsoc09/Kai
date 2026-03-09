from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.campaign import Artifact, Observation, SubmissionDraft
from ..models.enums import FindingStatusEnum
from ..models.hil import Evidence, Finding
from .audit_events import record_transition_event


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _maybe_uuid(raw) -> UUID | None:
    if isinstance(raw, UUID):
        return raw
    if isinstance(raw, str):
        try:
            return UUID(raw)
        except ValueError:
            return None
    return None


@dataclass
class SubmissionPackageResult:
    finding_id: UUID
    draft_id: UUID
    draft_status: str
    package_json: dict


class SubmissionPackageService:
    """Prepare deterministic submission package JSON from finding evidence context."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_finding(self, finding_id: UUID) -> Finding | None:
        result = await self.db.execute(
            select(Finding).where(Finding.id == finding_id, Finding.is_deleted.is_(False))
        )
        return result.scalar_one_or_none()

    async def _latest_draft(self, finding_id: UUID) -> SubmissionDraft | None:
        result = await self.db.execute(
            select(SubmissionDraft)
            .where(SubmissionDraft.finding_id == finding_id)
            .order_by(SubmissionDraft.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _evidence_rows(self, finding_id: UUID) -> list[Evidence]:
        result = await self.db.execute(
            select(Evidence)
            .where(Evidence.finding_id == finding_id, Evidence.is_deleted.is_(False))
            .order_by(Evidence.created_at.asc())
        )
        return list(result.scalars().all())

    async def _observation_rows(self, finding_id: UUID) -> list[Observation]:
        result = await self.db.execute(
            select(Observation)
            .where(Observation.finding_id == finding_id)
            .order_by(Observation.created_at.asc())
        )
        return list(result.scalars().all())

    async def _artifact_rows(self, finding_id: UUID, observations: list[Observation]) -> list[Artifact]:
        artifacts: dict[UUID, Artifact] = {}

        finding_result = await self.db.execute(
            select(Artifact)
            .where(Artifact.finding_id == finding_id)
            .order_by(Artifact.created_at.asc())
        )
        for artifact in finding_result.scalars().all():
            artifacts[artifact.id] = artifact

        for observation in observations:
            if observation.source_artifact_id is None:
                continue
            source_result = await self.db.execute(
                select(Artifact).where(Artifact.id == observation.source_artifact_id)
            )
            source = source_result.scalar_one_or_none()
            if source is not None:
                artifacts[source.id] = source

        return list(artifacts.values())

    def _campaign_context(
        self,
        *,
        finding: Finding,
        draft: SubmissionDraft,
        observations: list[Observation],
    ) -> dict:
        scope_json = finding.scope_json if isinstance(finding.scope_json, dict) else {}
        first_observation = observations[0] if observations else None
        return {
            "campaign_id": str(draft.campaign_id),
            "branch_id": str(draft.branch_id) if draft.branch_id else None,
            "phase_job_id": str(scope_json.get("phase_job_id"))
            if scope_json.get("phase_job_id")
            else str(first_observation.phase_job_id)
            if first_observation and first_observation.phase_job_id
            else None,
            "tool_execution_id": str(scope_json.get("tool_execution_id"))
            if scope_json.get("tool_execution_id")
            else str(first_observation.tool_execution_id)
            if first_observation and first_observation.tool_execution_id
            else None,
        }

    async def _get_or_create_draft(
        self,
        *,
        finding: Finding,
        prepared_by: str,
        intention_id: UUID | None,
    ) -> SubmissionDraft:
        draft = await self._latest_draft(finding.id)
        if draft is not None:
            return draft
        scope_json = finding.scope_json if isinstance(finding.scope_json, dict) else {}
        campaign_id = _maybe_uuid(scope_json.get("campaign_id"))
        if campaign_id is None:
            raise ValueError("Cannot create submission draft without campaign_id context")
        branch_id = _maybe_uuid(scope_json.get("branch_id"))
        draft = SubmissionDraft(
            campaign_id=campaign_id,
            branch_id=branch_id,
            finding_id=finding.id,
            intention_id=intention_id,
            status="NEEDS_REVIEW",
            title=finding.title,
            prepared_by=prepared_by,
            details_json={},
        )
        self.db.add(draft)
        await self.db.flush()
        return draft

    async def prepare_submission_package(
        self,
        *,
        finding_id: UUID,
        prepared_by: str,
        intention_id: UUID | None = None,
    ) -> SubmissionPackageResult:
        finding = await self._get_finding(finding_id)
        if finding is None:
            raise ValueError(f"Finding not found: {finding_id}")
        if finding.status in {
            FindingStatusEnum.REJECTED,
            FindingStatusEnum.DUPLICATE,
            FindingStatusEnum.RESOLVED,
        }:
            raise ValueError(f"Finding status {finding.status.value} is not package-eligible")
        if finding.status != FindingStatusEnum.HIL_APPROVED:
            raise ValueError(
                "Finding must be approved before package preparation (expected HIL_APPROVED status)"
            )

        draft = await self._get_or_create_draft(
            finding=finding,
            prepared_by=prepared_by,
            intention_id=intention_id,
        )
        evidence_rows = await self._evidence_rows(finding.id)
        observations = await self._observation_rows(finding.id)
        artifacts = await self._artifact_rows(finding.id, observations)

        package_json = {
            "finding": {
                "id": str(finding.id),
                "program": finding.program,
                "asset": finding.asset,
                "title": finding.title,
                "description": finding.description,
                "severity": finding.severity.value,
                "status": finding.status.value,
            },
            "campaign_context": self._campaign_context(
                finding=finding,
                draft=draft,
                observations=observations,
            ),
            "evidence": [
                {
                    "id": str(evidence.id),
                    "kind": evidence.kind,
                    "uri": evidence.uri,
                    "sha256_hex": evidence.sha256.hex(),
                    "synthetic": bool(
                        evidence.meta.get("synthetic")
                        if isinstance(evidence.meta, dict)
                        else False
                    ),
                    "meta": evidence.meta,
                }
                for evidence in evidence_rows
            ],
            "artifacts": [
                {
                    "id": str(artifact.id),
                    "uri": artifact.uri,
                    "artifact_type": artifact.artifact_type.value if artifact.artifact_type else None,
                    "mime_type": artifact.mime_type,
                    "content_hash": artifact.content_hash,
                    "size_bytes": artifact.size_bytes,
                    "synthetic": bool(
                        (artifact.uri or "").startswith("inline://")
                        or (
                            isinstance(artifact.details_json, dict)
                            and (
                                artifact.details_json.get("inline")
                                or artifact.details_json.get("placeholder")
                                or artifact.details_json.get("synthetic")
                            )
                        )
                    ),
                    "tool_execution_id": str(artifact.tool_execution_id)
                    if artifact.tool_execution_id
                    else None,
                    "phase_job_id": str(artifact.phase_job_id) if artifact.phase_job_id else None,
                }
                for artifact in artifacts
            ],
            "observations": [
                {
                    "id": str(observation.id),
                    "type": observation.observation_type.value
                    if observation.observation_type
                    else None,
                    "category": observation.category,
                    "title": observation.title,
                    "summary": observation.summary,
                    "confidence": observation.confidence,
                }
                for observation in observations
            ],
            "reproduction_notes": [
                observation.summary
                for observation in observations
                if (
                    (observation.category or "").upper() == "VALIDATION"
                    and observation.summary
                )
            ],
            "prepared_by": prepared_by,
            "prepared_at": _utcnow().isoformat(),
        }

        package_hash = hashlib.sha256(
            json.dumps(package_json, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        details = draft.details_json if isinstance(draft.details_json, dict) else {}
        details["package_json"] = package_json
        details["package_hash"] = package_hash
        draft.details_json = details
        draft.prepared_by = prepared_by
        draft.content_uri = f"inline://submission-draft/{draft.id}/package"
        draft.content_hash = package_hash
        draft.status = "READY_FOR_SUBMISSION"
        await self.db.flush()

        await record_transition_event(
            self.db,
            event_type="submission_package.prepared",
            actor=prepared_by,
            message="Submission package prepared for approved finding",
            campaign_id=draft.campaign_id,
            branch_id=draft.branch_id,
            finding_id=finding.id,
            intention_id=intention_id,
            payload={
                "submission_draft_id": str(draft.id),
                "status": draft.status,
                "evidence_count": len(evidence_rows),
                "artifact_count": len(artifacts),
                "observation_count": len(observations),
                "package_hash": package_hash,
            },
        )

        return SubmissionPackageResult(
            finding_id=finding.id,
            draft_id=draft.id,
            draft_status=draft.status,
            package_json=package_json,
        )
