"""ScanQueueRotator — manages the rotating opportunity scan pool.

Public interface::

    rotator = ScanQueueRotator()
    await rotator.tick_all(db)               # Called by beat task every 2 min
    await rotator.tick_pool(db, pool_id)     # Check completions + advance
    await rotator.add_opportunity(db, pool_id, ...)
    await rotator.remove_opportunity(db, pool_id, entry_id)
    await rotator.pause_pool(db, pool_id)
    await rotator.resume_pool(db, pool_id)
    await rotator.get_pool_status(db, pool_id) -> dict

All public methods accept an ``AsyncSession`` and flush changes to it without
committing — callers are responsible for ``await db.commit()``.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update

from ..models.scan_pool import OpportunityScanPool, OpportunityScanPoolEntry

logger = logging.getLogger(__name__)


class ScanQueueRotator:
    """Stateless service object for the rotating scan pool.

    Instantiate per-call (no shared mutable state); all persistence is
    in the DB via the supplied ``AsyncSession``.
    """

    # ------------------------------------------------------------------ #
    # Beat-facing entry points                                             #
    # ------------------------------------------------------------------ #

    async def tick_all(self, db: Any) -> dict:
        """Tick all ACTIVE pools.  Called by the beat task every 2 minutes.

        Also drives stale-entry recovery (entries stuck as ACTIVE >4 hours).

        Returns a summary dict suitable for logging or task result storage.
        """
        try:
            result = await db.execute(
                select(OpportunityScanPool).where(
                    OpportunityScanPool.status == "active"
                )
            )
            pools: list[OpportunityScanPool] = result.scalars().all()
        except Exception as exc:
            logger.warning("scan_queue_rotator.tick_all: DB unavailable: %s", exc)
            return {"error": str(exc), "pools_ticked": 0}

        summary: list[dict] = []
        for pool in pools:
            try:
                tick_result = await self.tick_pool(db, pool.id)
                summary.append(tick_result)
            except Exception as exc:
                logger.warning(
                    "scan_queue_rotator.tick_pool failed for pool=%s: %s", pool.id, exc
                )
                summary.append({"pool_id": str(pool.id), "error": str(exc)})

        return {"pools_ticked": len(pools), "details": summary}

    async def tick_pool(self, db: Any, pool_id: UUID) -> dict:
        """Check completions and advance the queue for a single pool.

        Steps:
        1. Recover stale ACTIVE entries (>4 h without completion).
        2. Detect ACTIVE entries whose schedule job has finished and
           re-queue them at the tail.
        3. Fill the concurrency window up to ``min_concurrent``.
        4. Check whether the pool cycle has completed.
        """
        pool = await self._get_pool(db, pool_id)
        if pool is None:
            return {"pool_id": str(pool_id), "error": "pool not found"}

        if pool.status != "active":
            return {"pool_id": str(pool_id), "status": pool.status, "skipped": True}

        stale_count = await self.check_stale_active_entries(db, pool)
        completed_count = await self._detect_and_complete_finished_entries(db, pool)
        activated_count = await self.advance_queue(db, pool)
        cycle_completed = await self.check_cycle_completion(db, pool)

        return {
            "pool_id": str(pool_id),
            "stale_recovered": stale_count,
            "completed_detected": completed_count,
            "slots_activated": activated_count,
            "cycle_completed": cycle_completed,
        }

    # ------------------------------------------------------------------ #
    # Queue advancement                                                    #
    # ------------------------------------------------------------------ #

    async def advance_queue(self, db: Any, pool: OpportunityScanPool) -> int:
        """Fill the concurrency window up to ``min_concurrent``.

        Returns the number of entries activated this call.
        """
        # Count currently active entries.
        active_result = await db.execute(
            select(func.count()).where(
                OpportunityScanPoolEntry.pool_id == pool.id,
                OpportunityScanPoolEntry.status == "active",
            )
        )
        active_count: int = active_result.scalar() or 0

        # How many more can we start? Never exceed max_concurrent.
        slots_available = min(
            pool.min_concurrent - active_count,
            pool.max_concurrent - active_count,
        )
        if slots_available <= 0:
            return 0

        # Fetch next WAITING entries in queue order.
        waiting_result = await db.execute(
            select(OpportunityScanPoolEntry)
            .where(
                OpportunityScanPoolEntry.pool_id == pool.id,
                OpportunityScanPoolEntry.status == "waiting",
            )
            .order_by(OpportunityScanPoolEntry.queue_position)
            .limit(slots_available)
        )
        waiting_entries: list[OpportunityScanPoolEntry] = waiting_result.scalars().all()

        activated = 0
        for entry in waiting_entries:
            success = await self.activate_entry(db, pool, entry)
            if success:
                activated += 1

        return activated

    async def activate_entry(
        self, db: Any, pool: OpportunityScanPool, entry: OpportunityScanPoolEntry
    ) -> bool:
        """Dispatch a scan for ``entry`` via Celery.

        Sets entry status to "active" and records the Celery task ID.
        Returns True on successful dispatch, False on failure (entry marked "error").
        """
        if entry.schedule_job_id is None:
            logger.warning(
                "scan_queue_rotator.activate_entry: entry=%s has no schedule_job_id — "
                "cannot dispatch scan; marking error",
                entry.id,
            )
            entry.status = "error"
            entry.last_scan_status = "error"
            db.add(entry)
            return False

        try:
            from apps.backend.src.worker.campaign_tasks import run_bug_bounty_schedule_task

            task = run_bug_bounty_schedule_task.delay(
                schedule_id=str(entry.schedule_job_id),
                actor="scan_queue_rotator",
                worker_role="scan_pool_worker",
                force=False,
            )
            entry.status = "active"
            entry.last_activated_at = datetime.now(timezone.utc)
            entry.last_celery_task_id = task.id
            db.add(entry)
            logger.info(
                "scan_queue_rotator.activate_entry: pool=%s entry=%s task=%s",
                pool.id,
                entry.id,
                task.id,
            )
            return True
        except Exception as exc:
            logger.error(
                "scan_queue_rotator.activate_entry: failed to dispatch entry=%s: %s",
                entry.id,
                exc,
            )
            entry.status = "error"
            entry.last_scan_status = "error"
            db.add(entry)
            return False

    # ------------------------------------------------------------------ #
    # Entry completion and re-queuing                                      #
    # ------------------------------------------------------------------ #

    async def complete_entry(
        self,
        db: Any,
        pool_id: UUID,
        entry_id: UUID,
        success: bool,
        workflow_run_id: UUID | None = None,
    ) -> None:
        """Record scan completion and re-queue the entry at the tail.

        Called by ``on_pool_scan_complete_task`` after a pool scan finishes.
        After re-queuing, a new slot is filled via ``advance_queue``.
        """
        entry = await self._get_entry(db, entry_id)
        if entry is None:
            logger.warning("complete_entry: entry %s not found", entry_id)
            return

        pool = await self._get_pool(db, pool_id)
        if pool is None:
            logger.warning("complete_entry: pool %s not found", pool_id)
            return

        now = datetime.now(timezone.utc)
        entry.last_completed_at = now
        entry.last_scan_status = "completed" if success else "failed"
        entry.total_scans_completed = (entry.total_scans_completed or 0) + 1
        entry.current_cycle_scanned = True
        if workflow_run_id is not None:
            entry.last_workflow_run_id = workflow_run_id

        # Re-queue at tail (round-robin).
        max_pos_result = await db.execute(
            select(func.max(OpportunityScanPoolEntry.queue_position)).where(
                OpportunityScanPoolEntry.pool_id == pool_id
            )
        )
        max_position: int = max_pos_result.scalar() or 0
        entry.queue_position = max_position + 1
        entry.status = "waiting"
        db.add(entry)

        await db.flush()

        # Check if the full cycle just completed.
        await self.check_cycle_completion(db, pool)

        # Immediately fill the freed slot.
        if pool.status == "active":
            await self.advance_queue(db, pool)

    # ------------------------------------------------------------------ #
    # Cycle management                                                     #
    # ------------------------------------------------------------------ #

    async def check_cycle_completion(
        self, db: Any, pool: OpportunityScanPool
    ) -> bool:
        """Return True and increment the cycle counter if all entries have been
        scanned in the current cycle.  Resets ``current_cycle_scanned`` on all
        entries for the next rotation.
        """
        # Count total entries and how many have been scanned this cycle.
        total_result = await db.execute(
            select(func.count()).where(
                OpportunityScanPoolEntry.pool_id == pool.id
            )
        )
        total: int = total_result.scalar() or 0
        if total == 0:
            return False

        unscanned_result = await db.execute(
            select(func.count()).where(
                OpportunityScanPoolEntry.pool_id == pool.id,
                OpportunityScanPoolEntry.current_cycle_scanned.is_(False),
            )
        )
        unscanned: int = unscanned_result.scalar() or 0

        if unscanned > 0:
            return False

        # All entries scanned — complete the cycle.
        now = datetime.now(timezone.utc)
        pool.current_cycle = (pool.current_cycle or 0) + 1
        pool.last_cycle_completed_at = now
        if pool.cycle_started_at is None:
            # Retroactively record the cycle start as pool creation time.
            pool.cycle_started_at = pool.created_at or now

        duration_seconds: float | None = None
        if pool.cycle_started_at is not None:
            delta = now - pool.cycle_started_at
            duration_seconds = delta.total_seconds()

        logger.info(
            "scan_queue_rotator: pool=%s completed cycle=%d in %.0f seconds",
            pool.id,
            pool.current_cycle,
            duration_seconds or 0.0,
        )

        # Reset per-entry scan flags for the next cycle, then record new start.
        await db.execute(
            update(OpportunityScanPoolEntry)
            .where(OpportunityScanPoolEntry.pool_id == pool.id)
            .values(current_cycle_scanned=False)
        )
        pool.cycle_started_at = now
        db.add(pool)
        await db.flush()
        return True

    # ------------------------------------------------------------------ #
    # Pool and entry CRUD                                                  #
    # ------------------------------------------------------------------ #

    async def add_opportunity(
        self,
        db: Any,
        pool_id: UUID,
        program_name: str,
        program_id: UUID | None = None,
        schedule_job_id: UUID | None = None,
        platform: str | None = None,
        program_handle: str | None = None,
    ) -> OpportunityScanPoolEntry:
        """Append a new opportunity at the tail of the queue."""
        max_pos_result = await db.execute(
            select(func.max(OpportunityScanPoolEntry.queue_position)).where(
                OpportunityScanPoolEntry.pool_id == pool_id
            )
        )
        max_position: int = max_pos_result.scalar() or 0

        entry = OpportunityScanPoolEntry(
            pool_id=pool_id,
            program_id=program_id,
            schedule_job_id=schedule_job_id,
            queue_position=max_position + 1,
            status="waiting",
            program_name=program_name,
            platform=platform,
            program_handle=program_handle,
            total_scans_completed=0,
            current_cycle_scanned=False,
        )
        db.add(entry)
        await db.flush()
        logger.info(
            "scan_queue_rotator.add_opportunity: pool=%s entry=%s pos=%d program=%r",
            pool_id,
            entry.id,
            entry.queue_position,
            program_name,
        )
        return entry

    async def remove_opportunity(
        self, db: Any, pool_id: UUID, entry_id: UUID
    ) -> bool:
        """Remove a WAITING or ERROR entry.  Refuses to remove ACTIVE entries.

        Returns True if removed, False if the entry was active or not found.
        """
        entry = await self._get_entry(db, entry_id)
        if entry is None:
            logger.warning("remove_opportunity: entry %s not found", entry_id)
            return False

        if entry.status == "active":
            logger.warning(
                "remove_opportunity: cannot remove active entry %s in pool %s",
                entry_id,
                pool_id,
            )
            return False

        await db.delete(entry)
        await db.flush()
        return True

    async def pause_entry(
        self, db: Any, pool_id: UUID, entry_id: UUID
    ) -> OpportunityScanPoolEntry | None:
        """Pause a waiting or active entry.

        Active scans are not cancelled here; this only prevents the entry from
        being selected again until it is resumed.
        """
        entry = await self._get_entry(db, entry_id)
        if entry is None or entry.pool_id != pool_id:
            return None
        if entry.status not in {"waiting", "active"}:
            return entry
        entry.status = "paused"
        db.add(entry)
        await db.flush()
        return entry

    async def resume_entry(
        self, db: Any, pool_id: UUID, entry_id: UUID
    ) -> OpportunityScanPoolEntry | None:
        """Resume a paused entry back into the waiting queue.

        If the pool is active, queue advancement is attempted immediately.
        """
        entry = await self._get_entry(db, entry_id)
        if entry is None or entry.pool_id != pool_id:
            return None
        if entry.status != "paused":
            return entry

        entry.status = "waiting"
        db.add(entry)
        await db.flush()

        pool = await self._get_pool(db, pool_id)
        if pool is not None and pool.status == "active":
            await self.advance_queue(db, pool)
        return entry

    # ------------------------------------------------------------------ #
    # Pool lifecycle                                                       #
    # ------------------------------------------------------------------ #

    async def pause_pool(self, db: Any, pool_id: UUID) -> None:
        """Set pool status to 'paused'."""
        pool = await self._get_pool(db, pool_id)
        if pool is None:
            raise ValueError(f"Pool {pool_id} not found")
        pool.status = "paused"
        db.add(pool)
        await db.flush()

    async def resume_pool(self, db: Any, pool_id: UUID) -> None:
        """Set pool status to 'active' and immediately advance the queue."""
        pool = await self._get_pool(db, pool_id)
        if pool is None:
            raise ValueError(f"Pool {pool_id} not found")
        pool.status = "active"
        if pool.cycle_started_at is None:
            pool.cycle_started_at = datetime.now(timezone.utc)
        db.add(pool)
        await db.flush()
        await self.advance_queue(db, pool)

    # ------------------------------------------------------------------ #
    # Status and settings                                                  #
    # ------------------------------------------------------------------ #

    async def get_pool_status(self, db: Any, pool_id: UUID) -> dict:
        """Return a summary dict for a pool and its entries."""
        pool = await self._get_pool(db, pool_id)
        if pool is None:
            return {"error": "pool not found"}

        entries_result = await db.execute(
            select(OpportunityScanPoolEntry)
            .where(OpportunityScanPoolEntry.pool_id == pool_id)
            .order_by(OpportunityScanPoolEntry.queue_position)
        )
        entries: list[OpportunityScanPoolEntry] = entries_result.scalars().all()

        status_counts: dict[str, int] = {}
        for e in entries:
            status_counts[e.status] = status_counts.get(e.status, 0) + 1

        return {
            "pool_id": str(pool.id),
            "name": pool.name,
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
            "total_entries": len(entries),
            "status_counts": status_counts,
            "entries": [
                {
                    "id": str(e.id),
                    "queue_position": e.queue_position,
                    "program_name": e.program_name,
                    "platform": e.platform,
                    "program_handle": e.program_handle,
                    "status": e.status,
                    "total_scans_completed": e.total_scans_completed,
                    "current_cycle_scanned": e.current_cycle_scanned,
                    "last_activated_at": (
                        e.last_activated_at.isoformat() if e.last_activated_at else None
                    ),
                    "last_completed_at": (
                        e.last_completed_at.isoformat() if e.last_completed_at else None
                    ),
                    "last_scan_status": e.last_scan_status,
                    "last_celery_task_id": e.last_celery_task_id,
                }
                for e in entries
            ],
        }

    async def set_concurrency(
        self,
        db: Any,
        pool_id: UUID,
        min_concurrent: int,
        max_concurrent: int,
    ) -> None:
        """Update the concurrency window.  Raises ValueError if constraints fail."""
        if min_concurrent < 1:
            raise ValueError("min_concurrent must be >= 1")
        if max_concurrent < 1 or max_concurrent > 25:
            raise ValueError("max_concurrent must be between 1 and 25")
        if min_concurrent > max_concurrent:
            raise ValueError("min_concurrent must be <= max_concurrent")

        pool = await self._get_pool(db, pool_id)
        if pool is None:
            raise ValueError(f"Pool {pool_id} not found")

        pool.min_concurrent = min_concurrent
        pool.max_concurrent = max_concurrent
        db.add(pool)
        await db.flush()

    async def reorder_queue(
        self, db: Any, pool_id: UUID, entry_ids: list[UUID]
    ) -> None:
        """Reorder the queue by specifying the desired ordering of entry IDs.

        Only WAITING and PAUSED entries may be reordered; ACTIVE entries keep
        their current positions to avoid disrupting in-flight scans.
        """
        entries_result = await db.execute(
            select(OpportunityScanPoolEntry).where(
                OpportunityScanPoolEntry.pool_id == pool_id,
                OpportunityScanPoolEntry.id.in_(entry_ids),
                OpportunityScanPoolEntry.status.in_(["waiting", "paused"]),
            )
        )
        entries_by_id: dict[UUID, OpportunityScanPoolEntry] = {
            e.id: e for e in entries_result.scalars().all()
        }

        # Build a contiguous position block starting after the highest active
        # entry's position so active scans are not displaced.
        active_max_result = await db.execute(
            select(func.max(OpportunityScanPoolEntry.queue_position)).where(
                OpportunityScanPoolEntry.pool_id == pool_id,
                OpportunityScanPoolEntry.status == "active",
            )
        )
        start_pos: int = (active_max_result.scalar() or 0) + 1

        for new_pos, eid in enumerate(entry_ids, start=start_pos):
            entry = entries_by_id.get(eid)
            if entry is not None:
                entry.queue_position = new_pos
                db.add(entry)

        await db.flush()

    # ------------------------------------------------------------------ #
    # Stale entry recovery                                                 #
    # ------------------------------------------------------------------ #

    async def check_stale_active_entries(
        self,
        db: Any,
        pool: OpportunityScanPool,
        stale_after_hours: int = 4,
    ) -> int:
        """Mark ACTIVE entries that have been running longer than
        ``stale_after_hours`` as 'error'.

        Returns the number of stale entries recovered.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=stale_after_hours)
        stale_result = await db.execute(
            select(OpportunityScanPoolEntry).where(
                OpportunityScanPoolEntry.pool_id == pool.id,
                OpportunityScanPoolEntry.status == "active",
                OpportunityScanPoolEntry.last_activated_at < cutoff,
            )
        )
        stale: list[OpportunityScanPoolEntry] = stale_result.scalars().all()

        for entry in stale:
            logger.warning(
                "scan_queue_rotator: stale active entry pool=%s entry=%s "
                "activated_at=%s — marking error",
                pool.id,
                entry.id,
                entry.last_activated_at,
            )
            entry.status = "error"
            entry.last_scan_status = "timeout"
            db.add(entry)

        if stale:
            await db.flush()

        return len(stale)

    # ------------------------------------------------------------------ #
    # Internal helpers                                                     #
    # ------------------------------------------------------------------ #

    async def _detect_and_complete_finished_entries(
        self, db: Any, pool: OpportunityScanPool
    ) -> int:
        """Poll active entries to see if their schedule job has finished.

        Completion is inferred when the ``HuntScheduleJob.last_run_finished_at``
        is more recent than the entry's ``last_activated_at``.  This is a
        best-effort poll; the authoritative completion path is the Celery
        callback task ``on_pool_scan_complete_task``.
        """
        from ..models.bug_bounty import HuntScheduleJob

        active_result = await db.execute(
            select(OpportunityScanPoolEntry).where(
                OpportunityScanPoolEntry.pool_id == pool.id,
                OpportunityScanPoolEntry.status == "active",
                OpportunityScanPoolEntry.schedule_job_id.isnot(None),
            )
        )
        active_entries: list[OpportunityScanPoolEntry] = active_result.scalars().all()

        completed = 0
        for entry in active_entries:
            try:
                job_result = await db.execute(
                    select(HuntScheduleJob).where(
                        HuntScheduleJob.id == entry.schedule_job_id
                    )
                )
                job: HuntScheduleJob | None = job_result.scalar_one_or_none()
                if job is None:
                    continue

                last_finished = getattr(job, "last_run_finished_at", None)
                if last_finished is None or entry.last_activated_at is None:
                    continue

                if last_finished > entry.last_activated_at:
                    # Job finished after we activated — treat as completed.
                    job_status = getattr(job, "last_run_status", None) or ""
                    success = str(job_status).upper() not in {"FAILED", "ERROR", "TIMEOUT"}
                    await self.complete_entry(db, pool.id, entry.id, success)
                    completed += 1
            except Exception as exc:
                logger.warning(
                    "scan_queue_rotator._detect_finished: entry=%s error: %s",
                    entry.id,
                    exc,
                )

        return completed

    async def _get_pool(
        self, db: Any, pool_id: UUID
    ) -> OpportunityScanPool | None:
        result = await db.execute(
            select(OpportunityScanPool).where(OpportunityScanPool.id == pool_id)
        )
        return result.scalar_one_or_none()

    async def _get_entry(
        self, db: Any, entry_id: UUID
    ) -> OpportunityScanPoolEntry | None:
        result = await db.execute(
            select(OpportunityScanPoolEntry).where(
                OpportunityScanPoolEntry.id == entry_id
            )
        )
        return result.scalar_one_or_none()
