"""Analyst validation workflow endpoints for false-positive control."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import ROLE_ADMIN, ROLE_ANALYST, ROLE_OPERATOR, User, require_roles
from ..core.hil_db import get_db
from ..services.finding_override_service import FindingOverrideService
from ..services.validation_queue_manager import ValidationQueueManager

router = APIRouter(
    prefix="/api/v1/validation",
    tags=["validation"],
    dependencies=[Depends(require_roles(ROLE_ANALYST, ROLE_OPERATOR, ROLE_ADMIN))],
)


class FindingReviewRequest(BaseModel):
    decision: str = Field(description="approve | exclude | force_include")
    reason: str = Field(default="", max_length=255)
    notes: str = Field(default="", max_length=4000)


class BatchApproveRequest(BaseModel):
    finding_ids: list[str] = Field(default_factory=list)


@router.get("/queue")
async def get_validation_queue(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_ANALYST, ROLE_OPERATOR, ROLE_ADMIN)),
) -> dict[str, Any]:
    manager = ValidationQueueManager(db)
    return await manager.get_validation_queue(current_user.id)


@router.post("/finding/{finding_id}/review")
async def submit_finding_review(
    finding_id: str,
    body: FindingReviewRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_ANALYST, ROLE_OPERATOR, ROLE_ADMIN)),
) -> dict[str, Any]:
    manager = ValidationQueueManager(db)
    return await manager.submit_analyst_review(
        finding_id=finding_id,
        decision=body.decision,
        reason=body.reason,
        notes=body.notes,
        analyst_id=current_user.id,
    )


@router.post("/batch-approve")
async def batch_approve_findings(
    body: BatchApproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_ANALYST, ROLE_OPERATOR, ROLE_ADMIN)),
) -> dict[str, Any]:
    service = FindingOverrideService(db)
    return await service.batch_approve_findings(body.finding_ids, current_user.id)


@router.get("/stats")
async def get_validation_stats(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(require_roles(ROLE_ANALYST, ROLE_OPERATOR, ROLE_ADMIN)),
) -> dict[str, Any]:
    manager = ValidationQueueManager(db)
    return await manager.get_queue_stats()
