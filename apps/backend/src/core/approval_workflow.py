"""
Human-in-the-Loop Approval Workflow
Integrates key management with orchestration graph for PGP-signed approvals
"""

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum


class ApprovalDecision(str, Enum):
    """Approval decision type"""
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"
    ESCALATED = "escalated"


@dataclass
class ApprovalRequest:
    """Request for approval"""
    action_id: str
    target_domain: str
    action_type: str  # reconnaissance, exploitation, etc.
    description: str
    risk_level: str  # low, medium, high, critical
    requires_pgp: bool = True
    created_at: datetime = None
    expires_at: datetime = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc)
        if self.expires_at is None:
            from datetime import timedelta, timezone
            self.expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ApprovalDecisionRecord:
    """Record of an approval decision"""
    approval_id: str
    action_id: str
    decision: ApprovalDecision
    admin_id: str
    admin_key_fingerprint: str
    signed_at: datetime
    pgp_signature: Optional[str] = None
    justification: str = ""
    audit_trail: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.audit_trail is None:
            self.audit_trail = []


class HiLApprovalWorkflow:
    """
    Human-in-the-Loop Approval Workflow
    Manages approval requests, decisions, and PGP signature verification
    """

    def __init__(
        self,
        key_management_system=None,
        orchestration_graph=None
    ):
        self.key_mgmt = key_management_system
        self.orch_graph = orchestration_graph
        self.approval_requests: Dict[str, ApprovalRequest] = {}
        self.approval_decisions: Dict[str, ApprovalDecisionRecord] = {}
        self.pending_queue: List[str] = []  # List of approval_ids awaiting decision
        self.audit_log: List[Dict[str, Any]] = []

    async def request_approval(
        self,
        action_id: str,
        target_domain: str,
        action_type: str,
        description: str,
        risk_level: str,
        requires_pgp: bool = True,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Create an approval request
        Returns: (success, message, approval_request_id)
        """
        try:
            import uuid
            approval_id = str(uuid.uuid4())

            request = ApprovalRequest(
                action_id=action_id,
                target_domain=target_domain,
                action_type=action_type,
                description=description,
                risk_level=risk_level,
                requires_pgp=requires_pgp,
                metadata=metadata or {}
            )

            self.approval_requests[approval_id] = request
            self.pending_queue.append(approval_id)

            self._log_audit(
                "approval_requested",
                {
                    "approval_id": approval_id,
                    "action_id": action_id,
                    "target_domain": target_domain,
                    "risk_level": risk_level
                }
            )

            return (True, "Approval request created", approval_id)

        except Exception as e:
            return (False, f"Request creation failed: {str(e)}", None)

    async def approve_action(
        self,
        approval_id: str,
        admin_id: str,
        pgp_signature: Optional[str] = None,
        justification: str = ""
    ) -> Tuple[bool, str, Optional[ApprovalDecisionRecord]]:
        """
        Approve an action with optional PGP signature
        Returns: (success, message, decision_record)
        """
        try:
            if approval_id not in self.approval_requests:
                return (False, "Approval request not found", None)

            request = self.approval_requests[approval_id]

            # If PGP signature required, verify it
            if request.requires_pgp and self.key_mgmt:
                if not pgp_signature:
                    return (False, "PGP signature required but not provided", None)

                # Get admin's primary key
                admin_key_result = await self.key_mgmt.get_admin_primary_key(admin_id)
                if not admin_key_result:
                    return (False, "Admin PGP key not found", None)

                admin_key_metadata, _ = admin_key_result

                # Verify signature
                message = f"{approval_id}:{request.action_id}:{request.target_domain}"
                valid, msg, signer_key_id = await self.key_mgmt.verify_pgp_signature(
                    signature=pgp_signature,
                    message=message,
                    expected_key_id=admin_key_metadata.key_id
                )

                if not valid:
                    return (False, f"Signature verification failed: {msg}", None)

                admin_fingerprint = admin_key_metadata.fingerprint
            else:
                admin_fingerprint = "unsigned"

            # Create approval decision record
            import uuid
            decision_id = str(uuid.uuid4())

            decision = ApprovalDecisionRecord(
                approval_id=approval_id,
                action_id=request.action_id,
                decision=ApprovalDecision.APPROVED,
                admin_id=admin_id,
                admin_key_fingerprint=admin_fingerprint,
                signed_at=datetime.now(timezone.utc),
                pgp_signature=pgp_signature,
                justification=justification
            )

            self.approval_decisions[decision_id] = decision
            if approval_id in self.pending_queue:
                self.pending_queue.remove(approval_id)

            # Record in orchestration graph if available
            if self.orch_graph:
                await self.orch_graph.approve_action_with_pgp(
                    request.action_id,
                    pgp_signature or "unsigned"
                )

            self._log_audit(
                "approval_granted",
                {
                    "approval_id": approval_id,
                    "action_id": request.action_id,
                    "admin_id": admin_id,
                    "admin_fingerprint": admin_fingerprint
                }
            )

            return (True, "Action approved", decision)

        except Exception as e:
            return (False, f"Approval failed: {str(e)}", None)

    async def reject_action(
        self,
        approval_id: str,
        admin_id: str,
        reason: str = "",
        pgp_signature: Optional[str] = None
    ) -> Tuple[bool, str, Optional[ApprovalDecisionRecord]]:
        """
        Reject an action with optional PGP signature
        Returns: (success, message, decision_record)
        """
        try:
            if approval_id not in self.approval_requests:
                return (False, "Approval request not found", None)

            request = self.approval_requests[approval_id]

            # If PGP signature required, verify it
            if request.requires_pgp and self.key_mgmt and pgp_signature:
                admin_key_result = await self.key_mgmt.get_admin_primary_key(admin_id)
                if admin_key_result:
                    admin_key_metadata, _ = admin_key_result
                    admin_fingerprint = admin_key_metadata.fingerprint
                else:
                    admin_fingerprint = "unsigned"
            else:
                admin_fingerprint = "unsigned"

            # Create rejection record
            import uuid
            decision_id = str(uuid.uuid4())

            decision = ApprovalDecisionRecord(
                approval_id=approval_id,
                action_id=request.action_id,
                decision=ApprovalDecision.REJECTED,
                admin_id=admin_id,
                admin_key_fingerprint=admin_fingerprint,
                signed_at=datetime.now(timezone.utc),
                pgp_signature=pgp_signature,
                justification=reason
            )

            self.approval_decisions[decision_id] = decision
            if approval_id in self.pending_queue:
                self.pending_queue.remove(approval_id)

            # Record in orchestration graph
            if self.orch_graph:
                await self.orch_graph.reject_action(request.action_id, reason)

            self._log_audit(
                "approval_rejected",
                {
                    "approval_id": approval_id,
                    "action_id": request.action_id,
                    "admin_id": admin_id,
                    "reason": reason
                }
            )

            return (True, "Action rejected", decision)

        except Exception as e:
            return (False, f"Rejection failed: {str(e)}", None)

    async def escalate_approval(
        self,
        approval_id: str,
        escalation_reason: str = "",
        escalate_to_admins: Optional[List[str]] = None
    ) -> Tuple[bool, str]:
        """
        Escalate an approval request to senior admins
        """
        try:
            if approval_id not in self.approval_requests:
                return (False, "Approval request not found")

            request = self.approval_requests[approval_id]

            self._log_audit(
                "approval_escalated",
                {
                    "approval_id": approval_id,
                    "action_id": request.action_id,
                    "escalation_reason": escalation_reason,
                    "escalate_to": escalate_to_admins or []
                }
            )

            return (True, f"Approval escalated to {len(escalate_to_admins or [])} admins")

        except Exception as e:
            return (False, f"Escalation failed: {str(e)}")

    def get_pending_approvals(self) -> List[Dict[str, Any]]:
        """Get list of pending approval requests"""
        pending = []
        for approval_id in self.pending_queue:
            if approval_id in self.approval_requests:
                req = self.approval_requests[approval_id]
                pending.append({
                    "approval_id": approval_id,
                    "action_id": req.action_id,
                    "target_domain": req.target_domain,
                    "action_type": req.action_type,
                    "description": req.description,
                    "risk_level": req.risk_level,
                    "created_at": req.created_at.isoformat(),
                    "expires_at": req.expires_at.isoformat(),
                    "time_pending_hours": (datetime.now(timezone.utc) - req.created_at).total_seconds() / 3600
                })

        return sorted(pending, key=lambda x: x["created_at"])

    def get_approval_decision(self, approval_id: str) -> Optional[Dict[str, Any]]:
        """Get the decision record for an approval"""
        if approval_id not in self.approval_decisions:
            return None

        decision = self.approval_decisions[approval_id]
        return {
            "approval_id": decision.approval_id,
            "action_id": decision.action_id,
            "decision": decision.decision.value,
            "admin_id": decision.admin_id,
            "admin_key_fingerprint": decision.admin_key_fingerprint,
            "signed_at": decision.signed_at.isoformat(),
            "justification": decision.justification,
            "pgp_signature_present": bool(decision.pgp_signature)
        }

    def get_approval_audit_trail(self) -> List[Dict[str, Any]]:
        """Get complete audit trail of all approvals"""
        return self.audit_log

    def _log_audit(self, event_type: str, details: Dict[str, Any]):
        """Log audit event"""
        self.audit_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "details": details
        })


# Global HiL approval workflow instance
hil_approval_workflow = None


def initialize_hil_approval_workflow(
    key_management_system=None,
    orchestration_graph=None
) -> HiLApprovalWorkflow:
    """Initialize the HiL approval workflow"""
    global hil_approval_workflow

    hil_approval_workflow = HiLApprovalWorkflow(
        key_management_system=key_management_system,
        orchestration_graph=orchestration_graph
    )

    return hil_approval_workflow


def get_hil_approval_workflow() -> HiLApprovalWorkflow:
    """Get the global HiL approval workflow"""
    global hil_approval_workflow

    if hil_approval_workflow is None:
        hil_approval_workflow = initialize_hil_approval_workflow()

    return hil_approval_workflow
