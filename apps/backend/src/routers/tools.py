"""
Tools API Router
Exposes all K1 tools via REST API with autonomy tier gating
"""

from typing import Optional, Dict, Any, List, Callable
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
import logging
from datetime import datetime
import anyio.to_thread
from functools import partial
from urllib.parse import urlparse

from ..core.auth import ROLE_ADMIN, ROLE_ANALYST, ROLE_OPERATOR, User, require_roles
from ..core.tools import (
    get_registry,
    ToolCategory,
    ToolStatus,
    ToolAutonomyTier,
    ToolExecutionContext,
)
from ..core.tool_registry_catalog import get_catalog_entry, list_catalog_entries
from ..core.tool_health_service import (
    apply_execution_history,
    build_dashboard,
    load_last_execution_records,
    write_dashboard_report,
)
from ..core.toolpacks import get_toolpack_manager, ToolpackValidationError
from ..core.authorization_gate import (
    enforce_authorization_gates_async,
    AuthorizationGateError,
)
from ..core.kai_security_guardrails import get_guardrail_engine
from ..core.tools_validators import FindingValidatorTool, QuickClassifierTool
from ..core.tool_execution_store import get_tool_execution_store
from ..core.tools_analysis import (
    VulnerabilityAnalyzerTool,
    ChainAnalyzerTool,
    ProgramMatcherTool,
)
from ..schemas.common import Response

logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/api/v1/tools", tags=["Tools"])

# Tool registry (initialize on startup)
_registry = None


def _safe_register_optional_tool(factory: Callable[[], Any], *, tool_name: str) -> None:
    registry = get_registry()
    try:
        registry.register(factory())
    except Exception as exc:
        logger.warning("optional tool unavailable (%s): %s", tool_name, exc)


def _extract_target(params: Dict[str, Any]) -> str:
    for key in ("target", "url", "domain", "host", "ip", "rhost"):
        value = params.get(key)
        if isinstance(value, str) and value.strip():
            text = value.strip()
            if "://" in text:
                parsed = urlparse(text)
                return (parsed.hostname or "").strip()
            return text
    return ""


def _resolve_authorization_hints(
    *,
    tool_id: str,
    params: Dict[str, Any],
    method: Optional[str],
    current_user: User,
    requested_program_id: Optional[str],
    requested_certificate_id: Optional[str],
) -> tuple[Optional[str], Optional[str]]:
    target = _extract_target(params)
    resolved_method = (method or params.get("method") or "").strip()
    requested_program = (requested_program_id or str(params.get("program_id") or "")).strip() or None
    cert_hints = {
        value.strip()
        for value in (
            requested_certificate_id,
            str(params.get("certificate_id") or ""),
        )
        if isinstance(value, str) and value.strip()
    }
    if len(cert_hints) > 1:
        raise HTTPException(status_code=403, detail="conflicting certificate_id values provided")

    guardrails = get_guardrail_engine()
    matching_certs: list[tuple[str, str | None]] = []
    for cert_id, cert in guardrails.authorized_certificates.items():
        if not cert.is_valid():
            continue
        cert_user = str((cert.metadata or {}).get("user_id") or "").strip()
        if cert_user and cert_user != current_user.id:
            continue
        if target and not guardrails._matches_target(cert.target, target):
            continue
        if resolved_method and resolved_method not in cert.allowed_methods:
            continue
        cert_program = str((cert.metadata or {}).get("program_id") or "").strip() or None
        matching_certs.append((cert_id, cert_program))

    authoritative_certificate_id: Optional[str] = None
    authoritative_program_id: Optional[str] = None
    requested_cert = next(iter(cert_hints), None)
    if requested_cert:
        cert = guardrails.authorized_certificates.get(requested_cert)
        if cert is None:
            raise HTTPException(status_code=403, detail="certificate_id not recognized")
        cert_user = str((cert.metadata or {}).get("user_id") or "").strip()
        if cert_user and cert_user != current_user.id:
            raise HTTPException(status_code=403, detail="certificate_id not valid for authenticated principal")
        if target and not guardrails._matches_target(cert.target, target):
            raise HTTPException(status_code=403, detail="certificate target does not authorize requested target")
        if resolved_method and resolved_method not in cert.allowed_methods:
            raise HTTPException(status_code=403, detail="certificate method does not authorize requested action")
        authoritative_certificate_id = requested_cert
        authoritative_program_id = str((cert.metadata or {}).get("program_id") or "").strip() or None
    elif len(matching_certs) == 1:
        authoritative_certificate_id, authoritative_program_id = matching_certs[0]

    if requested_program and authoritative_program_id and requested_program != authoritative_program_id:
        raise HTTPException(status_code=403, detail="program_id does not match authorized certificate metadata")
    if requested_program and authoritative_program_id is None:
        raise HTTPException(status_code=403, detail="program_id must be derived from authorized certificate context")

    if authoritative_certificate_id:
        params.pop("certificate_id", None)
    if authoritative_program_id:
        params.pop("program_id", None)
    return authoritative_program_id, authoritative_certificate_id


