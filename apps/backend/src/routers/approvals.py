"""Simple approval router to gate intrusive tools."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from apps.backend.src.core.tool_runner import tool_runner
from apps.backend.src.core.tools import get_registry, initialize_default_tools
from apps.backend.src.core.kai_security_guardrails import get_tool_tier, ToolRiskTier
from apps.backend.src.core.auth import require_roles, ROLE_ANALYST, ROLE_ADMIN, User
from apps.backend.src.core.hil_db import get_db
from apps.backend.src.core.approval_gate_service import ApprovalGateService
from apps.backend.src.models.enums import ApprovalGateStatusEnum
from apps.backend.src.schemas.campaigns import ApprovalGateDecision


router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalRequest(BaseModel):
    tool_id: str
    run_id: str | None = None
    approved: bool
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
async def approve_tool_run(
    payload: ApprovalRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(ROLE_ANALYST, ROLE_ADMIN))
):
    """Approve or reject a specific tool run id or blanket tool id."""
    initialize_default_tools()
    reg = get_registry()
    tool = reg.get(payload.tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="tool not found")

    if not payload.approved:
        raise HTTPException(status_code=403, detail="run rejected by approver")

    # Persist the approval decision to the database
    if payload.run_id:
        try:
            run_uuid = UUID(payload.run_id)
            gate_service = ApprovalGateService(db)
            # Find pending gates for this campaign/run
            gates = await gate_service.list_pending_for_campaign(run_uuid)
            
            if gates:
                decision = ApprovalGateDecision(
                    status=ApprovalGateStatusEnum.APPROVED,
                    decided_by=current_user.id,
                    operator_notes=payload.note
                )
                for gate in gates:
                    await gate_service.decide_gate(gate, decision)
                await db.commit()
        except ValueError:
            pass # Invalid UUID

    return {
        "tool_id": payload.tool_id,
        "run_id": payload.run_id,
        "approved": True,
        "approver": current_user.id,
        "note": payload.note,
    }
