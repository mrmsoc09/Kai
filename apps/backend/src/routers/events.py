"""
Mission Timeline & Event API
============================
API for mission activity timelines, streaming events, and audit logs.
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from apps.backend.src.auth.dependencies import require_roles, CurrentUser
from apps.backend.src.auth.models import UserRole
from apps.backend.src.core.hil_db import get_db
from apps.backend.src.core.praison_mission_runtime import get_mission_runtime
from apps.backend.src.models.campaign import AuditEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/events", tags=["events"])


def _enforce_mission_tenant_access(current_user: CurrentUser, mission_id: UUID) -> None:
    runtime = get_mission_runtime()
    tenant_id = runtime.tenant_for_mission(str(mission_id))
    if tenant_id is None:
        return
    if tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=403, detail="mission_out_of_scope")


# -- Timeline Schema ----------------------------------------------------------

class TimelineEvent(BaseModel):
    id: UUID
    timestamp: datetime
    event_type: str
    actor: str | None = None
    message: str | None = None
    phase_job_id: UUID | None = None
    tool_execution_id: UUID | None = None
    approval_gate_id: UUID | None = None
    details: dict = Field(default_factory=dict)


# -- Endpoints ----------------------------------------------------------------

@router.get("/mission/{mission_id}/timeline", response_model=list[TimelineEvent])
async def get_mission_timeline(
    mission_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.OPERATOR, UserRole.ANALYST, UserRole.ADMIN))
):
    """Get a chronological timeline of all events for a specific mission."""
    _enforce_mission_tenant_access(current_user, mission_id)
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.campaign_id == mission_id)
        .order_by(AuditEvent.happened_at.asc())
    )
    result = await db.execute(stmt)
    events = result.scalars().all()
    
    return [
        TimelineEvent(
            id=e.id,
            timestamp=e.happened_at,
            event_type=e.event_type,
            actor=e.actor,
            message=e.message,
            phase_job_id=e.phase_job_id,
            tool_execution_id=e.tool_execution_id,
            approval_gate_id=e.approval_gate_id,
            details=e.event_payload_json,
        )
        for e in events
    ]


@router.get("/mission/{mission_id}/latest")
async def get_latest_mission_event(
    mission_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.OPERATOR, UserRole.ANALYST, UserRole.ADMIN))
):
    """Get the single most recent event for a mission."""
    _enforce_mission_tenant_access(current_user, mission_id)
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.campaign_id == mission_id)
        .order_by(AuditEvent.happened_at.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    event = result.scalar_one_or_none()
    
    if not event:
        raise HTTPException(status_code=404, detail="No events found for this mission")
        
    return TimelineEvent(
        id=event.id,
        timestamp=event.happened_at,
        event_type=event.event_type,
        actor=event.actor,
        message=event.message,
        phase_job_id=event.phase_job_id,
        tool_execution_id=event.tool_execution_id,
        approval_gate_id=event.approval_gate_id,
        details=event.event_payload_json,
    )
