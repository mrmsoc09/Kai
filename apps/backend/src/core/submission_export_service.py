from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.campaign import Artifact, Observation, SubmissionDraft
from ..models.enums import FindingStatusEnum
from ..models.hil import Evidence, Finding
from .audit_events import record_transition_event
from .submission_adapters import (
    BugcrowdSubmissionAdapter,
    HackerOneSubmissionAdapter,
    IntigritiSubmissionAdapter,
    ProviderPayloadResult,
    SubmissionExportContext,
    SubmissionProviderAdapter,
)

READY_DRAFT_STATUS = "READY_FOR_SUBMISSION"
SUPPORTED_PROVIDERS = ("hackerone", "bugcrowd", "intigriti")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _maybe_uuid(raw: Any) -> UUID | None:
    if raw is None:
        return None
    if isinstance(raw, UUID):
        return raw
    if isinstance(raw, str):
        try:
            return UUID(raw)
        except ValueError:
            return None
    return None


@dataclass
class SubmissionExportResult:
    provider: str
    finding_id: UUID
    submission_draft_id: UUID
    ready: bool
    state: str
    missing_fields: list[str]
    warnings: list[str]
    payload: dict[str, Any]
    stored: bool
    exported_at: datetime | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "finding_id": str(self.finding_id),
            "submission_draft_id": str(self.submission_draft_id),
            "ready": self.ready,
            "state": self.state,
            "missing_fields": self.missing_fields,
            "warnings": self.warnings,
            "payload": self.payload,
            "stored": self.stored,
            "exported_at": self.exported_at.isoformat() if self.exported_at else None,
        }


