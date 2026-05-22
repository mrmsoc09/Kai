"""
KaiOrchestrator API Router
Exposes endpoints for executing tools through the compliance middleware
"""

from datetime import datetime, timezone
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
import logging
import uuid

import yaml

from ..core.crew_yaml_runner import (
    CREW_REGISTRY_PATH,
    list_all_crews,
    run_crew_yaml,
)
from ..core.tool_registry_catalog import list_catalog_entries
from ..core.auth import require_roles, ROLE_OPERATOR, ROLE_ADMIN

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/orchestrator",
    tags=["orchestrator"],
    dependencies=[Depends(require_roles(ROLE_OPERATOR, ROLE_ADMIN))],
)


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


class CrewRunRequest(BaseModel):
    """Request to run a crew YAML through the managed adapter path."""
    file_path: str = Field(..., description="Crew YAML file path under ./crews")
    framework: Optional[str] = Field(
        default=None,
        description="Framework override (crewai, autogen, praisonai)",
    )


def _display_name(name: str) -> str:
    return name.replace("_", " ").replace("-", " ").title()


def _normalize_safety(value: str) -> str:
    lowered = (value or "").strip().lower()
    if lowered in {"passive", "active", "intrusive"}:
        return lowered
    if lowered in {"safe", "read_only", "readonly"}:
        return "passive"
    if lowered in {"dangerous", "exploit"}:
        return "intrusive"
    return "active"


def _infer_phase(category: str) -> int:
    lowered = (category or "").strip().lower()
    if lowered in {"recon_asset_discovery", "http_live_host", "osint"}:
        return 1
    if lowered in {"vulnerability_scanning", "api_auth_testing"}:
        return 7
    if lowered in {"validation_support"}:
        return 8
    if lowered in {"reporting", "aggregation"}:
        return 9
    return 5


def _resolve_crew_path(raw_path: str) -> Path:
    repo_crews = (Path.cwd() / "crews").resolve()
    candidate = (Path.cwd() / raw_path).resolve()
    try:
        candidate.relative_to(repo_crews)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="crew_path_outside_allowed_root") from exc
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="crew_yaml_not_found")
    return candidate


