"""
K1 LangGraph Orchestration State Machine
Manages the complete hunting workflow from planning through execution and verification
"""

from typing import Dict, List, Optional, Any, Annotated, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import json


class HuntPhase(str, Enum):
    """Phases of the hunting workflow"""
    PLANNING = "planning"
    RECONNAISSANCE = "reconnaissance"
    ANALYSIS = "analysis"
    SIGNAL_VALIDATION = "signal_validation"
    VALIDATION = "validation"
    REPORTING = "reporting"
    COMPLETE = "complete"


class ApprovalStatus(str, Enum):
    """Approval status for actions"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"


@dataclass
class PlanAction:
    """Single action in the plan"""
    action_id: str
    action_type: str  # reconnaissance, analysis, validation, reporting
    target: str
    description: str
    expected_outcome: str
    risk_level: str  # low, medium, high, critical
    requires_approval: bool
    approval_status: ApprovalStatus = ApprovalStatus.PENDING
    pgp_signature: Optional[str] = None  # For HiL approval
    approval_at: Optional[datetime] = None


@dataclass
class ExecutionResult:
    """Result of executing an action"""
    action_id: str
    execution_time_ms: float
    success: bool
    output: Dict[str, Any]
    errors: List[str] = field(default_factory=list)
    model_used: Optional[str] = None
    model_cost_cents: float = 0.0
    verified: bool = False
    verification_model: Optional[str] = None
    verification_result: Optional[Dict[str, Any]] = None


@dataclass
class HuntingSession:
    """Complete hunting session state"""
    session_id: str
    started_at: datetime
    target_domain: str
    mission_statement: str
    current_phase: HuntPhase

    # Planning
    plan: List[PlanAction] = field(default_factory=list)
    plan_approved: bool = False
    plan_approval_at: Optional[datetime] = None

    # Execution
    executed_actions: List[ExecutionResult] = field(default_factory=list)
    current_action_index: int = 0

    # Findings
    findings: List[Dict[str, Any]] = field(default_factory=list)
    duplicate_findings: List[str] = field(default_factory=list)
    chainable_findings: List[Tuple[str, str]] = field(default_factory=list)

    # Model tracking
    model_assignments: Dict[str, str] = field(default_factory=dict)  # action_id -> model_id
    total_api_cost_cents: float = 0.0

    # Episodic memory
    learned_patterns: Dict[str, float] = field(default_factory=dict)  # pattern -> success_rate
    blocked_techniques: List[str] = field(default_factory=list)

    # Audit trail
    events: List[Dict[str, Any]] = field(default_factory=list)

    def add_event(self, event_type: str, details: Dict[str, Any]):
        """Add event to audit trail"""
        self.events.append({
            "timestamp": datetime.utcnow().isoformat(),
            "type": event_type,
            "details": details
        })

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "target_domain": self.target_domain,
            "current_phase": self.current_phase.value,
            "actions_planned": len(self.plan),
            "actions_executed": len(self.executed_actions),
            "findings": len(self.findings),
            "total_cost_cents": self.total_api_cost_cents,
            "events_logged": len(self.events)
        }


class OrchestrationGraph:
    """LangGraph state machine for hunt orchestration"""

    def __init__(self, session_id: str, target_domain: str, mission: str):
        self.session = HuntingSession(
            session_id=session_id,
            started_at=datetime.utcnow(),
            target_domain=target_domain,
            mission_statement=mission,
            current_phase=HuntPhase.PLANNING
        )

        # State machine transitions
        self.transitions = {
            HuntPhase.PLANNING: [HuntPhase.RECONNAISSANCE],
            HuntPhase.RECONNAISSANCE: [HuntPhase.ANALYSIS],
            HuntPhase.ANALYSIS: [HuntPhase.SIGNAL_VALIDATION, HuntPhase.REPORTING],
            HuntPhase.SIGNAL_VALIDATION: [HuntPhase.VALIDATION, HuntPhase.ANALYSIS],
            HuntPhase.VALIDATION: [HuntPhase.REPORTING, HuntPhase.SIGNAL_VALIDATION],
            HuntPhase.REPORTING: [HuntPhase.COMPLETE]
        }

    async def transition_phase(self, new_phase: HuntPhase) -> bool:
        """Transition to new phase if allowed"""
        allowed = self.transitions.get(self.session.current_phase, [])

        if new_phase not in allowed:
            self.session.add_event("phase_transition_rejected", {
                "from": self.session.current_phase.value,
                "to": new_phase.value,
                "reason": "Invalid transition"
            })
            return False

        old_phase = self.session.current_phase
        self.session.current_phase = new_phase

        self.session.add_event("phase_transitioned", {
            "from": old_phase.value,
            "to": new_phase.value
        })

        return True

    async def add_plan_action(self, action: PlanAction) -> None:
        """Add action to the plan"""
        self.session.plan.append(action)

        self.session.add_event("plan_action_added", {
            "action_id": action.action_id,
            "type": action.action_type,
            "requires_approval": action.requires_approval
        })

    async def request_hil_approval(self, action_id: str, reason: str = "") -> bool:
        """Request human approval for high-risk action"""
        action = next((a for a in self.session.plan if a.action_id == action_id), None)

        if not action:
            return False

        action.approval_status = ApprovalStatus.PENDING

        self.session.add_event("hil_approval_requested", {
            "action_id": action_id,
            "reason": reason,
            "requires_pgp": True
        })

        return True

    async def approve_action_with_pgp(self, action_id: str, pgp_signature: str) -> bool:
        """Approve action with PGP signature"""
        action = next((a for a in self.session.plan if a.action_id == action_id), None)

        if not action:
            return False

        # Verify PGP signature (simplified for now)
        action.approval_status = ApprovalStatus.APPROVED
        action.pgp_signature = pgp_signature
        action.approval_at = datetime.utcnow()

        self.session.add_event("action_approved", {
            "action_id": action_id,
            "approval_method": "pgp_signature"
        })

        return True

    async def reject_action(self, action_id: str, reason: str) -> bool:
        """Reject action"""
        action = next((a for a in self.session.plan if a.action_id == action_id), None)

        if not action:
            return False

        action.approval_status = ApprovalStatus.REJECTED

        self.session.add_event("action_rejected", {
            "action_id": action_id,
            "reason": reason
        })

        return True

    async def record_execution(self, result: ExecutionResult) -> None:
        """Record execution result"""
        self.session.executed_actions.append(result)
        self.session.total_api_cost_cents += result.model_cost_cents

        self.session.add_event("action_executed", {
            "action_id": result.action_id,
            "success": result.success,
            "cost_cents": result.model_cost_cents,
            "model": result.model_used
        })

    async def add_finding(self, finding: Dict[str, Any]) -> None:
        """Add finding from execution"""
        self.session.findings.append(finding)

        self.session.add_event("finding_added", {
            "finding_id": finding.get("id"),
            "type": finding.get("type"),
            "severity": finding.get("severity")
        })

    async def record_episodic_memory(self, pattern: str, success_rate: float) -> None:
        """Record learned pattern in episodic memory"""
        self.session.learned_patterns[pattern] = success_rate

        self.session.add_event("pattern_learned", {
            "pattern": pattern,
            "success_rate": success_rate
        })

    async def mark_technique_blocked(self, technique: str) -> None:
        """Mark technique as blocked/unsuccessful"""
        if technique not in self.session.blocked_techniques:
            self.session.blocked_techniques.append(technique)

        self.session.add_event("technique_blocked", {
            "technique": technique
        })

    def get_plan_summary(self) -> Dict[str, Any]:
        """Get plan overview"""
        pending = [a for a in self.session.plan if a.approval_status == ApprovalStatus.PENDING]
        approved = [a for a in self.session.plan if a.approval_status == ApprovalStatus.APPROVED]

        return {
            "total_actions": len(self.session.plan),
            "pending_approval": len(pending),
            "approved": len(approved),
            "actions": [
                {
                    "id": a.action_id,
                    "type": a.action_type,
                    "status": a.approval_status.value,
                    "risk": a.risk_level
                }
                for a in self.session.plan
            ]
        }

    def get_execution_summary(self) -> Dict[str, Any]:
        """Get execution progress"""
        total_cost = sum(r.model_cost_cents for r in self.session.executed_actions)
        successful = len([r for r in self.session.executed_actions if r.success])
        verified = len([r for r in self.session.executed_actions if r.verified])

        return {
            "total_executed": len(self.session.executed_actions),
            "successful": successful,
            "verified": verified,
            "total_cost_cents": total_cost,
            "models_used": list(set(r.model_used for r in self.session.executed_actions if r.model_used))
        }

    def get_findings_summary(self) -> Dict[str, Any]:
        """Get findings overview"""
        return {
            "total_findings": len(self.session.findings),
            "duplicates": len(self.session.duplicate_findings),
            "chainable": len(self.session.chainable_findings),
            "findings_by_severity": self._group_by_severity(),
            "critical_or_high": len([f for f in self.session.findings if f.get("severity") in ["critical", "high"]])
        }

    def _group_by_severity(self) -> Dict[str, int]:
        """Group findings by severity"""
        grouped = {}
        for finding in self.session.findings:
            severity = finding.get("severity", "unknown")
            grouped[severity] = grouped.get(severity, 0) + 1
        return grouped

    def get_audit_trail(self) -> List[Dict[str, Any]]:
        """Get complete audit trail"""
        return self.session.events

    def to_dict(self) -> Dict[str, Any]:
        """Export full state"""
        return {
            "session": self.session.to_dict(),
            "plan": self.get_plan_summary(),
            "execution": self.get_execution_summary(),
            "findings": self.get_findings_summary(),
            "audit_events": len(self.session.events)
        }


# Global orchestration graph
orchestration_graph = None


def initialize_orchestration_graph(
    session_id: str,
    target_domain: str,
    mission: str
) -> OrchestrationGraph:
    """Initialize orchestration graph"""
    global orchestration_graph

    orchestration_graph = OrchestrationGraph(session_id, target_domain, mission)
    print(f"✓ Orchestration graph initialized: {session_id}")

    return orchestration_graph
