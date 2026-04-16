from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import ROLE_ADMIN, ROLE_ANALYST, ROLE_OPERATOR, User, require_roles
from ..core.hil_db import get_db
from ..core.signal_scoring_service import SignalScoringService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/signal-scores", tags=["signal-scores"])


class SignalScoreCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    campaign_id: UUID | None = None
    finding_id: UUID | None = None
    exploitability_score: float = Field(..., ge=0.0, le=10.0)
    impact_score: float = Field(..., ge=0.0, le=10.0)
    evidence_completeness: float = Field(..., ge=0.0, le=1.0)
    novelty_score: float = Field(..., ge=0.0, le=1.0)
    score_rationale: str | None = Field(default=None, max_length=8000)
    scored_by: str = Field(..., min_length=1, max_length=255)


class SignalScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID | None = None
    finding_id: UUID | None = None
    exploitability_score: float
    impact_score: float
    evidence_completeness: float
    novelty_score: float
    overall_priority: float
    score_rationale: str | None = None
    scored_at: datetime
    scored_by: str


@router.post("/", response_model=SignalScoreRead, status_code=201)
async def create_signal_score(
    body: SignalScoreCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
) -> SignalScoreRead:
    if body.campaign_id is None and body.finding_id is None:
        raise HTTPException(
            status_code=422,
            detail="At least one of campaign_id or finding_id must be provided",
        )
    svc = SignalScoringService(db)
    record = await svc.compute_signal_score(
        exploitability=body.exploitability_score,
        impact=body.impact_score,
        evidence_completeness=body.evidence_completeness,
        novelty=body.novelty_score,
        rationale=body.score_rationale,
        scored_by=body.scored_by,
        campaign_id=body.campaign_id,
        finding_id=body.finding_id,
    )
    return SignalScoreRead.model_validate(record)


@router.get("/", response_model=list[SignalScoreRead])
async def list_signal_scores(
    campaign_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
) -> list[SignalScoreRead]:
    if campaign_id is None:
        raise HTTPException(
            status_code=422,
            detail="campaign_id query parameter is required",
        )
    svc = SignalScoringService(db)
    records = await svc.get_scores_for_campaign(
        campaign_id, tenant_id=current_user.tenant_id
    )
    return [SignalScoreRead.model_validate(r) for r in records]
