from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.campaign import Observation, SubmissionDraft
from ..models.enums import FindingStatusEnum
from ..models.hil import Evidence, Finding

REVIEWABLE_DRAFT_STATUSES = {"NEEDS_REVIEW", "READY_FOR_REVIEW"}
NON_REVIEWABLE_FINDING_STATUSES = {
    FindingStatusEnum.REJECTED,
    FindingStatusEnum.DUPLICATE,
    FindingStatusEnum.SUBMITTED,
    FindingStatusEnum.RESOLVED,
}


class ReviewQueueService:
    """Query utilities for operator finding review queues."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _draft_candidates(
        self,
        *,
        campaign_id: UUID | None,
        limit: int,
    ) -> list[SubmissionDraft]:
        stmt = (
            select(SubmissionDraft)
            .where(SubmissionDraft.status.in_(list(REVIEWABLE_DRAFT_STATUSES)))
            .order_by(SubmissionDraft.created_at.asc())
            .limit(limit)
        )
        if campaign_id is not None:
            stmt = stmt.where(SubmissionDraft.campaign_id == campaign_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def _finding(self, finding_id: UUID) -> Finding | None:
        result = await self.db.execute(
            select(Finding).where(Finding.id == finding_id, Finding.is_deleted.is_(False))
        )
        return result.scalar_one_or_none()

    async def _evidence_count(self, finding_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count(Evidence.id)).where(
                Evidence.finding_id == finding_id,
                Evidence.is_deleted.is_(False),
            )
        )
        return int(result.scalar() or 0)

    async def _observation_summary(self, finding_id: UUID) -> dict:
        result = await self.db.execute(
            select(Observation)
            .where(Observation.finding_id == finding_id)
            .order_by(Observation.created_at.desc())
            .limit(5)
        )
        observations = result.scalars().all()
        return {
            "count": len(observations),
            "items": [
                {
                    "id": str(obs.id),
                    "category": obs.category,
                    "title": obs.title,
                    "summary": obs.summary,
                }
                for obs in observations
            ],
        }

    async def list_review_queue(
        self,
        *,
        campaign_id: UUID | None = None,
        limit: int = 200,
    ) -> list[dict]:
        queue_items: list[dict] = []
        drafts = await self._draft_candidates(campaign_id=campaign_id, limit=limit)
        for draft in drafts:
            if draft.finding_id is None:
                continue
            finding = await self._finding(draft.finding_id)
            if finding is None:
                continue
            if finding.status in NON_REVIEWABLE_FINDING_STATUSES:
                continue

            queue_items.append(
                {
                    "finding_id": str(finding.id),
                    "draft_id": str(draft.id),
                    "campaign_id": str(draft.campaign_id),
                    "branch_id": str(draft.branch_id) if draft.branch_id else None,
                    "program": finding.program,
                    "asset": finding.asset,
                    "title": finding.title,
                    "finding_status": finding.status.value,
                    "readiness_status": draft.status,
                    "evidence_count": await self._evidence_count(finding.id),
                    "observation_summary": await self._observation_summary(finding.id),
                }
            )
        return queue_items
