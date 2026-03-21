"""
System Status & Health API
==========================
API for monitoring platform health, worker status, and mission runtime metrics.
"""

from __future__ import annotations

import os
import psutil
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from apps.backend.src.auth.dependencies import require_roles, CurrentUser
from apps.backend.src.auth.models import UserRole
from apps.backend.src.core.praison_mission_runtime import get_mission_runtime

router = APIRouter(prefix="/system", tags=["system"])


class SystemStatusResponse(BaseModel):
    status: str
    active_missions: int
    completed_missions: int
    worker_ok: bool
    queue_depth: int
    memory_usage_mb: float
    cpu_percent: float


@router.get("/health")
async def get_health():
    """Simple health check endpoint."""
    return {"status": "ok", "timestamp": str(os.getloadavg()[0])}


@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status(
    request: Request,
    current_user: CurrentUser = Depends(require_roles(UserRole.ADMIN))
):
    """
    Detailed system status including resource usage and mission metrics.
    Restricted to ROLE_ADMIN.
    """
    runtime = get_mission_runtime()
    missions = runtime.list_missions(tenant_id=current_user.tenant_id)
    
    active = len([m for m in missions if m.state == "running"])
    completed = len([m for m in missions if m.state == "completed"])
    
    # Resource usage
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / (1024 * 1024)
    cpu = psutil.cpu_percent()
    
    # Worker probe (simulated or via Celery control)
    try:
        from apps.backend.src.worker.celery_app import celery_app
        inspector = celery_app.control.inspect(timeout=0.5)
        ping = inspector.ping() if inspector else None
        worker_ok = bool(ping)
    except Exception:
        worker_ok = False
        
    return SystemStatusResponse(
        status="ok",
        active_missions=active,
        completed_missions=completed,
        worker_ok=worker_ok,
        queue_depth=0, # Simplified
        memory_usage_mb=mem,
        cpu_percent=cpu
    )
