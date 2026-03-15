"""
Human-in-the-Loop Approval API Router
Endpoints for managing approval workflow for reports and emails
"""

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field

from ..core.auth import require_roles, ROLE_ANALYST, ROLE_ADMIN, User
from ..core.hil_approval_system import (
    HiLApprovalSystem,
    ApprovalRequest,
    ApprovalType,
    ApprovalStatus
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/approval",
    tags=["HiL Approval"],
    dependencies=[Depends(require_roles(ROLE_ANALYST, ROLE_ADMIN))]
)


# Global HiL approval system instance
_hil_system: Optional[HiLApprovalSystem] = None


def get_hil_system() -> HiLApprovalSystem:
    """Get global HiL approval system instance"""
    global _hil_system
    if _hil_system is None:
        _hil_system = HiLApprovalSystem()
    return _hil_system


# Request/Response Models

class ApprovalRequestResponse(BaseModel):
    """Approval request response"""
    approval_id: str
    approval_type: str
    status: str
    created_at: str
    title: str
    description: str
    content: Dict[str, Any]
    scan_id: Optional[str] = None
    program_id: Optional[str] = None
    program_name: Optional[str] = None
    approved_by: Optional[str] = None
    approved_at: Optional[str] = None
    rejection_reason: Optional[str] = None
    user_notes: str = ""


class ApprovalListResponse(BaseModel):
    """List of approval requests"""
    approvals: List[ApprovalRequestResponse]
    total_pending: int
    total_approved: int
    total_rejected: int


class ApprovalActionRequest(BaseModel):
    """Request to approve/reject"""
    user_id: str = Field(..., description="User performing the action")
    notes: Optional[str] = Field(None, description="Optional notes from user")


class RejectionRequest(BaseModel):
    """Request to reject approval"""
    user_id: str
    reason: str = Field(..., description="Reason for rejection")


class UpdateDraftRequest(BaseModel):
    """Request to update draft content"""
    content: Dict[str, Any] = Field(..., description="Updated draft content")
    notes: Optional[str] = Field(None, description="Update notes")


def _to_response(approval: ApprovalRequest) -> ApprovalRequestResponse:
    """Convert ApprovalRequest to response model"""
    return ApprovalRequestResponse(
        approval_id=approval.approval_id,
        approval_type=approval.approval_type.value,
        status=approval.status.value,
        created_at=approval.created_at.isoformat(),
        title=approval.title,
        description=approval.description,
        content=approval.content,
        scan_id=approval.scan_id,
        program_id=approval.program_id,
        program_name=approval.program_name,
        approved_by=approval.approved_by,
        approved_at=approval.approved_at.isoformat() if approval.approved_at else None,
        rejection_reason=approval.rejection_reason,
        user_notes=approval.user_notes
    )


# Endpoints

@router.get("/pending", response_model=ApprovalListResponse)
async def list_pending_approvals():
    """
    Get all pending approval requests

    Returns list of approval requests awaiting user review.
    """
    hil_system = get_hil_system()

    pending = list(hil_system.pending_approvals.values())
    approved = [a for a in hil_system.approval_history if a.status == ApprovalStatus.APPROVED]
    rejected = [a for a in hil_system.approval_history if a.status == ApprovalStatus.REJECTED]

    return ApprovalListResponse(
        approvals=[_to_response(a) for a in pending],
        total_pending=len(pending),
        total_approved=len(approved),
        total_rejected=len(rejected)
    )


@router.get("/all", response_model=ApprovalListResponse)
async def list_all_approvals(
    status_filter: Optional[str] = None,
    approval_type: Optional[str] = None,
    limit: int = 100
):
    """
    Get all approval requests (pending + history)

    Args:
        status_filter: Filter by status (pending, approved, rejected)
        approval_type: Filter by type (report_submission, email_reply)
        limit: Maximum number of results
    """
    hil_system = get_hil_system()

    # Combine pending and history
    all_approvals = list(hil_system.pending_approvals.values()) + hil_system.approval_history

    # Apply filters
    if status_filter:
        all_approvals = [a for a in all_approvals if a.status.value == status_filter]

    if approval_type:
        all_approvals = [a for a in all_approvals if a.approval_type.value == approval_type]

    # Sort by created_at descending
    all_approvals.sort(key=lambda x: x.created_at, reverse=True)

    # Apply limit
    all_approvals = all_approvals[:limit]

    # Count by status
    pending_count = sum(1 for a in all_approvals if a.status == ApprovalStatus.PENDING)
    approved_count = sum(1 for a in all_approvals if a.status == ApprovalStatus.APPROVED)
    rejected_count = sum(1 for a in all_approvals if a.status == ApprovalStatus.REJECTED)

    return ApprovalListResponse(
        approvals=[_to_response(a) for a in all_approvals],
        total_pending=pending_count,
        total_approved=approved_count,
        total_rejected=rejected_count
    )


