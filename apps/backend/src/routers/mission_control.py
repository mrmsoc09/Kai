"""
Mission Control API
===================
API for mission lifecycle management, including creation, execution,
stopping, and replay of missions.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from apps.backend.src.auth.dependencies import require_roles, CurrentUser
from apps.backend.src.auth.models import UserRole

from apps.backend.src.core.praison_mission_runtime import get_mission_runtime, MissionStatus
from apps.backend.src.core.graph_visualization import export_graph_structure

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/missions", tags=["mission-control"])


# -- Request/Response Schemas -------------------------------------------------

class MissionCreateRequest(BaseModel):
    workflow_id: str
    program_id: str
    mission_name: str = ""
    execution_mode: str = "live"
    run_config: dict[str, Any] = Field(default_factory=dict)


class MissionResponse(BaseModel):
    mission_id: str
    workflow_id: str
    program_id: str
    state: str
    execution_mode: str
    phase: str
    active_node: str
    progress: float
    error: str | None = None


# -- Endpoints ----------------------------------------------------------------

@router.post("/", response_model=MissionResponse)
async def create_mission(
    payload: MissionCreateRequest,
    current_user: CurrentUser = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN))
):
    """Create a new mission."""
    runtime = get_mission_runtime()
    try:
        handle = runtime.create_mission(
            tenant_id=current_user.tenant_id,
            workflow_id=payload.workflow_id,
            program_id=payload.program_id,
            mission_name=payload.mission_name,
            execution_mode=payload.execution_mode,
        )
        return MissionResponse(
            mission_id=handle.mission_id,
            workflow_id=handle.workflow_id,
            program_id=handle.program_id,
            state="created",
            execution_mode=handle.execution_mode,
            phase="",
            active_node="",
            progress=0.0,
        )
    except Exception as exc:
        logger.error("Failed to create mission: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/", response_model=list[MissionResponse])
async def list_missions(
    current_user: CurrentUser = Depends(require_roles(UserRole.VIEWER, UserRole.OPERATOR, UserRole.ANALYST, UserRole.ADMIN))
):
    """List all mission statuses for the current tenant."""
    runtime = get_mission_runtime()
    statuses = runtime.list_missions(tenant_id=current_user.tenant_id)
    return [
        MissionResponse(
            mission_id=s.mission_id,
            workflow_id=s.workflow_id,
            program_id=s.program_id,
            state=s.state,
            execution_mode=s.execution_mode,
            phase=s.phase,
            active_node=s.active_node,
            progress=s.progress,
            error=s.error or None,
        )
        for s in statuses
    ]


@router.get("/{mission_id}", response_model=MissionResponse)
async def get_mission_status(
    mission_id: str,
    current_user: CurrentUser = Depends(require_roles(UserRole.VIEWER, UserRole.OPERATOR, UserRole.ANALYST, UserRole.ADMIN))
):
    """Get status of a specific mission for the current tenant."""
    runtime = get_mission_runtime()
    try:
        s = runtime.get_status(mission_id, tenant_id=current_user.tenant_id)
        return MissionResponse(
            mission_id=s.mission_id,
            workflow_id=s.workflow_id,
            program_id=s.program_id,
            state=s.state,
            execution_mode=s.execution_mode,
            phase=s.phase,
            active_node=s.active_node,
            progress=s.progress,
            error=s.error or None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/{mission_id}/graph")
async def get_mission_graph(
    mission_id: str,
    current_user: CurrentUser = Depends(require_roles(UserRole.VIEWER, UserRole.OPERATOR, UserRole.ANALYST, UserRole.ADMIN))
):
    """Export mission graph structure for visualization."""
    result = export_graph_structure(mission_id, tenant_id=current_user.tenant_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.post("/{mission_id}/start")
async def start_mission(
    mission_id: str,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN))
):
    """Start mission execution in the background."""
    runtime = get_mission_runtime()
    try:
        # Check if already running
        status = runtime.get_status(mission_id, tenant_id=current_user.tenant_id)
        if status.state == "running":
            return {"status": "already running"}
        
        # Start in background as LangGraph might block
        background_tasks.add_task(runtime.start_mission, mission_id, tenant_id=current_user.tenant_id)
        return {"status": "started", "mission_id": mission_id}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/{mission_id}/stop")
async def stop_mission(
    mission_id: str,
    current_user: CurrentUser = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN))
):
    """Stop/pause a running mission."""
    runtime = get_mission_runtime()
    try:
        runtime.stop_mission(mission_id, tenant_id=current_user.tenant_id)
        return {"status": "stopping", "mission_id": mission_id}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/{mission_id}/replay")
async def replay_mission(
    mission_id: str,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_roles(UserRole.ANALYST, UserRole.ADMIN))
):
    """Replay a historical mission from checkpoints."""
    runtime = get_mission_runtime()
    try:
        # Replay implementation (mocked for now as we need real replay logic)
        # Assuming we can resume with replay mode
        background_tasks.add_task(runtime.resume_mission, mission_id, tenant_id=current_user.tenant_id)
        return {"status": "replay_started", "mission_id": mission_id}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
