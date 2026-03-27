"""FastAPI router for the rotating opportunity scan pool.

All endpoints are under ``/api/v1/scan-pool``.  This is an internal admin
API — no per-request authentication is enforced so that it can be called
from CLI tooling and the beat task.
"""
from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from ..core.hil_db import get_db
from ..core.scan_queue_rotator import ScanQueueRotator
from ..models.scan_pool import OpportunityScanPool, OpportunityScanPoolEntry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/scan-pool", tags=["scan-pool"])


# ============================================================================
# Pydantic request / response schemas
# ============================================================================


class CreatePoolRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    user_id: str | None = None
    min_concurrent: int = Field(default=5, ge=1, le=25)
    max_concurrent: int = Field(default=7, ge=1, le=25)
    target_cycle_days: int | None = Field(default=None, ge=1)


class UpdatePoolSettingsRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    min_concurrent: int | None = Field(default=None, ge=1, le=25)
    max_concurrent: int | None = Field(default=None, ge=1, le=25)
    target_cycle_days: int | None = Field(default=None, ge=1)


class AddOpportunityRequest(BaseModel):
    program_name: str = Field(..., min_length=1, max_length=255)
    program_id: UUID | None = None
    schedule_job_id: UUID | None = None
    platform: str | None = None
    program_handle: str | None = None


class ReorderQueueRequest(BaseModel):
    entry_ids: list[UUID] = Field(..., min_length=1)


class PoolResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    user_id: str | None
    status: str
    min_concurrent: int
    max_concurrent: int
    current_cycle: int
    cycle_started_at: str | None
    last_cycle_completed_at: str | None
    target_cycle_days: int | None
    created_at: str | None
    updated_at: str | None


class EntryResponse(BaseModel):
    id: UUID
    pool_id: UUID
    queue_position: int
    status: str
    program_name: str
    platform: str | None
    program_handle: str | None
    schedule_job_id: UUID | None
    program_id: UUID | None
    total_scans_completed: int
    current_cycle_scanned: bool
    last_activated_at: str | None
    last_completed_at: str | None
    last_scan_status: str | None
    last_celery_task_id: str | None
    created_at: str | None


def _pool_to_response(pool: OpportunityScanPool) -> dict[str, Any]:
    return {
        "id": pool.id,
        "name": pool.name,
        "description": pool.description,
        "user_id": pool.user_id,
        "status": pool.status,
        "min_concurrent": pool.min_concurrent,
        "max_concurrent": pool.max_concurrent,
        "current_cycle": pool.current_cycle,
        "cycle_started_at": pool.cycle_started_at.isoformat() if pool.cycle_started_at else None,
        "last_cycle_completed_at": (
            pool.last_cycle_completed_at.isoformat()
            if pool.last_cycle_completed_at
            else None
        ),
        "target_cycle_days": pool.target_cycle_days,
        "created_at": pool.created_at.isoformat() if pool.created_at else None,
        "updated_at": pool.updated_at.isoformat() if pool.updated_at else None,
    }


def _entry_to_response(entry: OpportunityScanPoolEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "pool_id": entry.pool_id,
        "queue_position": entry.queue_position,
        "status": entry.status,
        "program_name": entry.program_name,
        "platform": entry.platform,
        "program_handle": entry.program_handle,
        "schedule_job_id": entry.schedule_job_id,
        "program_id": entry.program_id,
        "total_scans_completed": entry.total_scans_completed,
        "current_cycle_scanned": entry.current_cycle_scanned,
        "last_activated_at": (
            entry.last_activated_at.isoformat() if entry.last_activated_at else None
        ),
        "last_completed_at": (
            entry.last_completed_at.isoformat() if entry.last_completed_at else None
        ),
        "last_scan_status": entry.last_scan_status,
        "last_celery_task_id": entry.last_celery_task_id,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
    }


# ============================================================================
# Pool CRUD endpoints
# ============================================================================


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_pool(
    body: CreatePoolRequest,
    db=Depends(get_db),
) -> dict[str, Any]:
    """Create a new rotating scan pool."""
    if body.min_concurrent > body.max_concurrent:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="min_concurrent must be <= max_concurrent",
        )
    pool = OpportunityScanPool(
        name=body.name,
        description=body.description,
        user_id=body.user_id,
        status="paused",
        min_concurrent=body.min_concurrent,
        max_concurrent=body.max_concurrent,
        target_cycle_days=body.target_cycle_days,
        current_cycle=0,
    )
    db.add(pool)
    await db.flush()
    await db.refresh(pool)
    return _pool_to_response(pool)


