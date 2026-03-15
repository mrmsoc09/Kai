"""Task submission endpoints for Celery-backed tool runs."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from ..worker.celery_app import run_tool_task
from ..core.tool_runner import tool_runner
from ..core.tools import get_registry, initialize_default_tools
from ..core.kai_security_guardrails import get_tool_tier, ToolRiskTier
from ..core.hil_db import get_db
from ..core.approval_gate_service import ApprovalGateService
from ..models.enums import ApprovalGateStatusEnum
from ..models.campaign import ApprovalGate


class TaskRequest(BaseModel):
    tool_id: str = Field(..., description="Registered tool ID")
    params: dict = Field(default_factory=dict, description="Tool parameters")


router = APIRouter(prefix="/api/v1/tasks", tags=["Tasks"])


@router.post("/enqueue")
async def enqueue_task(req: TaskRequest, db: AsyncSession = Depends(get_db)):
    initialize_default_tools()
    registry = get_registry()
    tool = registry.get(req.tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {req.tool_id}")

    # Require approval for intrusive tools by default
    risk_tier = get_tool_tier(req.tool_id)
    require_approval = risk_tier == ToolRiskTier.TIER_2_INTRUSIVE
    
    approved = False
    if require_approval:
        # Tool execution approval state must be read exclusively from ApprovalGate
        run_id = req.params.get("run_id")
        if not run_id:
             raise HTTPException(status_code=403, detail="run_id required for Tier 2 tools to verify approval")
        
        try:
            run_uuid = UUID(run_id)
            stmt = select(ApprovalGate).where(
                ApprovalGate.campaign_id == run_uuid,
                ApprovalGate.status == ApprovalGateStatusEnum.APPROVED
            )
            result = await db.execute(stmt)
            if result.scalars().first():
                approved = True
        except ValueError:
             raise HTTPException(status_code=400, detail="Invalid run_id format")

    if require_approval and not approved:
        raise HTTPException(status_code=403, detail="Tier 2 tool execution requires an approved ApprovalGate record")

    task_id = tool_runner.enqueue(
        req.tool_id,
        req.params,
        require_approval=require_approval,
        approved=approved,
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
