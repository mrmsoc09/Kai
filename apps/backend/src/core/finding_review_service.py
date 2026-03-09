from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.campaign import SubmissionDraft
from ..models.enums import FindingStatusEnum
from ..models.hil import Finding
from .audit_events import record_transition_event


REVIEW_ACTIONS = {
    "APPROVE",
    "REJECT",
    "NEEDS_MORE_EVIDENCE",
    "DUPLICATE",
    "SUPPRESS",
}

DRAFT_STATUS_READY_FOR_SUBMISSION = "READY_FOR_SUBMISSION"
DRAFT_STATUS_NEEDS_REVIEW = "NEEDS_REVIEW"
DRAFT_STATUS_CLOSED = "CLOSED"
DRAFT_STATUS_SUPPRESSED_DUPLICATE = "SUPPRESSED_DUPLICATE"


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
class FindingReviewResult:
    finding_id: UUID
    finding_status: FindingStatusEnum
    draft_id: UUID
    draft_status: str
    campaign_id: UUID
    review_timestamp: datetime


class FindingReviewService:
    """Human review transition service for correlated findings and drafts."""

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

    def _resolve_campaign_id(self, finding: Finding, draft: SubmissionDraft | None) -> UUID:
        if draft is not None:
            return draft.campaign_id
        scope_json = finding.scope_json if isinstance(finding.scope_json, dict) else {}
        campaign_id = _maybe_uuid(scope_json.get("campaign_id"))
        if campaign_id is None:
            raise ValueError(
                "Finding has no campaign context. A SubmissionDraft or scope_json.campaign_id is required."
            )
        return campaign_id

    @staticmethod
    def _initial_review_state(finding_status: FindingStatusEnum) -> None:
        if finding_status in {
            FindingStatusEnum.REJECTED,
            FindingStatusEnum.DUPLICATE,
            FindingStatusEnum.SUBMITTED,
            FindingStatusEnum.RESOLVED,
        }:
            raise ValueError(f"Finding is already terminal: {finding_status.value}")

    @staticmethod
    def _action_mapping(action: str) -> tuple[FindingStatusEnum, str]:
        if action == "APPROVE":
            return FindingStatusEnum.HIL_APPROVED, DRAFT_STATUS_READY_FOR_SUBMISSION
        if action == "REJECT":
            return FindingStatusEnum.REJECTED, DRAFT_STATUS_CLOSED
        if action == "NEEDS_MORE_EVIDENCE":
            return FindingStatusEnum.IN_REVIEW, DRAFT_STATUS_NEEDS_REVIEW
        if action == "DUPLICATE":
            return FindingStatusEnum.DUPLICATE, DRAFT_STATUS_SUPPRESSED_DUPLICATE
        if action == "SUPPRESS":
            return FindingStatusEnum.RESOLVED, DRAFT_STATUS_CLOSED
        raise ValueError(f"Unsupported review action: {action}")

    def _update_review_metadata(
        self,
        *,
        finding: Finding,
        action: str,
        reviewer_id: str,
        review_notes: str | None,
        review_timestamp: datetime,
        duplicate_of_finding_id: UUID | None,
    ) -> None:
        scope_json = finding.scope_json if isinstance(finding.scope_json, dict) else {}
        history = scope_json.get("review_history")
        if not isinstance(history, list):
            history = []
        entry = {
            "action": action,
            "reviewer_id": reviewer_id,
            "review_notes": review_notes,
            "review_timestamp": review_timestamp.isoformat(),
        }
        if duplicate_of_finding_id is not None:
            entry["duplicate_of_finding_id"] = str(duplicate_of_finding_id)
        history.append(entry)
        scope_json["review_history"] = history
        scope_json["last_review"] = entry
        if action == "DUPLICATE" and duplicate_of_finding_id is not None:
            scope_json["duplicate_of_finding_id"] = str(duplicate_of_finding_id)
        if action == "SUPPRESS":
            scope_json["suppressed"] = True
        finding.scope_json = scope_json

    def _upsert_draft_metadata(
        self,
        *,
        draft: SubmissionDraft,
        action: str,
        reviewer_id: str,
        review_notes: str | None,
        review_timestamp: datetime,
    ) -> None:
        details = draft.details_json if isinstance(draft.details_json, dict) else {}
        details["review"] = {
            "action": action,
            "reviewer_id": reviewer_id,
            "review_notes": review_notes,
            "review_timestamp": review_timestamp.isoformat(),
        }
        draft.details_json = details

    async def review_finding(
        self,
        *,
        finding_id: UUID,
        action: str,
        reviewer_id: str,
        review_notes: str | None = None,
        intention_id: UUID | None = None,
        duplicate_of_finding_id: UUID | None = None,
    ) -> FindingReviewResult:
        normalized_action = action.strip().upper()
        if normalized_action not in REVIEW_ACTIONS:
            raise ValueError(f"Unsupported review action: {action}")

        finding = await self._get_finding(finding_id)
        if finding is None:
            raise ValueError(f"Finding not found: {finding_id}")

        draft = await self._latest_draft(finding.id)
        campaign_id = self._resolve_campaign_id(finding, draft)
        branch_id = draft.branch_id if draft is not None else _maybe_uuid(
            (finding.scope_json or {}).get("branch_id") if isinstance(finding.scope_json, dict) else None
        )

        self._initial_review_state(finding.status)
        review_timestamp = _utcnow()

        if finding.status == FindingStatusEnum.NEW:
            finding.status = FindingStatusEnum.IN_REVIEW
            await record_transition_event(
                self.db,
                event_type="finding.review.started",
                actor=reviewer_id,
                message="Reviewer started finding evaluation",
                campaign_id=campaign_id,
                branch_id=branch_id,
                finding_id=finding.id,
                intention_id=intention_id,
                payload={
                    "reviewer_id": reviewer_id,
                    "review_timestamp": review_timestamp.isoformat(),
                },
            )

        target_finding_status, target_draft_status = self._action_mapping(normalized_action)

        if draft is None:
            draft = SubmissionDraft(
                campaign_id=campaign_id,
                branch_id=branch_id,
                finding_id=finding.id,
                intention_id=intention_id,
                status=DRAFT_STATUS_NEEDS_REVIEW,
                title=finding.title,
                prepared_by=reviewer_id,
                details_json={},
            )
            self.db.add(draft)

        finding.status = target_finding_status
        draft.status = target_draft_status
        draft.prepared_by = reviewer_id

        self._update_review_metadata(
            finding=finding,
            action=normalized_action,
            reviewer_id=reviewer_id,
            review_notes=review_notes,
            review_timestamp=review_timestamp,
            duplicate_of_finding_id=duplicate_of_finding_id,
        )
        self._upsert_draft_metadata(
            draft=draft,
            action=normalized_action,
            reviewer_id=reviewer_id,
            review_notes=review_notes,
            review_timestamp=review_timestamp,
        )
        await self.db.flush()

        await record_transition_event(
            self.db,
            event_type="finding.review.action",
            actor=reviewer_id,
            message=f"Review action {normalized_action} applied to finding",
            campaign_id=campaign_id,
            branch_id=branch_id,
            finding_id=finding.id,
            intention_id=intention_id,
            payload={
                "action": normalized_action,
                "reviewer_id": reviewer_id,
                "review_notes": review_notes,
                "review_timestamp": review_timestamp.isoformat(),
                "finding_status": finding.status.value,
                "draft_status": draft.status,
                "duplicate_of_finding_id": str(duplicate_of_finding_id)
                if duplicate_of_finding_id
                else None,
            },
        )

        return FindingReviewResult(
            finding_id=finding.id,
            finding_status=finding.status,
            draft_id=draft.id,
            draft_status=draft.status,
            campaign_id=campaign_id,
            review_timestamp=review_timestamp,
        )