def _load_crew_index() -> tuple[dict[str, str], set[str]]:
    phase_by_path: dict[str, str] = {}
    primary_paths: set[str] = set()
    try:
        payload = yaml.safe_load(CREW_REGISTRY_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return phase_by_path, primary_paths
    phase_crews = payload.get("phase_crews", {}) if isinstance(payload, dict) else {}
    if not isinstance(phase_crews, dict):
        return phase_by_path, primary_paths
    for phase_key, phase_cfg in phase_crews.items():
        if not isinstance(phase_cfg, dict):
            continue
        primary = phase_cfg.get("primary")
        if isinstance(primary, str) and primary.strip():
            normalized = str((Path.cwd() / primary).resolve())
            phase_by_path[normalized] = str(phase_key)
            primary_paths.add(normalized)
        alternatives = phase_cfg.get("alternatives", [])
        if isinstance(alternatives, list):
            for alt in alternatives:
                if not isinstance(alt, str) or not alt.strip():
                    continue
                normalized = str((Path.cwd() / alt).resolve())
                phase_by_path.setdefault(normalized, str(phase_key))
    return phase_by_path, primary_paths


def _normalize_framework(value: Optional[str]) -> str:
    lowered = (value or "").strip().lower()
    if lowered in {"autogen2", "autogen_2", "autogen-2"}:
        return "autogen"
    if lowered in {"crewai", "autogen", "praisonai"}:
        return lowered
    return "crewai"


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


@router.get("/agents/registry")
async def get_agent_registry() -> list[Dict[str, Any]]:
    """Part 3 compatibility endpoint for frontend tool-registry browser."""
    items = []
    for entry in list_catalog_entries():
        safety = _normalize_safety(entry.safety_classification)
        items.append(
            {
                "name": entry.name,
                "display_name": _display_name(entry.name),
                "description": (
                    f"{entry.execution_mode} execution path for {entry.category} workflows."
                ),
                "category": entry.category,
                "safety_classification": safety,
                "phase": _infer_phase(entry.category),
                "timeout_seconds": entry.timeout_seconds,
                "requires_auth": bool(entry.api_keys_required),
                "api_keys_required": bool(entry.api_keys_required),
                "enabled": bool(entry.enabled_by_default),
                "knowledge_files": [],
                "memory_files": [],
            }
        )
    return items


@router.get("/crews/registry")
async def get_crews_registry() -> list[Dict[str, Any]]:
    """Part 3 compatibility endpoint for Crew YAML browser."""
    phase_by_path, primary_paths = _load_crew_index()
    crews = []
    for crew in list_all_crews():
        file_path = str(crew.get("file_path") or "")
        resolved_path = str((Path.cwd() / file_path).resolve())
        raw_framework = str(crew.get("framework") or "praisonai")
        framework = _normalize_framework(raw_framework)
        roles = crew.get("roles")
        crews.append(
            {
                "name": str(crew.get("name") or _display_name(Path(file_path).stem)),
                "framework": framework,
                "phase": phase_by_path.get(resolved_path, "unmapped"),
                "topic": str(crew.get("topic") or ""),
                "roles": roles if isinstance(roles, list) else [],
                "file_path": file_path,
                "is_primary": resolved_path in primary_paths,
            }
        )
    crews.sort(key=lambda item: (item["phase"], item["name"]))
    return crews


@router.post("/crews/run")
async def run_crew_registry_entry(request: CrewRunRequest) -> Dict[str, Any]:
    """Run a registered crew file via the wrapper-only adapter path."""
    crew_path = _resolve_crew_path(request.file_path)
    framework = _normalize_framework(request.framework)
    if request.framework is None:
        try:
            parsed = yaml.safe_load(crew_path.read_text(encoding="utf-8")) or {}
            if isinstance(parsed, dict):
                framework = _normalize_framework(parsed.get("framework"))
        except Exception:
            # Keep safe default if YAML parsing fails.
            framework = "crewai"

    result = run_crew_yaml(
        yaml_path=str(crew_path),
        framework=framework,
    )
    return {
        "job_id": f"crew-{uuid.uuid4().hex[:12]}",
        "status": "completed" if bool(result.get("success")) else "failed",
        "file_path": request.file_path,
        "framework": framework,
        "result": {
            "success": bool(result.get("success")),
            "error": result.get("error"),
        },
    }


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


@router.get("/health/full")
async def orchestrator_health_full() -> Dict[str, Any]:
    """Part 3 compatibility endpoint for platform-status dashboard."""
    timestamp = datetime.now(timezone.utc).isoformat()
    services: list[dict[str, str]] = []

    try:
        from ..core.kai_orchestrator import get_kai_orchestrator

        get_kai_orchestrator()
        services.append(
            {
                "name": "KaiOrchestrator",
                "status": "up",
                "detail": "Compliance middleware initialized",
                "last_checked": timestamp,
            }
        )
    except Exception as exc:
        services.append(
            {
                "name": "KaiOrchestrator",
                "status": "down",
                "detail": f"Initialization failed: {exc}",
                "last_checked": timestamp,
            }
        )

    try:
        tool_count = len(list_catalog_entries())
        tool_status = "up" if tool_count > 0 else "degraded"
        services.append(
            {
                "name": "Tool Registry",
                "status": tool_status,
                "detail": f"{tool_count} tools available",
                "last_checked": timestamp,
            }
        )
    except Exception as exc:
        services.append(
            {
                "name": "Tool Registry",
                "status": "down",
                "detail": f"Registry read failed: {exc}",
                "last_checked": timestamp,
            }
        )
        tool_count = 0

    try:
        crew_count = len(list_all_crews())
        crew_status = "up" if crew_count > 0 else "degraded"
        services.append(
            {
                "name": "Crew Registry",
                "status": crew_status,
                "detail": f"{crew_count} crew YAML definitions discovered",
                "last_checked": timestamp,
            }
        )
    except Exception as exc:
        services.append(
            {
                "name": "Crew Registry",
                "status": "down",
                "detail": f"Crew registry read failed: {exc}",
                "last_checked": timestamp,
            }
        )
        crew_count = 0

    try:
        from ..core.scope_guardrails import _scope_audit_log_path

        scope_log = _scope_audit_log_path()
        services.append(
            {
                "name": "Scope Audit Log",
                "status": "up" if scope_log.exists() else "degraded",
                "detail": f"audit_log={scope_log}",
                "last_checked": timestamp,
            }
        )
    except Exception as exc:
        services.append(
            {
                "name": "Scope Audit Log",
                "status": "down",
                "detail": f"Scope audit unavailable: {exc}",
                "last_checked": timestamp,
            }
        )

    statuses = [service["status"] for service in services]
    if "down" in statuses:
        overall = "critical"
    elif "degraded" in statuses:
        overall = "degraded"
    else:
        overall = "healthy"

    ready_to_hunt = overall != "critical" and tool_count > 0 and crew_count > 0
    return {
        "overall": overall,
        "ready_to_hunt": ready_to_hunt,
        "services": services,
    }
