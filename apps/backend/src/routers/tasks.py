"""Task submission endpoints for Celery-backed tool runs."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from apps.backend.src.worker.celery_app import run_tool_task
from apps.backend.src.core.tool_runner import tool_runner
from apps.backend.src.core.tools import get_registry, initialize_default_tools


class TaskRequest(BaseModel):
    tool_id: str = Field(..., description="Registered tool ID")
    params: dict = Field(default_factory=dict, description="Tool parameters")


router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])


@router.post("/enqueue")
async def enqueue_task(req: TaskRequest):
    initialize_default_tools()
    registry = get_registry()
    tool = registry.get(req.tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {req.tool_id}")

    task_id = tool_runner.enqueue(req.tool_id, req.params, require_approval=False)
    return {"task_id": task_id, "status": "queued"}


@router.get("/{task_id}")
async def task_status(task_id: str):
    res = run_tool_task.AsyncResult(task_id)
    if res.state == "PENDING":
        return {"task_id": task_id, "status": "pending"}
    if res.state == "FAILURE":
        return {"task_id": task_id, "status": "failed", "error": str(res.info)}
    if res.state == "SUCCESS":
        return {"task_id": task_id, "status": "completed", "result": res.result}
    return {"task_id": task_id, "status": res.state.lower()}
