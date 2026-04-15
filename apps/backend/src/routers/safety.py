"""REST endpoints for safety systems (kill switch, violations listing).

Provides analyst-facing APIs for:
- Requesting emergency scan abort
- Checking abort status
- Listing scope violations
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from ..core.auth import get_current_user, User
from ..core.hil_db import get_db
from ..models.scope_violations import ScopeViolation
from ..services.scan_kill_switch import ScanKillSwitch

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/safety", tags=["safety"])


class AbortRequest:
    """Request body for abort endpoint."""

    def __init__(self, reason: str, requested_by: Optional[str] = None):
        self.reason = reason
        self.requested_by = requested_by


@router.post("/scans/{scan_id}/abort")
async def request_scan_abort(
    scan_id: str,
    reason: str = Query(..., description="Reason for abort"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Request emergency abort of a running scan.

    Analyst can stop any scan at any time via kill switch.
    Abort is acknowledged immediately; scan stops at safe checkpoint.

    Args:
        scan_id: UUID of scan to abort
        reason: Human-readable reason for abort
        current_user: Authenticated user
        db: Database session

    Returns:
        Dict confirming kill switch activation
    """
    kill_switch = ScanKillSwitch(db)
    result = await kill_switch.request_abort(
        scan_id=scan_id,
        reason=reason,
        requested_by=current_user.id if hasattr(current_user, "id") else str(current_user),
    )

    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])

    return result


@router.get("/scans/{scan_id}/abort-status")
async def check_abort_status(
    scan_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Check if abort has been requested for a scan.

    Returns abort details if kill switch is active, or empty dict if not.

    Args:
        scan_id: UUID of scan to check
        current_user: Authenticated user
        db: Database session

    Returns:
        Dict with abort status and details (if abort requested)
    """
    kill_switch = ScanKillSwitch(db)
    abort_info = await kill_switch.get_abort_info(scan_id)

    if abort_info:
        return abort_info

    return {"abort_requested": False}


@router.get("/violations")
async def list_scope_violations(
    program_id: Optional[str] = Query(None, description="Filter by program ID"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List scope violations (immutable audit trail).

    Returns paginated list of all scope violations detected during scans.

    Args:
        program_id: Optional filter by program ID
        limit: Max results (default 100)
        offset: Pagination offset
        current_user: Authenticated user
        db: Database session

    Returns:
        Dict with violations list and pagination info
    """
    query = select(ScopeViolation)

    if program_id:
        query = query.where(ScopeViolation.program_id == program_id)

    # Add ordering
    query = query.order_by(ScopeViolation.detected_at.desc())

    # Get total count
    count_result = await db.execute(select(func.count()).select_from(ScopeViolation))
    total_count = count_result.scalar()

    # Get paginated results
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    violations = result.scalars().all()

    return {
        "violations": [
            {
                "id": str(v.id),
                "program_id": str(v.program_id) if v.program_id else None,
                "scan_id": str(v.scan_id) if v.scan_id else None,
                "violation_type": v.violation_type,
                "reason": v.reason,
                "target": v.target,
                "detected_at": v.detected_at.isoformat(),
                "created_by": v.created_by,
            }
            for v in violations
        ],
        "total": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/violations/{program_id}")
async def list_violations_for_program(
    program_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    violation_type: Optional[str] = Query(None, description="Filter by violation type"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List violations for a specific program.

    Args:
        program_id: Program UUID
        limit: Max results
        offset: Pagination offset
        violation_type: Optional filter by violation type
        current_user: Authenticated user
        db: Database session

    Returns:
        Dict with violations for program and pagination info
    """
    query = select(ScopeViolation).where(ScopeViolation.program_id == program_id)

    if violation_type:
        query = query.where(ScopeViolation.violation_type == violation_type)

    # Add ordering
    query = query.order_by(ScopeViolation.detected_at.desc())

    # Get total count
    from sqlalchemy import func

    count_result = await db.execute(
        select(func.count()).select_from(ScopeViolation).where(ScopeViolation.program_id == program_id)
    )
    total_count = count_result.scalar()

    # Get paginated results
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    violations = result.scalars().all()

    return {
        "program_id": program_id,
        "violations": [
            {
                "id": str(v.id),
                "scan_id": str(v.scan_id) if v.scan_id else None,
                "violation_type": v.violation_type,
                "reason": v.reason,
                "target": v.target,
                "detected_at": v.detected_at.isoformat(),
                "created_by": v.created_by,
            }
            for v in violations
        ],
        "total": total_count,
        "limit": limit,
        "offset": offset,
    }


# Import func here to avoid circular imports
from sqlalchemy import func
