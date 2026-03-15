"""
KaiOrchestrator API Router
Exposes endpoints for executing tools through the compliance middleware
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orchestrator", tags=["orchestrator"])


# ============================================================================
# Request/Response Models
# ============================================================================

class OrchestratorExecuteRequest(BaseModel):
    """Request to execute a tool through the orchestrator"""
    certificate_id: str = Field(..., description="Authorization certificate ID")
    target: str = Field(..., description="Target domain, IP, or CIDR range")
    tool_name: str = Field(..., description="Name of the tool to execute")
    tool_command: str = Field(..., description="Command to execute (e.g., 'python3 osint.py')")
    tool_params: Dict[str, Any] = Field(default_factory=dict, description="Parameters to pass to the tool")
    reasoning: str = Field(..., description="AI reasoning for why this operation is being performed")


class OrchestratorResponse(BaseModel):
    """Response from orchestrator execution"""
    success: bool
    error: Optional[str] = None
    log_id: Optional[str] = None
    report_path: Optional[str] = None
    metadata_path: Optional[str] = None
    autonomy_tier: Optional[str] = None
    execution_timestamp: Optional[str] = None
    chain_of_custody_logs: Optional[list] = None
    result: Optional[Dict[str, Any]] = None


class ScopeValidationRequest(BaseModel):
    """Request to validate a target against scope"""
    target: str = Field(..., description="Target to validate")


class ScopeValidationResponse(BaseModel):
    """Response from scope validation"""
    is_valid: bool
    reason: str


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/execute", response_model=OrchestratorResponse)
async def execute_orchestrated_tool(request: OrchestratorExecuteRequest) -> OrchestratorResponse:
    """
    Execute a tool through the KaiOrchestrator compliance middleware.

    This endpoint enforces:
    1. Scope Guardian - validates target against whitelist
    2. Signed Intent - requires permission slips for Tier 3 operations
    3. Audit Logging - logs all operations pre and post execution
    4. Transparency - injects AI-generated headers and metadata
    5. Subprocess isolation - runs external tools safely

    Returns a signed, audited report suitable for bug bounty platform submission.
    """
    try:
        from ..core.kai_orchestrator import get_kai_orchestrator

        orchestrator = get_kai_orchestrator()

        # Execute through full compliance pipeline
        result = await orchestrator.execute_tool(
            user_id="api_user",  # Would come from auth in production
            certificate_id=request.certificate_id,
            target=request.target,
            tool_name=request.tool_name,
            tool_params=request.tool_params,
            tool_command=request.tool_command,
            reasoning=request.reasoning
        )

        return OrchestratorResponse(
            success=result["success"],
            error=result.get("error"),
            log_id=result.get("log_id"),
            report_path=result.get("report_path"),
            metadata_path=result.get("metadata_path"),
            autonomy_tier=result.get("autonomy_tier"),
            execution_timestamp=result.get("execution_timestamp"),
            chain_of_custody_logs=result.get("chain_of_custody_logs"),
            result=result.get("result")
        )

    except Exception as e:
        logger.error(f"Orchestrator execution error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/validate-scope", response_model=ScopeValidationResponse)
async def validate_scope(request: ScopeValidationRequest) -> ScopeValidationResponse:
    """
    Validate a target against the authorized scope.

    Checks if the target (domain, IP, or CIDR) is authorized for scanning.
    """
    try:
        from ..core.kai_orchestrator import get_kai_orchestrator

        orchestrator = get_kai_orchestrator()

        is_valid, reason = orchestrator.scope_guardian.validate_target(request.target)

        return ScopeValidationResponse(
            is_valid=is_valid,
            reason=reason
        )

    except Exception as e:
        logger.error(f"Scope validation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scope-status")
async def get_scope_status() -> Dict[str, Any]:
    """Get current scope configuration and authorization status."""
    try:
        from ..core.kai_orchestrator import get_kai_orchestrator

        orchestrator = get_kai_orchestrator()
        guardian = orchestrator.scope_guardian

        return {
            "authorized_domains": guardian.authorized_domains,
            "authorized_ips": guardian.authorized_ips,
            "authorized_cidrs": [str(cidr) for cidr in guardian.authorized_cidrs],
            "allowed_methods": guardian.allowed_methods,
            "tool_autonomy_tiers": guardian.tool_autonomy_tiers,
            "total_domains": len(guardian.authorized_domains),
            "total_ips": len(guardian.authorized_ips),
            "total_cidr_ranges": len(guardian.authorized_cidrs)
        }

    except Exception as e:
        logger.error(f"Scope status error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/create-permission-slip")
async def create_permission_slip(
    target: str,
    operation_name: str,
    authorized_targets: list,
    allowed_operations: list,
    expires_days: int = 30,
    justification: str = ""
) -> Dict[str, Any]:
    """
    Create a permission slip for testing purposes.

    In production, permission slips would be:
    1. Created by authorized admins
    2. Signed with PGP keys
    3. Stored in vault/permission_slips/

    This endpoint is for demo/testing only.
    """
    try:
        from ..core.kai_orchestrator import get_kai_orchestrator

        orchestrator = get_kai_orchestrator()

        success, message = orchestrator.signed_intent.create_permission_slip(
            target=target,
            operation_name=operation_name,
            authorized_targets=authorized_targets,
            allowed_operations=allowed_operations,
            expires_days=expires_days,
            justification=justification
        )

        return {
            "success": success,
            "message": message
        }

    except Exception as e:
        logger.error(f"Permission slip creation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scope-decisions")
async def get_scope_decisions(limit: int = 50) -> Dict[str, Any]:
    """Return recent scope enforcement decisions from the audit JSONL log.

    Data source: output/logs/scope_decisions.jsonl (written by scope_guardrails.py)
    Each entry contains target, allowed, reason, evaluated_at.
    """
    import json as _json
    from ..core.scope_guardrails import _scope_audit_log_path

    try:
        log_path = _scope_audit_log_path()
        if not log_path.exists():
            return {"decisions": [], "total": 0}

        lines = log_path.read_text(encoding="utf-8").strip().splitlines()
        parsed = []
        for line in lines:
            try:
                parsed.append(_json.loads(line))
            except Exception:
                pass

        # Return the most recent `limit` entries in reverse-chronological order
        recent = parsed[-limit:]
        recent.reverse()
        return {"decisions": recent, "total": len(parsed)}

    except Exception as exc:
        logger.error("scope-decisions read error: %s", exc)
        return {"decisions": [], "total": 0, "error": str(exc)}


@router.get("/health")
async def orchestrator_health() -> Dict[str, Any]:
    """Health check for KaiOrchestrator middleware."""
    try:
        from ..core.kai_orchestrator import get_kai_orchestrator

        orchestrator = get_kai_orchestrator()

        return {
            "status": "healthy",
            "middleware": "KaiOrchestrator",
            "components": {
                "scope_guardian": "initialized",
                "signed_intent": "initialized",
                "audit_logger": "initialized",
                "execution_gateway": "initialized",
                "transparency_enforcer": "initialized"
            },
            "logs_directory": str(orchestrator.audit_logger.log_dir),
            "reports_directory": str(orchestrator.transparency.reports_dir)
        }

    except Exception as e:
        logger.error(f"Health check error: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }
