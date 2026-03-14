"""Simple approval router to gate intrusive tools."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from apps.backend.src.core.tool_runner import tool_runner
from apps.backend.src.core.tools import get_registry, initialize_default_tools
from apps.backend.src.core.kai_security_guardrails import get_tool_tier, ToolRiskTier


router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalRequest(BaseModel):
    tool_id: str
    run_id: str | None = None
    approved: bool
    approver: str
    note: str | None = None


@router.get("/tools")
def list_intrusive_tools():
    """List tools that require approval."""
    initialize_default_tools()
    reg = get_registry()
    items = []
    for tool in reg.list_all():
        tid = tool.id
        if get_tool_tier(tid) == ToolRiskTier.TIER_2_INTRUSIVE:
            items.append({"id": tid, "name": tool.name, "description": tool.description})
    return {"tools": items}


@router.post("/tool-run")
def approve_tool_run(payload: ApprovalRequest):
    """Approve or reject a specific tool run id or blanket tool id."""
    initialize_default_tools()
    reg = get_registry()
    tool = reg.get(payload.tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="tool not found")

    if not payload.approved:
        raise HTTPException(status_code=403, detail="run rejected by approver")

    # In this simplified model we just acknowledge approval; caller passes `approved=True` when enqueuing.
    return {
        "tool_id": payload.tool_id,
        "run_id": payload.run_id,
        "approved": True,
        "approver": payload.approver,
        "note": payload.note,
    }
