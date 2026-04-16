from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import ROLE_ADMIN, ROLE_ANALYST, ROLE_OPERATOR, User, require_roles
from ..core.hil_db import get_db
from ..core.evidence_lifecycle_service import EvidenceLifecycleService
from ..models.structured_evidence import StructuredEvidence
from ..schemas.evidence import (
    EvidenceReadinessReport,
    LifecycleAdvanceRequest,
    ReplayFieldsPatch,
)

logger = logging.getLogger(__name__)

# Prefix is /evidence/structured — safe as long as /evidence router has no parameterized catch-all routes.
router = APIRouter(prefix="/evidence/structured", tags=["structured-evidence"])

VALID_EVIDENCE_TYPES = {
    "screenshot",
    "http_trace",
    "log_excerpt",
    "scan_output",
    "manual_note",
}

VALID_VALIDATION_STATUSES = {"PENDING", "CONFIRMED", "REJECTED"}


class StructuredEvidenceCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    campaign_id: UUID | None = None
    finding_id: UUID | None = None
    evidence_type: str = Field(..., min_length=1, max_length=255)
    source_phase: str | None = Field(default=None, max_length=255)
    collected_at: datetime | None = None
    collected_by: str = Field(..., min_length=1, max_length=255)
    artifact_uri: str | None = Field(default=None, max_length=4096)
    summary: str | None = Field(default=None, max_length=8000)
    validation_status: str = Field(default="PENDING", max_length=50)


class StructuredEvidenceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    campaign_id: UUID | None = None
    finding_id: UUID | None = None
    evidence_type: str
    source_phase: str | None = None
    collected_at: datetime
    collected_by: str
    artifact_uri: str | None = None
    summary: str | None = None
    validation_status: str
    # Phase 2 lifecycle fields
    lifecycle_status: str = "COLLECTED"
    lifecycle_transitioned_at: datetime | None = None
    lifecycle_actor: str | None = None
    # Phase 2 replay fields
    replay_request_response_uri: str | None = None
    replay_command_transcript_uri: str | None = None
    replay_screen_recording_uri: str | None = None
    replay_reproduction_steps: str | None = None
    replay_terminal_ref: str | None = None
    created_at: datetime
    updated_at: datetime


@router.post("/", response_model=StructuredEvidenceRead, status_code=201)
async def create_structured_evidence(
    body: StructuredEvidenceCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
) -> StructuredEvidenceRead:
    if body.evidence_type not in VALID_EVIDENCE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid evidence_type '{body.evidence_type}'. "
                f"Allowed: {sorted(VALID_EVIDENCE_TYPES)}"
            ),
        )
    if body.validation_status not in VALID_VALIDATION_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Invalid validation_status '{body.validation_status}'. "
                f"Allowed: {sorted(VALID_VALIDATION_STATUSES)}"
            ),
        )
    collected_at = body.collected_at or datetime.now(timezone.utc)
    record = StructuredEvidence(
        campaign_id=body.campaign_id,
        finding_id=body.finding_id,
        evidence_type=body.evidence_type,
        source_phase=body.source_phase,
        collected_at=collected_at,
        collected_by=body.collected_by,
        artifact_uri=body.artifact_uri,
        summary=body.summary,
        validation_status=body.validation_status,
    )
    db.add(record)
    await db.flush()
    await db.refresh(record)
    logger.info(
        "structured_evidence.created id=%s evidence_type=%s campaign_id=%s",
        record.id,
        record.evidence_type,
        record.campaign_id,
    )
    return StructuredEvidenceRead.model_validate(record)


@router.get("/", response_model=list[StructuredEvidenceRead])
async def list_structured_evidence(
    campaign_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
) -> list[StructuredEvidenceRead]:
    stmt = select(StructuredEvidence).order_by(StructuredEvidence.collected_at.desc())
    if campaign_id is not None:
        stmt = stmt.where(StructuredEvidence.campaign_id == campaign_id)
    if current_user.tenant_id:
        stmt = stmt.where(StructuredEvidence.tenant_id == current_user.tenant_id)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    return [StructuredEvidenceRead.model_validate(r) for r in rows]


@router.get("/{evidence_id}", response_model=StructuredEvidenceRead)
async def get_structured_evidence(
    evidence_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
) -> StructuredEvidenceRead:
    result = await db.execute(
        select(StructuredEvidence).where(StructuredEvidence.id == evidence_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail=f"Structured evidence not found: {evidence_id}")
    return StructuredEvidenceRead.model_validate(record)


@router.post("/{evidence_id}/lifecycle", response_model=StructuredEvidenceRead)
async def advance_evidence_lifecycle(
    evidence_id: UUID,
    body: LifecycleAdvanceRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
) -> StructuredEvidenceRead:
    """Advance the lifecycle state of a piece of structured evidence.

    Valid transitions::

        COLLECTED → CORRELATED | REJECTED
        CORRELATED → REVIEWED | REJECTED
        REVIEWED → VALIDATED | REJECTED
        VALIDATED → RECORDED | REJECTED
        RECORDED → REPORT_READY
        REPORT_READY → (terminal)
        REJECTED → (terminal)
    """
    result = await db.execute(
        select(StructuredEvidence).where(StructuredEvidence.id == evidence_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail=f"Structured evidence not found: {evidence_id}")
    svc = EvidenceLifecycleService(db)
    try:
        record = await svc.advance_lifecycle(record, body.to_status, body.actor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    await db.commit()
    await db.refresh(record)
    return StructuredEvidenceRead.model_validate(record)


@router.patch("/{evidence_id}/replay", response_model=StructuredEvidenceRead)
async def patch_replay_fields(
    evidence_id: UUID,
    body: ReplayFieldsPatch,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
) -> StructuredEvidenceRead:
    # Future: replay engine will POST to this endpoint to auto-populate replay fields after execution.
    """Partially update replay artifact references on a piece of structured evidence.

    Only fields present in the request body (non-null) are written.
    Omitting a field leaves the existing value unchanged.
    """
    result = await db.execute(
        select(StructuredEvidence).where(StructuredEvidence.id == evidence_id)
    )
    record = result.scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail=f"Structured evidence not found: {evidence_id}")

    patch_data = body.model_dump(exclude_none=True)
    if not patch_data:
        raise HTTPException(status_code=422, detail="No replay fields provided in request body.")

    for field_name, value in patch_data.items():
        setattr(record, field_name, value)

    await db.flush()
    await db.commit()
    await db.refresh(record)
    logger.info(
        "structured_evidence.replay_patched id=%s fields=%s",
        evidence_id,
        list(patch_data.keys()),
    )
    return StructuredEvidenceRead.model_validate(record)


@router.get("/{evidence_id}/readiness", response_model=EvidenceReadinessReport)
async def get_evidence_readiness(
    evidence_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
) -> EvidenceReadinessReport:
    """Compute a report-readiness snapshot for a piece of structured evidence.

    Returns computed fields; no additional database table is written.
    """
    svc = EvidenceLifecycleService(db)
    try:
        return await svc.get_readiness(evidence_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
