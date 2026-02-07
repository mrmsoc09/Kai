"""
Human-in-the-Loop (HiL) Approval System
Manages approval gates for report submissions and email communications
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class ApprovalType(str, Enum):
    """Types of items requiring approval"""
    REPORT_SUBMISSION = "report_submission"
    EMAIL_REPLY = "email_reply"
    EMAIL_INITIAL = "email_initial"  # Never used - kept for reference
    FINDING_DISCLOSURE = "finding_disclosure"


class ApprovalStatus(str, Enum):
    """Approval status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


@dataclass
class ApprovalRequest:
    """Request for human approval"""
    approval_id: str
    approval_type: ApprovalType
    status: ApprovalStatus
    created_at: datetime

    # Content requiring approval
    title: str
    description: str
    content: Dict[str, Any]  # Draft email, report, etc.

    # Context
    scan_id: Optional[str] = None
    program_id: Optional[str] = None
    program_name: Optional[str] = None

    # Approval details
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

    # User notes/edits
    user_notes: str = ""
    user_edits: Dict[str, Any] = field(default_factory=dict)


class HiLApprovalSystem:
    """
    Human-in-the-Loop Approval System

    Manages approval workflow for:
    1. Report Submissions - User must approve before submitting to BBP platform
    2. Email Replies - User must approve draft replies before sending
    3. Finding Disclosures - User must approve sensitive information release

    IMPORTANT: Platform NEVER sends emails automatically. It only:
    - Creates draft emails ready for user review
    - Queues drafts for user approval
    - Sends only after explicit user approval
    """

    def __init__(self):
        """Initialize HiL approval system"""
        self.pending_approvals: Dict[str, ApprovalRequest] = {}
        self.approval_history: List[ApprovalRequest] = []

        logger.info("✓ HiLApprovalSystem initialized")

    async def request_report_submission_approval(
        self,
        scan_id: str,
        program_id: str,
        program_name: str,
        report_content: Dict[str, Any],
        submission_platform: str  # "hackerone", "bugcrowd", etc.
    ) -> ApprovalRequest:
        """
        Request approval to submit report to BBP platform

        Args:
            scan_id: Scan ID
            program_id: BBP program ID
            program_name: Program name
            report_content: Complete report ready for submission
            submission_platform: Target platform

        Returns:
            ApprovalRequest in PENDING status
        """

        approval_id = str(uuid.uuid4())

        request = ApprovalRequest(
            approval_id=approval_id,
            approval_type=ApprovalType.REPORT_SUBMISSION,
            status=ApprovalStatus.PENDING,
            created_at=datetime.utcnow(),
            title=f"Report Submission: {program_name}",
            description=f"Review and approve security findings report for submission to {submission_platform}",
            content={
                "report": report_content,
                "submission_platform": submission_platform,
                "findings_count": report_content.get("findings_count", 0),
                "severity_breakdown": report_content.get("severity_breakdown", {})
            },
            scan_id=scan_id,
            program_id=program_id,
            program_name=program_name
        )

        self.pending_approvals[approval_id] = request

        logger.info(f"📋 Report submission approval requested: {approval_id}")
        logger.info(f"Program: {program_name}, Platform: {submission_platform}")
        logger.info(f"Findings: {report_content.get('findings_count', 0)}")

        return request

    async def request_email_reply_approval(
        self,
        scan_id: str,
        program_id: str,
        program_name: str,
        incoming_email: Dict[str, Any],
        draft_reply: Dict[str, Any]
    ) -> ApprovalRequest:
        """
        Request approval to send email reply

        Platform monitors incoming emails from stakeholders and generates
        draft replies. User reviews, approves, and manually sends.

        Args:
            scan_id: Scan ID
            program_id: Program ID
            program_name: Program name
            incoming_email: Original email from stakeholder
            draft_reply: Generated draft reply

        Returns:
            ApprovalRequest in PENDING status
        """

        approval_id = str(uuid.uuid4())

        request = ApprovalRequest(
            approval_id=approval_id,
            approval_type=ApprovalType.EMAIL_REPLY,
            status=ApprovalStatus.PENDING,
            created_at=datetime.utcnow(),
            title=f"Email Reply: {program_name}",
            description=f"Review draft reply to stakeholder inquiry about {incoming_email.get('subject', 'vulnerability')}",
            content={
                "incoming_email": incoming_email,
                "draft_reply": draft_reply,
                "reply_to": incoming_email.get("from"),
                "subject": draft_reply.get("subject"),
                "body_preview": draft_reply.get("body", "")[:200]
            },
            scan_id=scan_id,
            program_id=program_id,
            program_name=program_name
        )

        self.pending_approvals[approval_id] = request

        logger.info(f"📧 Email reply approval requested: {approval_id}")
        logger.info(f"Reply to: {incoming_email.get('from')}")
        logger.info(f"Subject: {draft_reply.get('subject')}")

        return request

    async def approve(
        self,
        approval_id: str,
        user_id: str,
        user_notes: Optional[str] = None,
        user_edits: Optional[Dict[str, Any]] = None
    ) -> ApprovalRequest:
        """
        Approve a pending request

        Args:
            approval_id: Approval ID
            user_id: User approving
            user_notes: Optional user notes
            user_edits: Optional user edits to content

        Returns:
            Updated ApprovalRequest
        """

        if approval_id not in self.pending_approvals:
            raise ValueError(f"Approval {approval_id} not found")

        request = self.pending_approvals[approval_id]

        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Approval {approval_id} is not pending (status: {request.status})")

        # Update request
        request.status = ApprovalStatus.APPROVED
        request.approved_by = user_id
        request.approved_at = datetime.utcnow()

        if user_notes:
            request.user_notes = user_notes

        if user_edits:
            request.user_edits = user_edits
            # Apply user edits to content
            request.content.update(user_edits)

        # Move to history
        self.approval_history.append(request)
        del self.pending_approvals[approval_id]

        logger.info(f"✅ Approval granted: {approval_id} by {user_id}")

        return request

    async def reject(
        self,
        approval_id: str,
        user_id: str,
        reason: str
    ) -> ApprovalRequest:
        """
        Reject a pending request

        Args:
            approval_id: Approval ID
            user_id: User rejecting
            reason: Rejection reason

        Returns:
            Updated ApprovalRequest
        """

        if approval_id not in self.pending_approvals:
            raise ValueError(f"Approval {approval_id} not found")

        request = self.pending_approvals[approval_id]

        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Approval {approval_id} is not pending")

        # Update request
        request.status = ApprovalStatus.REJECTED
        request.approved_by = user_id
        request.approved_at = datetime.utcnow()
        request.rejection_reason = reason

        # Move to history
        self.approval_history.append(request)
        del self.pending_approvals[approval_id]

        logger.info(f"❌ Approval rejected: {approval_id} by {user_id}")
        logger.info(f"Reason: {reason}")

        return request

    async def update_draft(
        self,
        approval_id: str,
        updated_content: Dict[str, Any]
    ) -> ApprovalRequest:
        """
        Update draft content (user makes edits before approval)

        Args:
            approval_id: Approval ID
            updated_content: Updated content

        Returns:
            Updated ApprovalRequest
        """

        if approval_id not in self.pending_approvals:
            raise ValueError(f"Approval {approval_id} not found")

        request = self.pending_approvals[approval_id]
        request.content.update(updated_content)
        request.user_edits.update(updated_content)

        logger.info(f"📝 Draft updated: {approval_id}")

        return request

    def get_pending_approvals(
        self,
        approval_type: Optional[ApprovalType] = None
    ) -> List[ApprovalRequest]:
        """
        Get all pending approvals, optionally filtered by type

        Args:
            approval_type: Optional filter by type

        Returns:
            List of pending ApprovalRequests
        """

        approvals = list(self.pending_approvals.values())

        if approval_type:
            approvals = [a for a in approvals if a.approval_type == approval_type]

        # Sort by created_at (oldest first)
        approvals.sort(key=lambda a: a.created_at)

        return approvals

    def get_approval(self, approval_id: str) -> Optional[ApprovalRequest]:
        """Get specific approval request"""

        # Check pending
        if approval_id in self.pending_approvals:
            return self.pending_approvals[approval_id]

        # Check history
        for request in self.approval_history:
            if request.approval_id == approval_id:
                return request

        return None

    def get_approval_history(
        self,
        limit: int = 100,
        approval_type: Optional[ApprovalType] = None
    ) -> List[ApprovalRequest]:
        """
        Get approval history

        Args:
            limit: Maximum number of records
            approval_type: Optional filter by type

        Returns:
            List of historical ApprovalRequests
        """

        history = self.approval_history.copy()

        if approval_type:
            history = [a for a in history if a.approval_type == approval_type]

        # Sort by approved_at (most recent first)
        history.sort(key=lambda a: a.approved_at or a.created_at, reverse=True)

        return history[:limit]

    def get_stats(self) -> Dict[str, Any]:
        """Get approval system statistics"""

        return {
            "pending_count": len(self.pending_approvals),
            "pending_by_type": {
                approval_type.value: sum(
                    1 for a in self.pending_approvals.values()
                    if a.approval_type == approval_type
                )
                for approval_type in ApprovalType
            },
            "total_approved": sum(
                1 for a in self.approval_history
                if a.status == ApprovalStatus.APPROVED
            ),
            "total_rejected": sum(
                1 for a in self.approval_history
                if a.status == ApprovalStatus.REJECTED
            ),
            "approval_rate": (
                sum(1 for a in self.approval_history if a.status == ApprovalStatus.APPROVED) /
                len(self.approval_history)
            ) if self.approval_history else 0.0
        }


# Global instance
_hil_system: Optional[HiLApprovalSystem] = None


def get_hil_system() -> HiLApprovalSystem:
    """Get global HiL approval system instance"""
    global _hil_system
    if _hil_system is None:
        _hil_system = HiLApprovalSystem()
    return _hil_system
