from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.approval_gate_service import ApprovalGateService
from ..core.auth import ROLE_ADMIN, ROLE_ANALYST, ROLE_OPERATOR, User, require_roles
from ..core.hil_db import get_db
from ..models.approval_evidence_link import ApprovalEvidenceLink
from ..schemas.evidence import ApprovalEvidenceLinkCreate, ApprovalEvidenceLinkRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/approval-evidence", tags=["approval-evidence"])


@router.post("/links", response_model=ApprovalEvidenceLinkRead, status_code=201)
async def create_approval_evidence_link(
    body: ApprovalEvidenceLinkCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
) -> ApprovalEvidenceLinkRead:
    """Create a link between an ApprovalGate and a StructuredEvidence and/or EvidenceValidation.

    The ``reviewer_intention`` field from the gate is snapshotted into the link
    at creation time to provide an immutable audit trail.
    """
    if body.evidence_id is None and body.validation_id is None:
        raise HTTPException(
            status_code=422,
            detail="At least one of evidence_id or validation_id must be provided.",
        )
    svc = ApprovalGateService(db)
    try:
        link = await svc.link_approval_to_evidence(
            gate_id=body.approval_gate_id,
            linked_by=body.linked_by,
            evidence_id=body.evidence_id,
            validation_id=body.validation_id,
            reason=body.link_reason,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    await db.commit()
    await db.refresh(link)
    logger.info(
        "approval_evidence_link.endpoint_created id=%s gate_id=%s actor=%s",
        link.id,
        body.approval_gate_id,
        body.linked_by,
    )
    return ApprovalEvidenceLinkRead.model_validate(link)


@router.get("/links", response_model=list[ApprovalEvidenceLinkRead])
async def list_approval_evidence_links(
    approval_gate_id: UUID | None = Query(default=None),
    evidence_id: UUID | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
) -> list[ApprovalEvidenceLinkRead]:
    """List approval-evidence links.

    Filter by ``approval_gate_id`` to see all evidence linked to a gate.
    Filter by ``evidence_id`` to see all gates linked to a piece of evidence.
    At least one filter must be provided.
    """
    if approval_gate_id is None and evidence_id is None:
        raise HTTPException(
            status_code=422,
            detail="Provide at least one of: approval_gate_id, evidence_id.",
        )
    stmt = select(ApprovalEvidenceLink).order_by(ApprovalEvidenceLink.created_at.asc())
    if approval_gate_id is not None:
        stmt = stmt.where(ApprovalEvidenceLink.approval_gate_id == approval_gate_id)
    if evidence_id is not None:
        stmt = stmt.where(ApprovalEvidenceLink.evidence_id == evidence_id)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    return [ApprovalEvidenceLinkRead.model_validate(r) for r in rows]