def get_tool_registry():
    """Get initialized tool registry"""
    global _registry
    if _registry is None:
        _registry = get_registry()
        # Autoload default adapters
        try:
            from apps.backend.src.core.tools import initialize_default_tools
            initialize_default_tools()
            manager = get_toolpack_manager()
            manager.load()
            manager.resolve_mappings(_registry.get_all_schemas().keys())
        except Exception as e:
            logger.error(f"Tool init error: {e}")
        # Register optional LLM-assisted tools with graceful dependency degradation.
        _safe_register_optional_tool(FindingValidatorTool, tool_name="finding_validator")
        _safe_register_optional_tool(QuickClassifierTool, tool_name="quick_classifier")
        _safe_register_optional_tool(VulnerabilityAnalyzerTool, tool_name="vulnerability_analyzer")
        _safe_register_optional_tool(ChainAnalyzerTool, tool_name="chain_analyzer")
        _safe_register_optional_tool(ProgramMatcherTool, tool_name="program_matcher")
        logger.info(f"Tool registry initialized with {_registry.count()} tools")
    return _registry


def _ensure_tool_enabled(tool_id: str) -> None:
    try:
        manager = get_toolpack_manager()
        if manager.config is None:
            manager.load()
            manager.resolve_mappings(get_tool_registry().get_all_schemas().keys())
        if not manager.is_adapter_enabled(tool_id):
            raise HTTPException(status_code=403, detail=f"Tool disabled by toolpack policy: {tool_id}")
    except ToolpackValidationError as exc:
        raise HTTPException(status_code=503, detail=f"Toolpack policy unavailable: {exc}") from exc


# ============================================================================
# Tool Discovery Endpoints
# ============================================================================


@router.get("/health", tags=["Health"])
async def tools_health(
    enabled_only: bool = Query(default=False),
    run_smoke_tests: bool = Query(default=False),
    telemetry_window: int = Query(default=20, ge=1, le=200),
    install_timeout: int = Query(default=8, ge=1, le=60),
    include_execution_history: bool = Query(
        default=False,
        description="When true, enrich last execution fields from canonical ToolExecution rows",
    ),
    write_report: bool = Query(default=False),
):
    """Return structured per-tool health records from the canonical tool catalog."""
    registry = get_tool_registry()
    dashboard = await anyio.to_thread.run_sync(
        partial(
            build_dashboard,
            enabled_only=enabled_only,
            telemetry_window=telemetry_window,
            install_timeout=install_timeout,
            run_smoke_tests=run_smoke_tests,
            use_cached_install_report=True,
        )
    )
    if include_execution_history:
        # DB-backed execution history is best-effort and must not block health checks.
        try:
            from ..core.hil_db import get_async_session_maker

            session_maker = get_async_session_maker()
            async with session_maker() as db:
                execution_records = await load_last_execution_records(db)
            apply_execution_history(dashboard, execution_records)
        except Exception as exc:
            logger.warning("tool health execution history unavailable: %s", exc)

    report_path: str | None = None
    if write_report:
        report_path = await anyio.to_thread.run_sync(write_dashboard_report, dashboard)

    summary = dashboard.get("summary", {})
    degraded = int(summary.get("degraded", 0))
    unavailable = int(summary.get("unavailable", 0))
    status = "healthy" if degraded == 0 and unavailable == 0 else "degraded"
    return Response(
        success=True,
        data={
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "total_tools": registry.count(),
            **dashboard,
            "report_path": report_path,
        },
    )


