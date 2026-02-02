"""
Human-in-the-Loop Approval API Router
Exposes approval request, decision, and audit endpoints
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio

router = APIRouter(prefix="/api/approvals", tags=["approvals"])

# Module-level cache for systems
_hil_workflow = None


def set_hil_workflow(workflow):
    """Set HiL approval workflow reference from main.py"""
    global _hil_workflow
    _hil_workflow = workflow


def get_hil_workflow():
    """Get HiL workflow with fallback import"""
    global _hil_workflow

    if _hil_workflow is None:
        try:
            from apps.backend.src.core.approval_workflow import get_hil_approval_workflow
            _hil_workflow = get_hil_approval_workflow()
        except:
            raise HTTPException(status_code=500, detail="HiL approval workflow not initialized")

    return _hil_workflow


# ==================== Request/Response Models ====================

class ApprovalRequestModel(BaseModel):
    """Request approval for an action"""
    action_id: str
    target_domain: str
    action_type: str
    description: str
    risk_level: str
    requires_pgp: bool = True
    metadata: Optional[Dict[str, Any]] = None


class ApprovalDecisionModel(BaseModel):
    """Approve or reject an action"""
    approval_id: str
    admin_id: str
    decision: str  # approved or rejected
    pgp_signature: Optional[str] = None
    justification: str = ""


class ApprovalEscalationModel(BaseModel):
    """Escalate an approval request"""
    approval_id: str
    escalation_reason: str = ""
    escalate_to_admins: Optional[List[str]] = None


# ==================== Approval Request ====================

@router.post("/request", response_model=Dict[str, Any])
async def request_approval(request: ApprovalRequestModel):
    """Create an approval request for a high-risk action"""
    workflow = get_hil_workflow()

    try:
        success, message, approval_id = await workflow.request_approval(
            action_id=request.action_id,
            target_domain=request.target_domain,
            action_type=request.action_type,
            description=request.description,
            risk_level=request.risk_level,
            requires_pgp=request.requires_pgp,
            metadata=request.metadata
        )

        if not success:
            raise HTTPException(status_code=400, detail=message)

        return {
            "success": True,
            "approval_id": approval_id,
            "message": message,
            "requires_pgp": request.requires_pgp,
            "expires_in_hours": 24
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Request failed: {str(e)}")


@router.post("/decide", response_model=Dict[str, Any])
async def make_approval_decision(request: ApprovalDecisionModel):
    """Approve or reject an action (with optional PGP signature)"""
    workflow = get_hil_workflow()

    try:
        if request.decision == "approved":
            success, message, decision = await workflow.approve_action(
                approval_id=request.approval_id,
                admin_id=request.admin_id,
                pgp_signature=request.pgp_signature,
                justification=request.justification
            )
        elif request.decision == "rejected":
            success, message, decision = await workflow.reject_action(
                approval_id=request.approval_id,
                admin_id=request.admin_id,
                reason=request.justification,
                pgp_signature=request.pgp_signature
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid decision: must be 'approved' or 'rejected'")

        if not success:
            raise HTTPException(status_code=400, detail=message)

        return {
            "success": True,
            "decision": request.decision,
            "admin_id": request.admin_id,
            "signed": bool(request.pgp_signature),
            "signed_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decision failed: {str(e)}")


@router.get("/pending", response_model=List[Dict[str, Any]])
async def get_pending_approvals():
    """Get list of pending approval requests"""
    workflow = get_hil_workflow()

    try:
        pending = workflow.get_pending_approvals()
        return pending

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")


@router.get("/{approval_id}/status", response_model=Dict[str, Any])
async def get_approval_status(approval_id: str):
    """Get status of an approval request"""
    workflow = get_hil_workflow()

    try:
        # Check if pending
        pending_ids = [a["approval_id"] for a in workflow.get_pending_approvals()]
        if approval_id in pending_ids:
            return {
                "approval_id": approval_id,
                "status": "pending",
                "decision": None,
                "expires_at": None
            }

        # Check if decided
        decision = workflow.get_approval_decision(approval_id)
        if decision:
            return {
                "approval_id": approval_id,
                "status": "decided",
                "decision": decision["decision"],
                "admin_id": decision["admin_id"],
                "signed_at": decision["signed_at"]
            }

        raise HTTPException(status_code=404, detail="Approval request not found")

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Status check failed: {str(e)}")


# ==================== Escalation ====================

@router.post("/{approval_id}/escalate", response_model=Dict[str, Any])
async def escalate_approval(approval_id: str, request: ApprovalEscalationModel):
    """Escalate approval to senior admins"""
    workflow = get_hil_workflow()

    try:
        success, message = await workflow.escalate_approval(
            approval_id=request.approval_id,
            escalation_reason=request.escalation_reason,
            escalate_to_admins=request.escalate_to_admins
        )

        if not success:
            raise HTTPException(status_code=400, detail=message)

        return {
            "success": True,
            "approval_id": approval_id,
            "message": message,
            "escalated_at": datetime.utcnow().isoformat()
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Escalation failed: {str(e)}")


# ==================== Audit & History ====================

@router.get("/history/{approval_id}", response_model=Dict[str, Any])
async def get_approval_history(approval_id: str):
    """Get complete history of an approval"""
    workflow = get_hil_workflow()

    try:
        decision = workflow.get_approval_decision(approval_id)

        if not decision:
            raise HTTPException(status_code=404, detail="No approval history found")

        return decision

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"History retrieval failed: {str(e)}")


@router.get("/audit-trail", response_model=List[Dict[str, Any]])
async def get_approval_audit_trail(
    event_type: Optional[str] = None,
    limit: int = 100
):
    """Get complete audit trail of all approval decisions"""
    workflow = get_hil_workflow()

    try:
        audit = workflow.get_approval_audit_trail()

        if event_type:
            audit = [a for a in audit if a.get("event_type") == event_type]

        return audit[-limit:]

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audit retrieval failed: {str(e)}")


# ==================== Dashboard ====================

@router.get("/dashboard/summary", response_model=Dict[str, Any])
async def get_approval_summary():
    """Get approval workflow summary"""
    workflow = get_hil_workflow()

    try:
        pending = workflow.get_pending_approvals()
        audit = workflow.get_approval_audit_trail()

        approved_count = len([a for a in audit if a.get("event_type") == "approval_granted"])
        rejected_count = len([a for a in audit if a.get("event_type") == "approval_rejected"])
        escalated_count = len([a for a in audit if a.get("event_type") == "approval_escalated"])

        # Calculate average decision time
        decision_times = []
        for event in audit:
            if event.get("event_type") in ["approval_granted", "approval_rejected"]:
                # Would need timestamp correlation in production
                decision_times.append(1)  # Placeholder

        avg_decision_time = sum(decision_times) / len(decision_times) if decision_times else 0

        return {
            "pending_count": len(pending),
            "approved_count": approved_count,
            "rejected_count": rejected_count,
            "escalated_count": escalated_count,
            "total_decisions": approved_count + rejected_count,
            "average_decision_time_minutes": avg_decision_time,
            "approval_rate": (approved_count / (approved_count + rejected_count) * 100) if (approved_count + rejected_count) > 0 else 0,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summary failed: {str(e)}")