class SubmissionExportService:
    """Provider-specific deterministic payload preview/export for approved findings."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._adapters: dict[str, SubmissionProviderAdapter] = {
            "hackerone": HackerOneSubmissionAdapter(),
            "bugcrowd": BugcrowdSubmissionAdapter(),
            "intigriti": IntigritiSubmissionAdapter(),
        }

    def _adapter(self, provider: str) -> SubmissionProviderAdapter:
        normalized = provider.strip().lower()
        adapter = self._adapters.get(normalized)
        if adapter is None:
            raise ValueError(
                f"Unsupported provider '{provider}'. Supported providers: {', '.join(SUPPORTED_PROVIDERS)}"
            )
        return adapter

    async def _finding(self, finding_id: UUID) -> Finding | None:
        result = await self.db.execute(
            select(Finding).where(Finding.id == finding_id, Finding.is_deleted.is_(False))
        )
        return result.scalar_one_or_none()

    async def _latest_draft_for_finding(self, finding_id: UUID) -> SubmissionDraft | None:
        result = await self.db.execute(
            select(SubmissionDraft)
            .where(SubmissionDraft.finding_id == finding_id)
            .order_by(SubmissionDraft.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _draft_by_id(self, draft_id: UUID) -> SubmissionDraft | None:
        result = await self.db.execute(
            select(SubmissionDraft).where(SubmissionDraft.id == draft_id)
        )
        return result.scalar_one_or_none()

    async def _finding_evidence(self, finding_id: UUID) -> list[Evidence]:
        result = await self.db.execute(
            select(Evidence)
            .where(Evidence.finding_id == finding_id, Evidence.is_deleted.is_(False))
            .order_by(Evidence.created_at.asc())
        )
        return list(result.scalars().all())

    async def _finding_artifacts(self, finding_id: UUID) -> list[Artifact]:
        result = await self.db.execute(
            select(Artifact)
            .where(Artifact.finding_id == finding_id)
            .order_by(Artifact.created_at.asc())
        )
        return list(result.scalars().all())

    async def _finding_observations(self, finding_id: UUID) -> list[Observation]:
        result = await self.db.execute(
            select(Observation)
            .where(Observation.finding_id == finding_id)
            .order_by(Observation.created_at.asc())
        )
        return list(result.scalars().all())

    async def _resolve_finding_draft(
        self,
        *,
        finding_id: UUID | None,
        submission_draft_id: UUID | None,
    ) -> tuple[Finding, SubmissionDraft]:
        finding: Finding | None = None
        draft: SubmissionDraft | None = None

        if submission_draft_id is not None:
            draft = await self._draft_by_id(submission_draft_id)
            if draft is None:
                raise ValueError(f"SubmissionDraft not found: {submission_draft_id}")
            if draft.finding_id is None:
                raise ValueError(f"SubmissionDraft {submission_draft_id} has no finding linkage")

        target_finding_id = finding_id or (draft.finding_id if draft else None)
        if target_finding_id is None:
            raise ValueError("Either finding_id or submission_draft_id is required")

        finding = await self._finding(target_finding_id)
        if finding is None:
            raise ValueError(f"Finding not found: {target_finding_id}")

        if draft is None:
            draft = await self._latest_draft_for_finding(finding.id)
            if draft is None:
                raise ValueError(
                    f"No SubmissionDraft found for finding {finding.id}. "
                    "Prepare submission package before provider export."
                )

        if draft.finding_id != finding.id:
            raise ValueError(
                f"Draft {draft.id} is linked to finding {draft.finding_id}, "
                f"not requested finding {finding.id}"
            )
        return finding, draft

    def _core_readiness_checks(
        self,
        *,
        finding: Finding,
        draft: SubmissionDraft,
        package_json: dict[str, Any],
        evidence_rows: list[Evidence],
        artifacts: list[Artifact],
    ) -> tuple[list[str], list[str]]:
        missing_fields: list[str] = []
        warnings: list[str] = []
        if finding.status != FindingStatusEnum.HIL_APPROVED:
            missing_fields.append("finding.status:HIL_APPROVED")
        if draft.status != READY_DRAFT_STATUS:
            missing_fields.append(f"submission_draft.status:{READY_DRAFT_STATUS}")
        if not package_json:
            missing_fields.append("submission_draft.details_json.package_json")
        if len(evidence_rows) == 0:
            missing_fields.append("finding.evidence")
        if len(artifacts) == 0:
            warnings.append("no_artifacts_linked")
        synthetic_count = 0
        for row in evidence_rows:
            if isinstance(row.meta, dict) and row.meta.get("synthetic"):
                synthetic_count += 1
        if synthetic_count > 0:
            warnings.append(f"synthetic_evidence_count:{synthetic_count}")
        return missing_fields, warnings

    def _payload_hash(self, payload: dict[str, Any]) -> str:
        serialized = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

    def _resolve_intention_id(
        self,
        *,
        explicit_intention_id: UUID | None,
        draft: SubmissionDraft,
        finding: Finding,
    ) -> UUID | None:
        if explicit_intention_id is not None:
            return explicit_intention_id
        if draft.intention_id is not None:
            return draft.intention_id
        scope_json = finding.scope_json if isinstance(finding.scope_json, dict) else {}
        return _maybe_uuid(scope_json.get("intention_id"))

    async def _build(
        self,
        *,
        provider: str,
        finding_id: UUID | None,
        submission_draft_id: UUID | None,
        actor: str | None,
    ) -> tuple[ProviderPayloadResult, Finding, SubmissionDraft, UUID | None]:
        adapter = self._adapter(provider)
        finding, draft = await self._resolve_finding_draft(
            finding_id=finding_id,
            submission_draft_id=submission_draft_id,
        )
        details = draft.details_json if isinstance(draft.details_json, dict) else {}
        package_json = (
            details.get("package_json") if isinstance(details.get("package_json"), dict) else {}
        )
        evidence_rows = await self._finding_evidence(finding.id)
        artifacts = await self._finding_artifacts(finding.id)
        observations = await self._finding_observations(finding.id)
        core_missing_fields, core_warnings = self._core_readiness_checks(
            finding=finding,
            draft=draft,
            package_json=package_json,
            evidence_rows=evidence_rows,
            artifacts=artifacts,
        )

        context = SubmissionExportContext(
            provider=adapter.provider,
            finding=finding,
            submission_draft=draft,
            package_json=package_json,
            evidence_rows=evidence_rows,
            artifacts=artifacts,
            observations=observations,
            actor=actor,
        )
        payload_result = adapter.preview(
            context,
            core_missing_fields=core_missing_fields,
            core_warnings=core_warnings,
        )
        intention_id = self._resolve_intention_id(
            explicit_intention_id=None,
            draft=draft,
            finding=finding,
        )
        return payload_result, finding, draft, intention_id

    async def preview_payload(
        self,
        *,
        provider: str,
        finding_id: UUID | None = None,
        submission_draft_id: UUID | None = None,
        actor: str | None = None,
        intention_id: UUID | None = None,
    ) -> SubmissionExportResult:
        payload_result, finding, draft, resolved_intention = await self._build(
            provider=provider,
            finding_id=finding_id,
            submission_draft_id=submission_draft_id,
            actor=actor,
        )
        resolved_intention = intention_id or resolved_intention
        payload_hash = self._payload_hash(payload_result.payload)

        await record_transition_event(
            self.db,
            event_type="submission_export.previewed",
            actor=actor,
            message=f"Provider payload preview generated for {payload_result.provider}",
            campaign_id=draft.campaign_id,
            branch_id=draft.branch_id,
            finding_id=finding.id,
            draft_id=draft.id,
            intention_id=resolved_intention,
            action="preview_submission_export",
            outcome=payload_result.validation.state,
            dedupe_key=f"{finding.id}:{draft.id}:{payload_result.provider}:{payload_hash}:preview",
            payload={
                "provider": payload_result.provider,
                "ready": payload_result.validation.ready,
                "state": payload_result.validation.state,
                "missing_fields": payload_result.validation.missing_fields,
                "warnings": payload_result.validation.warnings,
                "payload_hash": payload_hash,
            },
        )
        return SubmissionExportResult(
            provider=payload_result.provider,
            finding_id=finding.id,
            submission_draft_id=draft.id,
            ready=payload_result.validation.ready,
            state=payload_result.validation.state,
            missing_fields=payload_result.validation.missing_fields,
            warnings=payload_result.validation.warnings,
            payload=payload_result.payload,
            stored=False,
        )

    async def export_payload(
        self,
        *,
        provider: str,
        finding_id: UUID | None = None,
        submission_draft_id: UUID | None = None,
        actor: str | None = None,
        intention_id: UUID | None = None,
    ) -> SubmissionExportResult:
        payload_result, finding, draft, resolved_intention = await self._build(
            provider=provider,
            finding_id=finding_id,
            submission_draft_id=submission_draft_id,
            actor=actor,
        )
        resolved_intention = intention_id or resolved_intention
        exported_at = _utcnow()
        payload_hash = self._payload_hash(payload_result.payload)

        details = draft.details_json if isinstance(draft.details_json, dict) else {}
        provider_exports = details.get("provider_exports")
        if not isinstance(provider_exports, dict):
            provider_exports = {}
        export_history = provider_exports.get(payload_result.provider)
        if not isinstance(export_history, list):
            export_history = []

        export_record = {
            "mode": "export",
            "provider": payload_result.provider,
            "ready": payload_result.validation.ready,
            "state": payload_result.validation.state,
            "missing_fields": payload_result.validation.missing_fields,
            "warnings": payload_result.validation.warnings,
            "payload_hash": payload_hash,
            "payload": payload_result.payload,
            "exported_at": exported_at.isoformat(),
            "actor": actor,
        }
        export_history.append(export_record)
        provider_exports[payload_result.provider] = export_history
        details["provider_exports"] = provider_exports
        details["latest_provider_export"] = {
            "provider": payload_result.provider,
            "ready": payload_result.validation.ready,
            "state": payload_result.validation.state,
            "payload_hash": payload_hash,
            "exported_at": exported_at.isoformat(),
            "actor": actor,
        }
        draft.details_json = details
        await self.db.flush()

        await record_transition_event(
            self.db,
            event_type=(
                "submission_export.staged"
                if payload_result.validation.ready
                else "submission_export.validation_failed"
            ),
            actor=actor,
            message=(
                f"Provider payload staged for {payload_result.provider}"
                if payload_result.validation.ready
                else f"Provider payload not ready for {payload_result.provider}"
            ),
            campaign_id=draft.campaign_id,
            branch_id=draft.branch_id,
            finding_id=finding.id,
            draft_id=draft.id,
            intention_id=resolved_intention,
            action="export_submission_payload",
            outcome=payload_result.validation.state,
            dedupe_key=f"{finding.id}:{draft.id}:{payload_result.provider}:{payload_hash}:export",
            payload={
                "provider": payload_result.provider,
                "ready": payload_result.validation.ready,
                "state": payload_result.validation.state,
                "missing_fields": payload_result.validation.missing_fields,
                "warnings": payload_result.validation.warnings,
                "payload_hash": payload_hash,
            },
        )

        return SubmissionExportResult(
            provider=payload_result.provider,
            finding_id=finding.id,
            submission_draft_id=draft.id,
            ready=payload_result.validation.ready,
            state=payload_result.validation.state,
            missing_fields=payload_result.validation.missing_fields,
            warnings=payload_result.validation.warnings,
            payload=payload_result.payload,
            stored=True,
            exported_at=exported_at,
        )
