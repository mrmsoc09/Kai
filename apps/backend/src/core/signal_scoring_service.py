from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.signal_score import SignalScore

logger = logging.getLogger(__name__)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


class SignalScoringService:
    """Compute and persist signal scores for findings/campaigns.

    Formula:
        overall_priority = (exploitability/10 + impact/10 + evidence_completeness + novelty) / 4 * 10
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    def compute_overall_priority(
        self,
        exploitability: float,
        impact: float,
        evidence_completeness: float,
        novelty: float,
    ) -> float:
        """Return overall_priority in [0.0, 10.0]."""
        raw = (
            _clamp(exploitability, 0.0, 10.0) / 10.0
            + _clamp(impact, 0.0, 10.0) / 10.0
            + _clamp(evidence_completeness, 0.0, 1.0)
            + _clamp(novelty, 0.0, 1.0)
        ) / 4.0 * 10.0
        return round(_clamp(raw, 0.0, 10.0), 4)

    async def compute_signal_score(
        self,
        exploitability: float,
        impact: float,
        evidence_completeness: float,
        novelty: float,
        rationale: str | None,
        scored_by: str,
        campaign_id: UUID | None = None,
        finding_id: UUID | None = None,
    ) -> SignalScore:
        """Create, persist, and return a new SignalScore record."""
        overall = self.compute_overall_priority(
            exploitability, impact, evidence_completeness, novelty
        )
        record = SignalScore(
            campaign_id=campaign_id,
            finding_id=finding_id,
            exploitability_score=_clamp(exploitability, 0.0, 10.0),
            impact_score=_clamp(impact, 0.0, 10.0),
            evidence_completeness=_clamp(evidence_completeness, 0.0, 1.0),
            novelty_score=_clamp(novelty, 0.0, 1.0),
            overall_priority=overall,
            score_rationale=rationale,
            scored_at=datetime.now(timezone.utc),
            scored_by=scored_by,
        )
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        logger.info(
            "signal_score.created id=%s overall_priority=%.4f campaign_id=%s finding_id=%s",
            record.id,
            overall,
            campaign_id,
            finding_id,
        )
        return record

    async def get_scores_for_campaign(
        self, campaign_id: UUID, tenant_id: str | None = None
    ) -> list[SignalScore]:
        stmt = (
            select(SignalScore)
            .where(SignalScore.campaign_id == campaign_id)
            .order_by(SignalScore.scored_at.desc())
        )
        if tenant_id:
            stmt = stmt.where(SignalScore.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