@router.get("")
async def list_pools(
    db=Depends(get_db),
) -> list[dict[str, Any]]:
    """List all scan pools."""
    from sqlalchemy import select

    result = await db.execute(select(OpportunityScanPool))
    pools: list[OpportunityScanPool] = result.scalars().all()
    return [_pool_to_response(p) for p in pools]


@router.get("/{pool_id}")
async def get_pool(
    pool_id: UUID,
    db=Depends(get_db),
) -> dict[str, Any]:
    """Get pool status including entry summary."""
    rotator = ScanQueueRotator()
    pool_status = await rotator.get_pool_status(db, pool_id)
    if "error" in pool_status and pool_status.get("error") == "pool not found":
        raise HTTPException(status_code=404, detail="Pool not found")
    return pool_status


@router.delete("/{pool_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pool(
    pool_id: UUID,
    db=Depends(get_db),
) -> None:
    """Delete a pool.  Pool must be in 'stopped' or 'paused' status."""
    from sqlalchemy import select

    result = await db.execute(
        select(OpportunityScanPool).where(OpportunityScanPool.id == pool_id)
    )
    pool: OpportunityScanPool | None = result.scalar_one_or_none()
    if pool is None:
        raise HTTPException(status_code=404, detail="Pool not found")
    if pool.status == "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pool must be paused or stopped before deletion",
        )
    await db.delete(pool)


@router.put("/{pool_id}/settings")
async def update_pool_settings(
    pool_id: UUID,
    body: UpdatePoolSettingsRequest,
    db=Depends(get_db),
) -> dict[str, Any]:
    """Update pool name, description, concurrency window, or target_cycle_days."""
    from sqlalchemy import select

    result = await db.execute(
        select(OpportunityScanPool).where(OpportunityScanPool.id == pool_id)
    )
    pool: OpportunityScanPool | None = result.scalar_one_or_none()
    if pool is None:
        raise HTTPException(status_code=404, detail="Pool not found")

    if body.name is not None:
        pool.name = body.name
    if body.description is not None:
        pool.description = body.description
    if body.target_cycle_days is not None:
        pool.target_cycle_days = body.target_cycle_days

    # Validate concurrency settings together.
    new_min = body.min_concurrent if body.min_concurrent is not None else pool.min_concurrent
    new_max = body.max_concurrent if body.max_concurrent is not None else pool.max_concurrent
    if new_min > new_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="min_concurrent must be <= max_concurrent",
        )
    if body.min_concurrent is not None:
        pool.min_concurrent = body.min_concurrent
    if body.max_concurrent is not None:
        pool.max_concurrent = body.max_concurrent

    db.add(pool)
    await db.flush()
    await db.refresh(pool)
    return _pool_to_response(pool)


# ============================================================================
# Pool lifecycle control
# ============================================================================


@router.post("/{pool_id}/pause")
async def pause_pool(
    pool_id: UUID,
    db=Depends(get_db),
) -> dict[str, Any]:
    """Pause a pool (no new scans started; in-progress scans finish)."""
    rotator = ScanQueueRotator()
    try:
        await rotator.pause_pool(db, pool_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"pool_id": str(pool_id), "status": "paused"}


