"""Campaign orchestration worker tasks."""
from __future__ import annotations

import asyncio
from uuid import UUID

from ..core.bug_bounty_hunting_service import BugBountyHuntingService
from ..core.execution_result_service import ingest_worker_result_sync, mark_worker_execution_running_sync
from ..core.hil_db import get_async_session_maker
from ..models.enums import ToolExecutionStatusEnum
from .celery_app import celery_app


@celery_app.task(name="campaign_phase_placeholder", bind=True)
def run_phase_job_placeholder_task(
    self,
    *,
    campaign_id: str,
    branch_id: str,
    phase_job_id: str,
    phase_name: str,
    payload: dict | None = None,
) -> dict:
    """Placeholder worker execution used until a concrete tool mapping is configured."""
    task_id = getattr(self.request, "id", "")
    retry_attempt = int(getattr(self.request, "retries", 0) or 0)
    running_update = None
    if task_id:
        running_update = mark_worker_execution_running_sync(
            worker_task_id=task_id,
            actor="worker.campaign.placeholder",
        )

    result = {
        "status": "queued_placeholder",
        "campaign_id": campaign_id,
        "branch_id": branch_id,
        "phase_job_id": phase_job_id,
        "phase_name": phase_name,
        "payload": payload or {},
        "note": "No concrete tool mapping configured for this phase yet.",
        "retry_attempt": retry_attempt,
        "worker_task_id": task_id or None,
        "running_update": running_update,
    }
    try:
        if task_id:
            ingest_outcome = ingest_worker_result_sync(
                worker_task_id=task_id,
                tool_status=ToolExecutionStatusEnum.COMPLETED,
                result_payload_json=result,
                actor="worker.campaign.placeholder",
            )
            result["ingest_outcome"] = ingest_outcome
    except Exception as exc:
        result["status"] = "failed"
        result["error"] = str(exc)
        if task_id:
            ingest_worker_result_sync(
                worker_task_id=task_id,
                tool_status=ToolExecutionStatusEnum.FAILED,
                result_payload_json=result,
                error_message=str(exc),
                actor="worker.campaign.placeholder",
            )
        raise
    return result


async def _trigger_bug_bounty_schedule_async(
    *,
    schedule_id: str,
    actor: str,
    worker_role: str,
    force: bool,
) -> dict:
    session_maker = get_async_session_maker()
    async with session_maker() as db:
        svc = BugBountyHuntingService(db)
        response = await svc.trigger_schedule(
            UUID(schedule_id),
            actor=actor,
            force=force,
            trigger_source=f"worker.{worker_role}",
        )
        await db.commit()
        return response.model_dump()


@celery_app.task(name="bug_bounty_schedule_run", bind=True)
def run_bug_bounty_schedule_task(
    self,
    *,
    schedule_id: str,
    actor: str = "worker.bugbounty.scheduler",
    worker_role: str = "recon_worker",
    force: bool = False,
) -> dict:
    """Execute one canonical bug bounty schedule from Celery worker context."""
    _ = self
    return asyncio.run(
        _trigger_bug_bounty_schedule_async(
            schedule_id=schedule_id,
            actor=actor,
            worker_role=worker_role,
            force=force,
        )
    )
