"""
Human-in-the-Loop (HiL) Approval Framework for K1.
Implements criticality gates, PGP-signed approvals, and CLI approval workflows.
"""

from __future__ import annotations

import logging
import asyncio
from typing import Any, Dict, Optional
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
import hashlib
import json

logger = logging.getLogger(__name__)


class CriticalityLevel(str, Enum):
    """Action criticality levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalMethod(str, Enum):
    """Methods for approval."""

    CLI_COMMAND = "cli_command"
    PGP_SIGNED = "pgp_signed"
    TIMEOUT_OVERRIDE = "timeout_override"
    AUTO_APPROVED = "auto_approved"


@dataclass
class ActionRequest:
    """Request for action approval."""

    action_id: str
    action_name: str
    criticality: CriticalityLevel
    target: str
    description: str
    impact_assessment: str
    affected_systems: list[str]
    estimated_runtime_seconds: int
    request_timestamp: str = None
    requester_id: str = ""
    playbook_id: str = ""
    phase_number: int = 0

    def __post_init__(self):
        if self.request_timestamp is None:
            self.request_timestamp = datetime.now(
                timezone.utc
            ).isoformat()

    def compute_hash(self) -> str:
        """Compute SHA256 hash of action request for verification."""
        content = json.dumps(
            {
                "action_id": self.action_id,
                "action_name": self.action_name,
                "criticality": self.criticality.value,
                "target": self.target,
                "request_timestamp": self.request_timestamp,
            },
            sort_keys=True,
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for display/signing."""
        return {
            "action_id": self.action_id,
            "action_name": self.action_name,
            "criticality": self.criticality.value,
            "target": self.target,
            "description": self.description,
            "impact_assessment": self.impact_assessment,
            "affected_systems": self.affected_systems,
            "estimated_runtime_seconds": self.estimated_runtime_seconds,
            "request_timestamp": self.request_timestamp,
            "requester_id": self.requester_id,
            "playbook_id": self.playbook_id,
            "phase_number": self.phase_number,
            "request_hash": self.compute_hash(),
        }


@dataclass
class ApprovalDecision:
    """Decision on an action request."""

    action_id: str
    approved: bool
    approval_method: ApprovalMethod
    approver_id: str
    approval_timestamp: str = None
    pgp_signature: Optional[str] = None
    reason: str = ""
    expiry_timestamp: Optional[str] = None

    def __post_init__(self):
        if self.approval_timestamp is None:
            self.approval_timestamp = datetime.now(
                timezone.utc
            ).isoformat()

    def is_expired(self) -> bool:
        """Check if approval has expired."""
        if not self.expiry_timestamp:
            return False

        expiry = datetime.fromisoformat(
            self.expiry_timestamp
        )
        now = datetime.now(timezone.utc)
        return now > expiry


class HiLApprovalGateway:
    """
    Human-in-the-Loop approval gateway for high-impact actions.
    Enforces criticality gates and approval workflows.
    """

    def __init__(
        self,
        require_approval_for: list[CriticalityLevel] = None,
        approval_timeout_seconds: int = 300,
    ):
        """
        Initialize approval gateway.

        Args:
            require_approval_for: List of criticality levels requiring approval
            approval_timeout_seconds: Timeout for approval requests
        """
        self.require_approval_for = (
            require_approval_for
            or [CriticalityLevel.HIGH, CriticalityLevel.CRITICAL]
        )
        self.approval_timeout_seconds = approval_timeout_seconds
        self.pending_approvals: Dict[str, ActionRequest] = {}
        self.approval_decisions: Dict[str, ApprovalDecision] = {}
        self.approval_history: list[tuple[ActionRequest, ApprovalDecision]] = []

    async def request_approval(
        self, request: ActionRequest
    ) -> bool:
        """
        Request approval for an action.

        Args:
            request: ActionRequest object

        Returns:
            True if approved, False if denied or timeout
        """
        if (
            request.criticality not in self.require_approval_for
        ):
            logger.info(
                f"Action {request.action_id} ({request.criticality.value}) "
                f"does not require approval"
            )
            return True

        logger.warning(
            f"HIGH-CRITICALITY ACTION PENDING APPROVAL:\n"
            f"  Action: {request.action_name}\n"
            f"  Target: {request.target}\n"
            f"  Criticality: {request.criticality.value}\n"
            f"  Impact: {request.impact_assessment}\n"
            f"  Affected Systems: {', '.join(request.affected_systems)}\n"
            f"  Runtime: ~{request.estimated_runtime_seconds}s\n"
            f"\nApproval ID: {request.action_id}"
        )

        # Store request
        self.pending_approvals[request.action_id] = request

        # Wait for approval with timeout
        approval_decision = await self._wait_for_approval(
            request.action_id, self.approval_timeout_seconds
        )

        if approval_decision is None:
            logger.error(
                f"APPROVAL TIMEOUT for action {request.action_id}"
            )
            del self.pending_approvals[request.action_id]
            return False

        # Record decision
        self.approval_decisions[request.action_id] = (
            approval_decision
        )
        self.approval_history.append((request, approval_decision))

        if approval_decision.approved:
            logger.info(
                f"✓ APPROVED: {request.action_name} "
                f"({approval_decision.approval_method.value})"
            )
        else:
            logger.error(
                f"✗ DENIED: {request.action_name} - {approval_decision.reason}"
            )

        del self.pending_approvals[request.action_id]
        return approval_decision.approved

    async def _wait_for_approval(
        self, action_id: str, timeout_seconds: int
    ) -> Optional[ApprovalDecision]:
        """
        Wait for approval from CLI or API.

        Args:
            action_id: Action ID to wait for
            timeout_seconds: Timeout in seconds

        Returns:
            ApprovalDecision or None if timeout
        """
        start_time = datetime.now(timezone.utc)

        while True:
            # Check if decision was made
            if action_id in self.approval_decisions:
                return self.approval_decisions.pop(action_id)

            # Check timeout
            elapsed = (
                datetime.now(timezone.utc) - start_time
            ).total_seconds()
            if elapsed > timeout_seconds:
                return None

            # Wait before retrying
            await asyncio.sleep(0.5)

    async def approve_action(
        self,
        action_id: str,
        approver_id: str,
        method: ApprovalMethod = ApprovalMethod.CLI_COMMAND,
        pgp_signature: Optional[str] = None,
    ) -> bool:
        """
        Approve a pending action.

        Args:
            action_id: Action ID to approve
            approver_id: ID of approver
            method: Approval method
            pgp_signature: Optional PGP signature

        Returns:
            True if approval recorded
        """
        if action_id not in self.pending_approvals:
            logger.error(f"Unknown action ID: {action_id}")
            return False

        request = self.pending_approvals[action_id]

        decision = ApprovalDecision(
            action_id=action_id,
            approved=True,
            approval_method=method,
            approver_id=approver_id,
            pgp_signature=pgp_signature,
            expiry_timestamp=(
                (datetime.now(timezone.utc) + timedelta(
                    hours=1
                )).isoformat()
            ),
        )

        self.approval_decisions[action_id] = decision
        logger.info(
            f"Approval recorded for {action_id} "
            f"by {approver_id} ({method.value})"
        )
        return True

    async def deny_action(
        self,
        action_id: str,
        denier_id: str,
        reason: str = "Denied by operator",
    ) -> bool:
        """
        Deny a pending action.

        Args:
            action_id: Action ID to deny
            denier_id: ID of denier
            reason: Reason for denial

        Returns:
            True if denial recorded
        """
        if action_id not in self.pending_approvals:
            logger.error(f"Unknown action ID: {action_id}")
            return False

        decision = ApprovalDecision(
            action_id=action_id,
            approved=False,
            approval_method=ApprovalMethod.CLI_COMMAND,
            approver_id=denier_id,
            reason=reason,
        )

        self.approval_decisions[action_id] = decision
        logger.warning(
            f"Action denied: {action_id} - {reason}"
        )
        return True

    def get_pending_approvals(self) -> list[Dict[str, Any]]:
        """Get list of pending approvals."""
        return [r.to_dict() for r in self.pending_approvals.values()]

    def get_approval_history(
        self, limit: int = 100
    ) -> list[Dict[str, Any]]:
        """Get approval decision history."""
        return [
            {
                "request": req.to_dict(),
                "decision": {
                    "approved": dec.approved,
                    "method": dec.approval_method.value,
                    "approver": dec.approver_id,
                    "timestamp": dec.approval_timestamp,
                    "reason": dec.reason,
                },
            }
            for req, dec in self.approval_history[-limit:]
        ]

    def get_approval_stats(self) -> Dict[str, Any]:
        """Get approval statistics."""
        total = len(self.approval_history)
        approved = sum(
            1 for _, dec in self.approval_history if dec.approved
        )
        denied = total - approved

        return {
            "total_requests": total,
            "approved": approved,
            "denied": denied,
            "approval_rate": (
                approved / total * 100 if total > 0 else 0
            ),
            "pending_count": len(self.pending_approvals),
        }


# Global HiL gateway instance
_hil_gateway: Optional[HiLApprovalGateway] = None


async def get_hil_gateway() -> HiLApprovalGateway:
    """Get or create global HiL gateway."""
    global _hil_gateway

    if _hil_gateway is None:
        _hil_gateway = HiLApprovalGateway(
            require_approval_for=[
                CriticalityLevel.HIGH,
                CriticalityLevel.CRITICAL,
            ],
            approval_timeout_seconds=300,  # 5 minutes
        )

    return _hil_gateway


async def request_action_approval(
    action_name: str,
    target: str,
    criticality: CriticalityLevel,
    description: str,
    impact_assessment: str,
    affected_systems: list[str],
    estimated_runtime_seconds: int = 60,
) -> bool:
    """
    Convenience function to request action approval.

    Args:
        action_name: Name of action
        target: Target URL/host
        criticality: Criticality level
        description: Action description
        impact_assessment: Impact assessment
        affected_systems: List of affected systems
        estimated_runtime_seconds: Estimated execution time

    Returns:
        True if approved
    """
    gateway = await get_hil_gateway()

    import uuid

    action_id = str(uuid.uuid4())[:8]

    request = ActionRequest(
        action_id=action_id,
        action_name=action_name,
        criticality=criticality,
        target=target,
        description=description,
        impact_assessment=impact_assessment,
        affected_systems=affected_systems,
        estimated_runtime_seconds=estimated_runtime_seconds,
    )

    return await gateway.request_approval(request)
