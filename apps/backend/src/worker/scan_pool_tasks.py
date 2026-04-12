"""Celery tasks for scan pool rotation.

Two tasks:

``scan_queue_advance_all``
    Beat task — advances all ACTIVE scan pools every 2 minutes.  Also
    drives stale-entry recovery (entries stuck in ACTIVE > 4 hours).

``scan_pool_entry_complete``
    Completion callback — called by the Celery chain after
    ``run_bug_bounty_schedule_task`` finishes for a pool entry.  Re-queues
    the entry at the tail and fills the freed concurrency slot.
"""
from __future__ import annotations

import asyncio
import logging
from uuid import UUID

from .celery_app import celery_app
from ..core.hil_db import get_async_session_maker

logger = logging.getLogger(__name__)


@celery_app.task(name="scan_queue_advance_all", bind=True)
def advance_all_scan_queues_task(self) -> dict:
    """Beat task: advance all active scan pools every 2 minutes.

    Handles both normal queue advancement and stale-entry recovery (entries
    stuck in ACTIVE for >4 hours are moved to the 'error' state so the slot
    is freed for the next waiting opportunity).

    Returns a summary dict that is stored in the Celery result backend.
    """
    try:
        return asyncio.run(_async_advance_all())
    except Exception as exc:
        # Beat tasks must never raise — a crash stops the beat process.
        logger.error("advance_all_scan_queues_task failed: %s", exc, exc_info=True)
        return {"error": str(exc), "pools_ticked": 0}


async def _async_advance_all() -> dict:
    """Async body for ``advance_all_scan_queues_task``."""
    from ..core.scan_queue_rotator import ScanQueueRotator

    session_maker = get_async_session_maker()
    async with session_maker() as db:
        rotator = ScanQueueRotator()
        result = await rotator.tick_all(db)
        await db.commit()
    return result


@celery_app.task(name="scan_pool_entry_complete", bind=True)
def on_pool_scan_complete_task(
    self,
    *,
    pool_id: str,
    entry_id: str,
    success: bool,
    workflow_run_id: str | None = None,
) -> dict:
    """Called when a pool-entry scan finishes.

    Re-queues the entry at the tail of the pool and advances the pool to fill
    the freed concurrency slot.  Intended to be used as part of a Celery
    ``link`` / callback chain from ``run_bug_bounty_schedule_task``.

    Args:
        pool_id: UUID string of the owning ``OpportunityScanPool``.
        entry_id: UUID string of the ``OpportunityScanPoolEntry``.
        success: Whether the scan completed successfully.
        workflow_run_id: Optional UUID string of the produced workflow run.

    Returns:
        Dict with pool_id, entry_id, and success flag.
    """
    try:
        return asyncio.run(
            _async_on_complete(
                pool_id=UUID(pool_id),
                entry_id=UUID(entry_id),
                success=success,
                workflow_run_id=UUID(workflow_run_id) if workflow_run_id else None,
            )
        )
    except Exception as exc:
        logger.error(
            "on_pool_scan_complete_task failed pool=%s entry=%s: %s",
            pool_id,
            entry_id,
            exc,
            exc_info=True,
        )
        return {
            "pool_id": pool_id,
            "entry_id": entry_id,
            "success": success,
            "error": str(exc),
        }


async def _async_on_complete(
    pool_id: UUID,
    entry_id: UUID,
    success: bool,
    workflow_run_id: UUID | None,
) -> dict:
    """Async body for ``on_pool_scan_complete_task``."""
    from ..core.scan_queue_rotator import ScanQueueRotator

    session_maker = get_async_session_maker()
    async with session_maker() as db:
        rotator = ScanQueueRotator()
        await rotator.complete_entry(db, pool_id, entry_id, success, workflow_run_id)
        await db.commit()
    return {"pool_id": str(pool_id), "entry_id": str(entry_id), "success": success}


# ============================================================================
# API Keys Orchestrator Task (6AM Daily Planning)
# ============================================================================


@celery_app.task(name="api_keys_orchestrator_6am", bind=True)
def run_api_keys_orchestrator_task(self) -> dict:
    """Beat task: Daily 6AM API keys orchestrator.

    Runs at 6AM PT (2PM UTC) to plan API key usage across the scan queue.
    Integrates with Vault-loaded API keys and ScanQueueRotator.

    Returns:
        Dict with orchestration result and queue status.
    """
    try:
        from ..core.api_keys_orchestrator import APIKeysOrchestrator

        session_maker = get_async_session_maker()
        async def _run_orchestrator():
            async with session_maker() as db:
                orchestrator = APIKeysOrchestrator()
                await orchestrator.run(db)
                await db.commit()

        asyncio.run(_run_orchestrator())
        logger.info("API Keys Orchestrator task completed successfully")
        return {
            "status": "success",
            "task": "api_keys_orchestrator_6am",
            "message": "Daily API key planning completed",
        }
    except Exception as exc:
        logger.error(
            "API Keys Orchestrator task failed: %s",
            exc,
            exc_info=True,
        )
        return {
            "status": "error",
            "task": "api_keys_orchestrator_6am",
            "error": str(exc),
        }