@router.get("", response_model=Response)
async def list_tools(
    category: Optional[ToolCategory] = Query(None),
    autonomy_tier: Optional[int] = Query(None),
):
    """List available tools"""
    registry = get_tool_registry()

    try:
        if category:
            tools = registry.list_by_category(category)
        elif autonomy_tier is not None:
            tier = ToolAutonomyTier(autonomy_tier)
            tools = registry.list_by_autonomy_tier(tier)
        else:
            tools = registry.list_all()

        tool_data = [
            {
                "id": tool.id,
                "name": tool.name,
                "description": tool.description,
                "category": tool.category.value,
                "autonomy_tier": tool.autonomy_tier.value,
                "version": tool.version,
            }
            for tool in tools
        ]

        return Response(
            success=True,
            data={
                "tools": tool_data,
                "count": len(tool_data),
            },
        )

    except Exception as e:
        logger.error(f"Error listing tools: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/categories", response_model=Response)
async def list_categories():
    """List all tool categories"""
    categories = [
        {
            "id": cat.value,
            "name": cat.name,
        }
        for cat in ToolCategory
    ]

    return Response(
        success=True,
        data={"categories": categories},
    )


@router.get("/stats", response_model=Response)
async def get_tools_stats():
    """Get overall tools statistics"""
    registry = get_tool_registry()

    return Response(
        success=True,
        data=registry.stats(),
    )


@router.get("/catalog/list", response_model=Response)
async def list_tool_catalog(enabled_only: bool = Query(default=False)):
    entries = [entry.as_dict() for entry in list_catalog_entries(enabled_only=enabled_only)]
    return Response(
        success=True,
        data={"count": len(entries), "tools": entries},
    )


@router.get("/catalog/item/{tool_name}", response_model=Response)
async def get_tool_catalog_entry(tool_name: str):
    entry = get_catalog_entry(tool_name)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Catalog tool not found: {tool_name}")
    return Response(success=True, data=entry.as_dict())


@router.get("/item/{tool_id}", response_model=Response)
async def get_tool_info(tool_id: str):
    """Get information about a specific tool"""
    registry = get_tool_registry()
    tool = registry.get(tool_id)

    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_id}")

    return Response(
        success=True,
        data=tool.to_dict(),
    )


@router.get("/item/{tool_id}/schema", response_model=Response)
async def get_tool_schema(tool_id: str):
    """Get tool schema for LLM tool calling"""
    registry = get_tool_registry()
    schema = registry.get_schema(tool_id)

    if not schema:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_id}")

    return Response(
        success=True,
        data=schema,
    )


# Backward-compatible aliases retained after static route declarations.
@router.get("/{tool_id}", response_model=Response, include_in_schema=False)
async def get_tool_info_legacy(tool_id: str):
    return await get_tool_info(tool_id)


@router.get("/{tool_id}/schema", response_model=Response, include_in_schema=False)
async def get_tool_schema_legacy(tool_id: str):
    return await get_tool_schema(tool_id)


# ============================================================================
# Tool Execution Endpoints
# ============================================================================


