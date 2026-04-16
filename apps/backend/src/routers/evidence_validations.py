from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.auth import ROLE_ADMIN, ROLE_ANALYST, ROLE_OPERATOR, User, require_roles
from ..core.evidence_validation_service import EvidenceValidationService
from ..core.hil_db import get_db
from ..schemas.evidence import EvidenceValidationCreate, EvidenceValidationRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/evidence/validations", tags=["evidence-validations"])


@router.post("/", response_model=EvidenceValidationRead, status_code=201)
async def create_evidence_validation(
    body: EvidenceValidationCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
) -> EvidenceValidationRead:
    """Create a validation record for a piece of structured evidence.

    If ``validation_outcome`` is "CONFIRMED" the evidence lifecycle will be
    automatically advanced to REVIEWED (if the current state allows it).
    If ``validation_outcome`` is "REJECTED" the evidence lifecycle will be
    advanced to REJECTED (if the current state allows it).

    Lifecycle advancement failures are non-fatal and are logged as warnings.
    """
    svc = EvidenceValidationService(db)
    try:
        record = await svc.create_validation(
            evidence_id=body.evidence_id,
            actor=body.actor,
            method=body.validation_method,
            outcome=body.validation_outcome,
            notes=body.notes,
            campaign_id=body.campaign_id,
            finding_id=body.finding_id,
            tenant_id=body.tenant_id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    await db.commit()
    await db.refresh(record)
    return EvidenceValidationRead.model_validate(record)


@router.get("/", response_model=list[EvidenceValidationRead])
async def list_evidence_validations(
    evidence_id: UUID = Query(..., description="UUID of the structured evidence record"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
) -> list[EvidenceValidationRead]:
    """List all validation records for a piece of structured evidence."""
    svc = EvidenceValidationService(db)
    records = await svc.get_validations_for_evidence(evidence_id)
    return [EvidenceValidationRead.model_validate(r) for r in records]
