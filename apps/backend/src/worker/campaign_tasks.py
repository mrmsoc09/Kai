"""Campaign orchestration worker tasks."""
from __future__ import annotations

from ..core.execution_result_service import ingest_worker_result_sync, mark_worker_execution_running_sync
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
    if task_id:
        mark_worker_execution_running_sync(
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
    }
    if task_id:
        ingest_worker_result_sync(
            worker_task_id=task_id,
            tool_status=ToolExecutionStatusEnum.COMPLETED,
            result_payload_json=result,
            actor="worker.campaign.placeholder",
        )
    return result