@router.post("/{tool_id}/execute", response_model=Response)
async def execute_tool(
    tool_id: str,
    params: Dict[str, Any],
    run_id: Optional[str] = Query(None),
    program_id: Optional[str] = Query(None),
    certificate_id: Optional[str] = Query(None),
    method: Optional[str] = Query(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
    requested_user_id: Optional[str] = Query(None, alias="user_id"),
    current_user: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    """Execute a tool with given parameters"""
    registry = get_tool_registry()
    tool = registry.get(tool_id)

    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_id}")
    _ensure_tool_enabled(tool_id)
    if requested_user_id and requested_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="user_id must match authenticated principal")
    resolved_program_id, resolved_certificate_id = _resolve_authorization_hints(
        tool_id=tool_id,
        params=params,
        method=method,
        current_user=current_user,
        requested_program_id=program_id,
        requested_certificate_id=certificate_id,
    )
    try:
        await enforce_authorization_gates_async(
            tool_id,
            params,
            user_id=current_user.id,
            program_id=resolved_program_id,
            certificate_id=resolved_certificate_id,
            method=method,
        )
    except AuthorizationGateError as exc:
        raise HTTPException(status_code=403, detail=f"Authorization gate blocked execution: {exc}") from exc

    try:
        # Create execution context
        context = ToolExecutionContext(
            tool_id=tool_id,
            run_id=run_id,
            user_id=current_user.id,
            autonomy_tier=tool.autonomy_tier,
            requires_approval=tool.autonomy_tier != ToolAutonomyTier.TIER_0_AUTO,
        )

        # Check if approval is needed
        if context.requires_approval:
            await get_tool_execution_store().create_pending(
                execution_id=context.execution_id,
                tool_id=tool_id,
                params=params,
                run_id=run_id,
                user_id=current_user.id,
            )
            return Response(
                success=True,
                data={
                    "execution_id": context.execution_id,
                    "status": "pending_approval",
                    "message": "Tool execution requires approval",
                    "context": context.to_dict(),
                },
                status_code=202,
            )

        # Execute tool immediately (TIER_0_AUTO)
        result = tool.execute(**params)

        return Response(
            success=result.status == ToolStatus.COMPLETED,
            data={
                "execution_id": context.execution_id,
                "result": result.to_dict(),
            },
        )

    except Exception as e:
        logger.error(f"Error executing tool {tool_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{tool_id}/execute/async", response_model=Response)
async def execute_tool_async(
    tool_id: str,
    params: Dict[str, Any],
    background_tasks: BackgroundTasks,
    run_id: Optional[str] = Query(None),
    program_id: Optional[str] = Query(None),
    certificate_id: Optional[str] = Query(None),
    method: Optional[str] = Query(None),
    requested_user_id: Optional[str] = Query(None, alias="user_id"),
    current_user: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    """Execute a tool asynchronously"""
    registry = get_tool_registry()
    tool = registry.get(tool_id)

    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_id}")
    _ensure_tool_enabled(tool_id)
    if requested_user_id and requested_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="user_id must match authenticated principal")
    resolved_program_id, resolved_certificate_id = _resolve_authorization_hints(
        tool_id=tool_id,
        params=params,
        method=method,
        current_user=current_user,
        requested_program_id=program_id,
        requested_certificate_id=certificate_id,
    )
    try:
        await enforce_authorization_gates_async(
            tool_id,
            params,
            user_id=current_user.id,
            program_id=resolved_program_id,
            certificate_id=resolved_certificate_id,
            method=method,
        )
    except AuthorizationGateError as exc:
        raise HTTPException(status_code=403, detail=f"Authorization gate blocked execution: {exc}") from exc

    context = ToolExecutionContext(
        tool_id=tool_id,
        run_id=run_id,
        user_id=current_user.id,
    )

    async def run_async():
        try:
            result = tool.execute(**params)
            logger.info(f"Async execution completed: {tool_id} - {context.execution_id}")
            await get_tool_execution_store().create_pending(
                execution_id=context.execution_id,
                tool_id=tool_id,
                params=params,
                run_id=run_id,
                user_id=current_user.id,
            )
            await get_tool_execution_store().mark_completed(context.execution_id, result.to_dict())
        except Exception as e:
            logger.error(f"Async execution error: {str(e)}")

    background_tasks.add_task(run_async)

    return Response(
        success=True,
        data={
            "execution_id": context.execution_id,
            "status": "queued",
            "message": "Tool queued for async execution",
        },
        status_code=202,
    )


