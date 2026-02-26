"""Task submission endpoints for Celery-backed tool runs."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..worker.celery_app import run_tool_task
from ..core.tool_runner import tool_runner
from ..core.tools import get_registry, initialize_default_tools
from ..core.kai_security_guardrails import get_tool_tier, ToolRiskTier


class TaskRequest(BaseModel):
    tool_id: str = Field(..., description="Registered tool ID")
    params: dict = Field(default_factory=dict, description="Tool parameters")
    approved: bool = Field(default=False, description="Set true if approval was granted")


router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])


@router.post("/enqueue")
async def enqueue_task(req: TaskRequest):
    initialize_default_tools()
    registry = get_registry()
    tool = registry.get(req.tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {req.tool_id}")

    # Require approval for intrusive tools by default
    risk_tier = get_tool_tier(req.tool_id)
    require_approval = risk_tier == ToolRiskTier.TIER_2_INTRUSIVE

    task_id = tool_runner.enqueue(
        req.tool_id,
        req.params,
        require_approval=require_approval,
        approved=req.approved,
    )
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