@router.post("/{pool_id}/resume")
async def resume_pool(
    pool_id: UUID,
    db=Depends(get_db),
) -> dict[str, Any]:
    """Resume a paused pool (status → active; immediately advances queue)."""
    rotator = ScanQueueRotator()
    try:
        await rotator.resume_pool(db, pool_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return {"pool_id": str(pool_id), "status": "active"}


@router.post("/{pool_id}/stop")
async def stop_pool(
    pool_id: UUID,
    db=Depends(get_db),
) -> dict[str, Any]:
    """Stop a pool (no new scans; sets status to 'stopped')."""
    from sqlalchemy import select

    result = await db.execute(
        select(OpportunityScanPool).where(OpportunityScanPool.id == pool_id)
    )
    pool: OpportunityScanPool | None = result.scalar_one_or_none()
    if pool is None:
        raise HTTPException(status_code=404, detail="Pool not found")
    pool.status = "stopped"
    db.add(pool)
    return {"pool_id": str(pool_id), "status": "stopped"}


# ============================================================================
# Queue view and management
# ============================================================================


@router.get("/{pool_id}/queue")
async def get_queue(
    pool_id: UUID,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db=Depends(get_db),
) -> dict[str, Any]:
    """Paginated ordered queue view for a pool."""
    from sqlalchemy import select, func

    pool_result = await db.execute(
        select(OpportunityScanPool).where(OpportunityScanPool.id == pool_id)
    )
    pool: OpportunityScanPool | None = pool_result.scalar_one_or_none()
    if pool is None:
        raise HTTPException(status_code=404, detail="Pool not found")

    total_result = await db.execute(
        select(func.count()).where(OpportunityScanPoolEntry.pool_id == pool_id)
    )
    total: int = total_result.scalar() or 0

    entries_result = await db.execute(
        select(OpportunityScanPoolEntry)
        .where(OpportunityScanPoolEntry.pool_id == pool_id)
        .order_by(OpportunityScanPoolEntry.queue_position)
        .offset(offset)
        .limit(limit)
    )
    entries: list[OpportunityScanPoolEntry] = entries_result.scalars().all()

    return {
        "pool_id": str(pool_id),
        "total": total,
        "offset": offset,
        "limit": limit,
        "entries": [_entry_to_response(e) for e in entries],
    }


@router.post("/{pool_id}/opportunities", status_code=status.HTTP_201_CREATED)
async def add_opportunity(
    pool_id: UUID,
    body: AddOpportunityRequest,
    db=Depends(get_db),
) -> dict[str, Any]:
    """Add an opportunity to the queue tail."""
    from sqlalchemy import select

    pool_result = await db.execute(
        select(OpportunityScanPool).where(OpportunityScanPool.id == pool_id)
    )
    pool: OpportunityScanPool | None = pool_result.scalar_one_or_none()
    if pool is None:
        raise HTTPException(status_code=404, detail="Pool not found")

    rotator = ScanQueueRotator()
    entry = await rotator.add_opportunity(
        db,
        pool_id,
        program_name=body.program_name,
        program_id=body.program_id,
        schedule_job_id=body.schedule_job_id,
        platform=body.platform,
        program_handle=body.program_handle,
    )
    return _entry_to_response(entry)


@router.delete(
    "/{pool_id}/opportunities/{entry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def remove_opportunity(
    pool_id: UUID,
    entry_id: UUID,
    db=Depends(get_db),
) -> None:
    """Remove a waiting or error entry from the queue."""
    rotator = ScanQueueRotator()
    removed = await rotator.remove_opportunity(db, pool_id, entry_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Entry not found or is currently active and cannot be removed",
        )


@router.put("/{pool_id}/reorder")
async def reorder_queue(
    pool_id: UUID,
    body: ReorderQueueRequest,
    db=Depends(get_db),
) -> dict[str, Any]:
    """Reorder the queue by specifying the new ordering of entry IDs."""
    from sqlalchemy import select

    pool_result = await db.execute(
        select(OpportunityScanPool).where(OpportunityScanPool.id == pool_id)
    )
    pool: OpportunityScanPool | None = pool_result.scalar_one_or_none()
    if pool is None:
        raise HTTPException(status_code=404, detail="Pool not found")

    rotator = ScanQueueRotator()
    await rotator.reorder_queue(db, pool_id, body.entry_ids)
    return {"pool_id": str(pool_id), "reordered": len(body.entry_ids)}


@router.post("/{pool_id}/advance")
async def manually_advance(
    pool_id: UUID,
    db=Depends(get_db),
) -> dict[str, Any]:
    """Manually trigger queue advancement (for testing / debugging)."""
    rotator = ScanQueueRotator()
    result = await rotator.tick_pool(db, pool_id)
    if "error" in result and result.get("error") == "pool not found":
        raise HTTPException(status_code=404, detail="Pool not found")
    return result