@router.post("/{tool_id}/approve", response_model=Response)
async def approve_tool_execution(
    tool_id: str,
    execution_id: str = Query(...),
    current_user: User = Depends(require_roles(ROLE_ANALYST, ROLE_ADMIN)),
):
    """Approve a pending tool execution"""
    registry = get_tool_registry()
    tool = registry.get(tool_id)

    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_id}")

    try:
        store = get_tool_execution_store()
        execution = await store.get(execution_id)
        if not execution or execution.tool_id != tool_id:
            raise HTTPException(status_code=404, detail="Execution request not found")
        if execution.status != "pending_approval":
            raise HTTPException(status_code=409, detail=f"Execution is not pending: {execution.status}")

        result = tool.execute(**execution.params)
        await store.mark_completed(execution_id, result.to_dict())

        return Response(
            success=True,
            data={
                "execution_id": execution_id,
                "status": "approved_and_executed",
                "approved_by": current_user.id,
                "approved_at": datetime.utcnow().isoformat(),
                "result": result.to_dict(),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving execution: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{tool_id}/reject", response_model=Response)
async def reject_tool_execution(
    tool_id: str,
    execution_id: str = Query(...),
    reason: Optional[str] = Query(None),
    current_user: User = Depends(require_roles(ROLE_ANALYST, ROLE_ADMIN)),
):
    """Reject a pending tool execution"""
    registry = get_tool_registry()
    tool = registry.get(tool_id)

    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_id}")

    try:
        store = get_tool_execution_store()
        execution = await store.get(execution_id)
        if not execution or execution.tool_id != tool_id:
            raise HTTPException(status_code=404, detail="Execution request not found")
        if execution.status != "pending_approval":
            raise HTTPException(status_code=409, detail=f"Execution is not pending: {execution.status}")
        await store.mark_rejected(execution_id, reason)

        return Response(
            success=True,
            data={
                "execution_id": execution_id,
                "status": "rejected",
                "rejected_by": current_user.id,
                "reason": reason,
                "rejected_at": datetime.utcnow().isoformat(),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting execution: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Orchestration Endpoints
# ============================================================================


@router.post("/orchestrate", response_model=Response)
async def orchestrate_tools(
    workflow: Dict[str, Any],
    run_id: Optional[str] = Query(None),
    _current_user: User = Depends(require_roles(ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN)),
):
    """Execute a workflow of tools (tool chaining)"""
    registry = get_tool_registry()

    try:
        # workflow format:
        # {
        #   "steps": [
        #     {"tool_id": "validator", "params": {...}},
        #     {"tool_id": "classifier", "params": {...}}
        #   ]
        # }

        steps = workflow.get("steps", [])
        results = []

        for i, step in enumerate(steps):
            tool_id = step.get("tool_id")
            params = step.get("params", {})

            tool = registry.get(tool_id)
            if not tool:
                return Response(
                    success=False,
                    data={
                        "step": i,
                        "error": f"Tool not found: {tool_id}",
                    },
                )

            result = tool.execute(**params)
            results.append(result.to_dict())

            # If step failed, stop workflow
            if result.status != ToolStatus.COMPLETED:
                break

        return Response(
            success=all(r["status"] == "completed" for r in results),
            data={
                "workflow_steps": len(steps),
                "completed_steps": len(results),
                "results": results,
            },
        )

    except Exception as e:
        logger.error(f"Error orchestrating tools: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Tool Management Endpoints
# ============================================================================


@router.delete("/{tool_id}", response_model=Response)
async def unregister_tool(
    tool_id: str,
    _: User = Depends(require_roles(ROLE_ADMIN)),
):
    """Unregister a tool"""
    registry = get_tool_registry()

    if registry.unregister(tool_id):
        return Response(
            success=True,
            data={"message": f"Tool unregistered: {tool_id}"},
        )
    else:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_id}")