@router.get("/{approval_id}", response_model=ApprovalRequestResponse)
async def get_approval(approval_id: str):
    """
    Get specific approval request details

    Args:
        approval_id: Approval request ID
    """
    hil_system = get_hil_system()

    # Check pending first
    if approval_id in hil_system.pending_approvals:
        return _to_response(hil_system.pending_approvals[approval_id])

    # Check history
    for approval in hil_system.approval_history:
        if approval.approval_id == approval_id:
            return _to_response(approval)

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Approval request {approval_id} not found"
    )


@router.post("/{approval_id}/approve", response_model=ApprovalRequestResponse)
async def approve_request(
    approval_id: str,
    request: ApprovalActionRequest,
    current_user: User = Depends(require_roles(ROLE_ANALYST, ROLE_ADMIN))
):
    """
    Approve an approval request

    Args:
        approval_id: Approval request ID
        request: Approval action details

    IMPORTANT: After approving, user must manually send the email or submit
    the report. This endpoint only marks the draft as approved.
    """
    hil_system = get_hil_system()

    try:
        approval = await hil_system.approve(
            approval_id=approval_id,
            user_id=current_user.id
        )

        # Update notes if provided
        if request.notes:
            approval.user_notes = request.notes

        logger.info(f"Approval {approval_id} approved by {current_user.id}")
        logger.info(f"⚠️  User must now manually send email or submit report")

        return _to_response(approval)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error approving request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve request: {str(e)}"
        )


@router.post("/{approval_id}/reject", response_model=ApprovalRequestResponse)
async def reject_request(
    approval_id: str,
    request: RejectionRequest,
    current_user: User = Depends(require_roles(ROLE_ANALYST, ROLE_ADMIN))
):
    """
    Reject an approval request

    Args:
        approval_id: Approval request ID
        request: Rejection details with reason
    """
    hil_system = get_hil_system()

    try:
        approval = await hil_system.reject(
            approval_id=approval_id,
            user_id=current_user.id,
            reason=request.reason
        )

        logger.info(f"Approval {approval_id} rejected by {current_user.id}: {request.reason}")

        return _to_response(approval)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error rejecting request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reject request: {str(e)}"
        )


@router.put("/{approval_id}/update", response_model=ApprovalRequestResponse)
async def update_draft(approval_id: str, request: UpdateDraftRequest):
    """
    Update draft content before approval

    Allows user to edit draft email or report content before approving.

    Args:
        approval_id: Approval request ID
        request: Updated content and notes
    """
    hil_system = get_hil_system()

    try:
        approval = await hil_system.update_draft(
            approval_id=approval_id,
            updated_content=request.content
        )

        if request.notes:
            approval.user_notes = request.notes
            approval.user_edits["update_notes"] = request.notes

        logger.info(f"Draft content updated for approval {approval_id}")

        return _to_response(approval)

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating draft: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update draft: {str(e)}"
        )


@router.delete("/{approval_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_approval(approval_id: str):
    """
    Cancel a pending approval request

    Args:
        approval_id: Approval request ID
    """
    hil_system = get_hil_system()

    if approval_id not in hil_system.pending_approvals:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approval request {approval_id} not found or already processed"
        )

    approval = hil_system.pending_approvals[approval_id]
    approval.status = ApprovalStatus.CANCELLED

    # Move to history
    del hil_system.pending_approvals[approval_id]
    hil_system.approval_history.append(approval)

    logger.info(f"Approval {approval_id} cancelled")


@router.get("/stats/summary")
async def get_approval_stats():
    """
    Get approval system statistics

    Returns summary stats about approval requests.
    """
    hil_system = get_hil_system()

    all_approvals = list(hil_system.pending_approvals.values()) + hil_system.approval_history

    stats = {
        "total_requests": len(all_approvals),
        "pending": len(hil_system.pending_approvals),
        "approved": sum(1 for a in hil_system.approval_history if a.status == ApprovalStatus.APPROVED),
        "rejected": sum(1 for a in hil_system.approval_history if a.status == ApprovalStatus.REJECTED),
        "cancelled": sum(1 for a in hil_system.approval_history if a.status == ApprovalStatus.CANCELLED),
        "by_type": {
            "report_submission": sum(1 for a in all_approvals if a.approval_type == ApprovalType.REPORT_SUBMISSION),
            "email_reply": sum(1 for a in all_approvals if a.approval_type == ApprovalType.EMAIL_REPLY),
        },
        "oldest_pending": None,
        "newest_pending": None
    }

    # Find oldest and newest pending
    pending_list = list(hil_system.pending_approvals.values())
    if pending_list:
        pending_list.sort(key=lambda x: x.created_at)
        stats["oldest_pending"] = {
            "approval_id": pending_list[0].approval_id,
            "created_at": pending_list[0].created_at.isoformat(),
            "title": pending_list[0].title
        }
        stats["newest_pending"] = {
            "approval_id": pending_list[-1].approval_id,
            "created_at": pending_list[-1].created_at.isoformat(),
            "title": pending_list[-1].title
        }

    return stats
