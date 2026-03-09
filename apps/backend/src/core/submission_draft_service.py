from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.campaign import Observation, SubmissionDraft
from ..models.hil import Finding
from .audit_events import record_transition_event
from .evidence_service import EvidenceService


DRAFT_STATUS_NEEDS_REVIEW = "NEEDS_REVIEW"
DRAFT_STATUS_READY_FOR_REVIEW = "READY_FOR_REVIEW"
DRAFT_STATUS_INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
DRAFT_STATUS_SUPPRESSED_DUPLICATE = "SUPPRESSED_DUPLICATE"


class SubmissionDraftService:
    """Conservative draft preparation based on finding evidence/readiness."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.evidence = EvidenceService(db)

    async def _latest_draft(self, finding_id: UUID) -> SubmissionDraft | None:
        result = await self.db.execute(
            select(SubmissionDraft)
            .where(SubmissionDraft.finding_id == finding_id)
            .order_by(SubmissionDraft.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _has_validation_observation(self, finding_id: UUID) -> bool:
        result = await self.db.execute(
            select(Observation)
            .where(Observation.finding_id == finding_id)
            .order_by(Observation.created_at.asc())
        )
        for observation in result.scalars().all():
            category = (observation.category or "").strip().upper()
            obs_type = (
                observation.observation_type.value
                if observation.observation_type is not None
                else ""
            ).upper()
            if category == "VALIDATION" or obs_type == "VALIDATION":
                return True
        return False

    @staticmethod
    def _is_duplicate_finding(finding: Finding) -> bool:
        scope_json = finding.scope_json if isinstance(finding.scope_json, dict) else {}
        return bool(scope_json.get("duplicate_of_finding_id") or scope_json.get("is_duplicate"))

    async def determine_status(
        self,
        *,
        finding: Finding,
        duplicate_detected: bool = False,
    ) -> tuple[str, dict[str, Any]]:
        evidence_rows = await self.evidence.list_finding_evidence(finding.id)
        has_validation = await self._has_validation_observation(finding.id)
        duplicate = duplicate_detected or self._is_duplicate_finding(finding)

        if duplicate:
            status = DRAFT_STATUS_SUPPRESSED_DUPLICATE
        elif not evidence_rows:
            status = DRAFT_STATUS_INSUFFICIENT_EVIDENCE
        elif has_validation:
            status = DRAFT_STATUS_READY_FOR_REVIEW
        else:
            status = DRAFT_STATUS_NEEDS_REVIEW

        details = {
            "evidence_count": len(evidence_rows),
            "has_validation_observation": has_validation,
            "duplicate": duplicate,
        }
        return status, details

    async def upsert_draft_for_finding(
        self,
        *,
        finding: Finding,
        campaign_id: UUID,
        branch_id: UUID | None,
        intention_id: UUID | None,
        actor: str | None,
        duplicate_detected: bool = False,
    ) -> SubmissionDraft:
        status, details = await self.determine_status(
            finding=finding,
            duplicate_detected=duplicate_detected,
        )
        draft = await self._latest_draft(finding.id)
        if draft is None:
            draft = SubmissionDraft(
                campaign_id=campaign_id,
                branch_id=branch_id,
                finding_id=finding.id,
                intention_id=intention_id,
                status=status,
                title=finding.title,
                prepared_by=actor,
                details_json=details,
            )
            self.db.add(draft)
        else:
            draft.status = status
            draft.title = draft.title or finding.title
            draft.prepared_by = actor or draft.prepared_by
            merged = draft.details_json if isinstance(draft.details_json, dict) else {}
            merged.update(details)
            draft.details_json = merged
        await self.db.flush()

        await record_transition_event(
            self.db,
            event_type="submission_draft.upserted",
            actor=actor,
            message=f"Submission draft status evaluated as {status}",
            campaign_id=campaign_id,
            branch_id=branch_id,
            finding_id=finding.id,
            intention_id=intention_id,
            payload={
                "submission_draft_id": str(draft.id),
                "status": status,
                **details,
            },
        )
        return draft
