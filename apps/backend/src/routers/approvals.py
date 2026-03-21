"""
Governance Approval API
=======================
API for managing governance approval gates (Band 2 human-in-the-loop).
Allows operators to review, approve, reject, or cancel pending actions.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from apps.backend.src.auth.dependencies import require_roles, CurrentUser
from apps.backend.src.auth.models import UserRole

from apps.backend.src.core.hil_db import get_db
from apps.backend.src.core.approval_gate_service import ApprovalGateService
from apps.backend.src.core.praison_mission_runtime import get_mission_runtime
from apps.backend.src.models.campaign import ApprovalGate
from apps.backend.src.models.enums import ApprovalGateStatusEnum
from apps.backend.src.schemas.campaigns import ApprovalGateRead, ApprovalGateDecision

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.get("/", response_model=list[ApprovalGateRead])
async def list_approvals(
    status: ApprovalGateStatusEnum = ApprovalGateStatusEnum.PENDING,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.OPERATOR, UserRole.ANALYST, UserRole.ADMIN))
):
    """List all approval gates with a specific status for the current tenant."""
    stmt = select(ApprovalGate).where(
        ApprovalGate.status == status,
        ApprovalGate.tenant_id == current_user.tenant_id
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{gate_id}", response_model=ApprovalGateRead)
async def get_approval(
    gate_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.OPERATOR, UserRole.ANALYST, UserRole.ADMIN))
):
    """Get details of a specific approval gate for the current tenant."""
    service = ApprovalGateService(db)
    gate = await service.get_gate(gate_id, tenant_id=current_user.tenant_id)
    if not gate:
        raise HTTPException(status_code=404, detail="Approval gate not found")
    return gate


@router.post("/{gate_id}/approve", response_model=ApprovalGateRead)
async def approve_gate(
    gate_id: UUID,
    notes: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN))
):
    """Approve a pending governance action."""
    service = ApprovalGateService(db)
    gate = await service.get_gate(gate_id, tenant_id=current_user.tenant_id)
    if not gate:
        raise HTTPException(status_code=404, detail="Approval gate not found")
    
    decision = ApprovalGateDecision(
        status=ApprovalGateStatusEnum.APPROVED,
        decided_by=str(current_user.id),
        operator_notes=notes
    )
    
    updated_gate = await service.decide_gate(gate, decision)
    await db.commit()
    
    # Notify mission runtime to resume if applicable
    runtime = get_mission_runtime()
    try:
        mission_id = str(updated_gate.campaign_id)
        # Verify if mission exists in runtime
        runtime.get_status(mission_id, tenant_id=current_user.tenant_id)
        runtime.approve_pending(
            mission_id=mission_id,
            tenant_id=current_user.tenant_id,
            approval_id=str(gate_id),
            decision="approved",
            resolved_by=str(current_user.id)
        )
    except ValueError:
        # Mission might not be active in this runtime instance
        pass
    
    return updated_gate


@router.post("/{gate_id}/reject", response_model=ApprovalGateRead)
async def reject_gate(
    gate_id: UUID,
    notes: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN))
):
    """Reject a pending governance action."""
    service = ApprovalGateService(db)
    gate = await service.get_gate(gate_id, tenant_id=current_user.tenant_id)
    if not gate:
        raise HTTPException(status_code=404, detail="Approval gate not found")
    
    decision = ApprovalGateDecision(
        status=ApprovalGateStatusEnum.REJECTED,
        decided_by=str(current_user.id),
        operator_notes=notes
    )
    
    updated_gate = await service.decide_gate(gate, decision)
    await db.commit()
    
    # Notify mission runtime
    runtime = get_mission_runtime()
    try:
        mission_id = str(updated_gate.campaign_id)
        runtime.get_status(mission_id, tenant_id=current_user.tenant_id)
        runtime.approve_pending(
            mission_id=mission_id,
            tenant_id=current_user.tenant_id,
            approval_id=str(gate_id),
            decision="rejected",
            resolved_by=str(current_user.id)
        )
    except ValueError:
        pass
    
    return updated_gate


@router.post("/{gate_id}/cancel", response_model=ApprovalGateRead)
async def cancel_gate(
    gate_id: UUID,
    notes: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN))
):
    """Cancel a pending approval gate."""
    service = ApprovalGateService(db)
    gate = await service.get_gate(gate_id, tenant_id=current_user.tenant_id)
    if not gate:
        raise HTTPException(status_code=404, detail="Approval gate not found")
    
    updated_gate = await service.cancel_gate(gate, actor=str(current_user.id), note=notes)
    await db.commit()
    
    return updated_gate
