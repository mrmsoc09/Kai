"""
Orchestration Graph API Router
Exposes hunting workflow state machine and phase transitions
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from datetime import datetime
import asyncio

router = APIRouter(prefix="/api/orchestration", tags=["orchestration"])

# Module-level cache for systems
_orchestration_graph = None


def set_orchestration_graph(graph):
    """Set orchestration graph reference from main.py"""
    global _orchestration_graph
    _orchestration_graph = graph


def get_orchestration_graph():
    """Get orchestration graph with fallback import"""
    global _orchestration_graph

    if _orchestration_graph is None:
        try:
            from apps.backend.src.core.orchestration_graph import orchestration_graph
            _orchestration_graph = orchestration_graph
        except Exception:
            raise HTTPException(status_code=500, detail="Orchestration graph not initialized")

    return _orchestration_graph


# ==================== Request/Response Models ====================

class CreateSessionRequest(BaseModel):
    """Request to create new hunting session"""
    target_domain: str
    mission_statement: str
    session_id: Optional[str] = None


class SessionResponse(BaseModel):
    """Current session state"""
    session_id: str
    target_domain: str
    current_phase: str
    started_at: str
    actions_planned: int
    actions_executed: int
    findings_count: int
    total_cost_cents: float


class PlanActionRequest(BaseModel):
    """Add action to hunting plan"""
    action_type: str  # reconnaissance, analysis, exploitation, validation, reporting
    target: str
    description: str
    expected_outcome: str
    risk_level: str  # low, medium, high, critical
    requires_approval: bool = False


class ApprovalRequest(BaseModel):
    """Request approval for action"""
    action_id: str
    pgp_signature: Optional[str] = None


class ExecutionResultRequest(BaseModel):
    """Record execution result"""
    action_id: str
    success: bool
    execution_time_ms: float
    output: Dict[str, Any]
    errors: List[str] = []
    model_used: Optional[str] = None
    model_cost_cents: float = 0.0
    verified: bool = False


class FindingRequest(BaseModel):
    """Submit finding from execution"""
    finding_id: str
    finding_type: str
    severity: str  # critical, high, medium, low
    description: str
    affected_endpoint: Optional[str] = None
    cvss_score: Optional[float] = None
    proof_of_concept: Optional[str] = None


class PhaseTransitionRequest(BaseModel):
    """Request phase transition"""
    target_phase: str


# ==================== Session Management ====================

@router.post("/sessions", response_model=SessionResponse)
async def create_hunting_session(request: CreateSessionRequest):
    """Create new hunting session"""
    from apps.backend.src.core.orchestration_graph import (
        initialize_orchestration_graph
    )
    import uuid

    try:
        session_id = request.session_id or str(uuid.uuid4())

        graph = initialize_orchestration_graph(
            session_id=session_id,
            target_domain=request.target_domain,
            mission=request.mission_statement
        )

        # Store globally for future requests
        global _orchestration_graph
        _orchestration_graph = graph

        return SessionResponse(
            session_id=graph.session.session_id,
            target_domain=graph.session.target_domain,
            current_phase=graph.session.current_phase.value,
            started_at=graph.session.started_at.isoformat(),
            actions_planned=len(graph.session.plan),
            actions_executed=len(graph.session.executed_actions),
            findings_count=len(graph.session.findings),
            total_cost_cents=graph.session.total_api_cost_cents
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Session creation failed: {str(e)}")


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session_state(session_id: str):
    """Get current session state"""
    graph = get_orchestration_graph()

    if graph.session.session_id != session_id:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return SessionResponse(
        session_id=graph.session.session_id,
        target_domain=graph.session.target_domain,
        current_phase=graph.session.current_phase.value,
        started_at=graph.session.started_at.isoformat(),
        actions_planned=len(graph.session.plan),
        actions_executed=len(graph.session.executed_actions),
        findings_count=len(graph.session.findings),
        total_cost_cents=graph.session.total_api_cost_cents
    )


# ==================== Plan Management ====================

@router.post("/sessions/{session_id}/plan", response_model=Dict[str, Any])
async def add_plan_action(session_id: str, action: PlanActionRequest):
    """Add action to hunting plan"""
    graph = get_orchestration_graph()

    if graph.session.session_id != session_id:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    try:
        from apps.backend.src.core.orchestration_graph import PlanAction, ApprovalStatus
        import uuid

        plan_action = PlanAction(
            action_id=str(uuid.uuid4()),
            action_type=action.action_type,
            target=action.target,
            description=action.description,
            expected_outcome=action.expected_outcome,
            risk_level=action.risk_level,
            requires_approval=action.requires_approval,
            approval_status=ApprovalStatus.PENDING
        )

        asyncio.create_task(graph.add_plan_action(plan_action))

        return {
            "action_id": plan_action.action_id,
            "status": "added_to_plan",
            "requires_approval": plan_action.requires_approval
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Plan action failed: {str(e)}")


@router.get("/sessions/{session_id}/plan", response_model=Dict[str, Any])
async def get_plan_summary(session_id: str):
    """Get plan summary"""
    graph = get_orchestration_graph()

    if graph.session.session_id != session_id:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return graph.get_plan_summary()


# ==================== Approval Workflow ====================

@router.post("/sessions/{session_id}/actions/{action_id}/request-approval", response_model=Dict[str, Any])
async def request_action_approval(
    session_id: str,
    action_id: str,
    reason: str = ""
):
    """Request human approval for action"""
    graph = get_orchestration_graph()

    if graph.session.session_id != session_id:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    try:
        success = await graph.request_hil_approval(action_id, reason)

        if not success:
            raise HTTPException(status_code=404, detail=f"Action {action_id} not found")

        return {
            "action_id": action_id,
            "approval_status": "pending",
            "requires_pgp": True
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Approval request failed: {str(e)}")


@router.post("/sessions/{session_id}/actions/{action_id}/approve", response_model=Dict[str, Any])
async def approve_action(
    session_id: str,
    action_id: str,
    request: ApprovalRequest
):
    """Approve action with PGP signature"""
    graph = get_orchestration_graph()

    if graph.session.session_id != session_id:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    try:
        success = await graph.approve_action_with_pgp(
            action_id,
            request.pgp_signature or "unsigned"
        )

        if not success:
            raise HTTPException(status_code=404, detail=f"Action {action_id} not found")

        return {
            "action_id": action_id,
            "approval_status": "approved"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Approval failed: {str(e)}")


@router.post("/sessions/{session_id}/actions/{action_id}/reject", response_model=Dict[str, Any])
async def reject_action(
    session_id: str,
    action_id: str,
    reason: str = ""
):
    """Reject action"""
    graph = get_orchestration_graph()

    if graph.session.session_id != session_id:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    try:
        success = await graph.reject_action(action_id, reason)

        if not success:
            raise HTTPException(status_code=404, detail=f"Action {action_id} not found")

        return {
            "action_id": action_id,
            "approval_status": "rejected",
            "reason": reason
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rejection failed: {str(e)}")


# ==================== Execution & Results ====================

@router.post("/sessions/{session_id}/execute", response_model=Dict[str, Any])
async def record_execution(
    session_id: str,
    result: ExecutionResultRequest
):
    """Record execution result"""
    graph = get_orchestration_graph()

    if graph.session.session_id != session_id:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    try:
        from apps.backend.src.core.orchestration_graph import ExecutionResult

        exec_result = ExecutionResult(
            action_id=result.action_id,
            execution_time_ms=result.execution_time_ms,
            success=result.success,
            output=result.output,
            errors=result.errors,
            model_used=result.model_used,
            model_cost_cents=result.model_cost_cents,
            verified=result.verified
        )

        await graph.record_execution(exec_result)

        return {
            "action_id": result.action_id,
            "execution_status": "recorded",
            "success": result.success
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution recording failed: {str(e)}")


@router.get("/sessions/{session_id}/execution-summary", response_model=Dict[str, Any])
async def get_execution_summary(session_id: str):
    """Get execution progress"""
    graph = get_orchestration_graph()

    if graph.session.session_id != session_id:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return graph.get_execution_summary()


# ==================== Findings ====================

@router.post("/sessions/{session_id}/findings", response_model=Dict[str, Any])
async def add_finding(
    session_id: str,
    finding: FindingRequest
):
    """Add finding from execution"""
    graph = get_orchestration_graph()

    if graph.session.session_id != session_id:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    try:
        finding_dict = {
            "id": finding.finding_id,
            "type": finding.finding_type,
            "severity": finding.severity,
            "description": finding.description,
            "affected_endpoint": finding.affected_endpoint,
            "cvss_score": finding.cvss_score,
            "proof_of_concept": finding.proof_of_concept,
            "timestamp": datetime.utcnow().isoformat()
        }

        await graph.add_finding(finding_dict)

        return {
            "finding_id": finding.finding_id,
            "status": "recorded"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Finding recording failed: {str(e)}")


@router.get("/sessions/{session_id}/findings", response_model=Dict[str, Any])
async def get_findings_summary(session_id: str):
    """Get findings overview"""
    graph = get_orchestration_graph()

    if graph.session.session_id != session_id:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return graph.get_findings_summary()


# ==================== Phase Management ====================

@router.post("/sessions/{session_id}/phase", response_model=Dict[str, Any])
async def transition_phase(
    session_id: str,
    request: PhaseTransitionRequest
):
    """Transition to next hunting phase"""
    graph = get_orchestration_graph()

    if graph.session.session_id != session_id:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    try:
        from apps.backend.src.core.orchestration_graph import HuntPhase

        target_phase = HuntPhase(request.target_phase)
        success = await graph.transition_phase(target_phase)

        if not success:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot transition from {graph.session.current_phase.value} to {target_phase.value}"
            )

        return {
            "current_phase": graph.session.current_phase.value,
            "previous_phase": request.target_phase,
            "status": "transitioned"
        }

    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid phase: {request.target_phase}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Phase transition failed: {str(e)}")


# ==================== Episodic Memory ====================

@router.post("/sessions/{session_id}/memory/pattern", response_model=Dict[str, Any])
async def record_learned_pattern(
    session_id: str,
    pattern: str,
    success_rate: float
):
    """Record learned pattern in episodic memory"""
    graph = get_orchestration_graph()

    if graph.session.session_id != session_id:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    try:
        await graph.record_episodic_memory(pattern, success_rate)

        return {
            "pattern": pattern,
            "success_rate": success_rate,
            "status": "recorded"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Memory recording failed: {str(e)}")


@router.post("/sessions/{session_id}/memory/blocked-technique", response_model=Dict[str, Any])
async def mark_technique_as_blocked(
    session_id: str,
    technique: str
):
    """Mark technique as blocked/unsuccessful"""
    graph = get_orchestration_graph()

    if graph.session.session_id != session_id:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    try:
        await graph.mark_technique_blocked(technique)

        return {
            "technique": technique,
            "status": "marked_blocked"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Blocking failed: {str(e)}")


# ==================== Audit Trail ====================

@router.get("/sessions/{session_id}/audit-trail", response_model=List[Dict[str, Any]])
async def get_audit_trail(session_id: str):
    """Get complete audit trail for session"""
    graph = get_orchestration_graph()

    if graph.session.session_id != session_id:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return graph.get_audit_trail()


@router.get("/sessions/{session_id}/summary", response_model=Dict[str, Any])
async def get_session_summary(session_id: str):
    """Get complete session summary"""
    graph = get_orchestration_graph()

    if graph.session.session_id != session_id:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")

    return graph.to_dict()
