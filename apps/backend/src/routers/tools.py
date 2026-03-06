"""
Tools API Router
Exposes all K1 tools via REST API with autonomy tier gating
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
import logging
from datetime import datetime

from ..core.tools import (
    get_registry,
    ToolCategory,
    ToolStatus,
    ToolAutonomyTier,
    ToolExecutionContext,
)
from ..core.toolpacks import get_toolpack_manager, ToolpackValidationError
from ..core.authorization_gate import enforce_authorization_gates, AuthorizationGateError
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
        # Register validation tools
        _registry.register(FindingValidatorTool())
        _registry.register(QuickClassifierTool())
        # Register analysis tools
        _registry.register(VulnerabilityAnalyzerTool())
        _registry.register(ChainAnalyzerTool())
        _registry.register(ProgramMatcherTool())
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
async def tools_health():
    """Health check for tools system"""
    registry = get_tool_registry()
    return Response(
        success=True,
        data={
            "status": "healthy",
            "total_tools": registry.count(),
            "timestamp": datetime.utcnow().isoformat(),
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


@router.get("/{tool_id}", response_model=Response)
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


@router.get("/{tool_id}/schema", response_model=Response)
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


# ============================================================================
# Tool Execution Endpoints
# ============================================================================


@router.post("/{tool_id}/execute", response_model=Response)
async def execute_tool(
    tool_id: str,
    params: Dict[str, Any],
    run_id: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
    program_id: Optional[str] = Query(None),
    certificate_id: Optional[str] = Query(None),
    method: Optional[str] = Query(None),
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    """Execute a tool with given parameters"""
    registry = get_tool_registry()
    tool = registry.get(tool_id)

    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_id}")
    _ensure_tool_enabled(tool_id)
    try:
        enforce_authorization_gates(
            tool_id,
            params,
            user_id=user_id,
            program_id=program_id,
            certificate_id=certificate_id,
            method=method,
        )
    except AuthorizationGateError as exc:
        raise HTTPException(status_code=403, detail=f"Authorization gate blocked execution: {exc}") from exc

    try:
        # Create execution context
        context = ToolExecutionContext(
            tool_id=tool_id,
            run_id=run_id,
            user_id=user_id,
            autonomy_tier=tool.autonomy_tier,
            requires_approval=tool.autonomy_tier != ToolAutonomyTier.TIER_0_AUTO,
        )

        # Check if approval is needed
        if context.requires_approval:
            get_tool_execution_store().create_pending(
                execution_id=context.execution_id,
                tool_id=tool_id,
                params=params,
                run_id=run_id,
                user_id=user_id,
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
    user_id: Optional[str] = Query(None),
    program_id: Optional[str] = Query(None),
    certificate_id: Optional[str] = Query(None),
    method: Optional[str] = Query(None),
):
    """Execute a tool asynchronously"""
    registry = get_tool_registry()
    tool = registry.get(tool_id)

    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_id}")
    _ensure_tool_enabled(tool_id)
    try:
        enforce_authorization_gates(
            tool_id,
            params,
            user_id=user_id,
            program_id=program_id,
            certificate_id=certificate_id,
            method=method,
        )
    except AuthorizationGateError as exc:
        raise HTTPException(status_code=403, detail=f"Authorization gate blocked execution: {exc}") from exc

    context = ToolExecutionContext(
        tool_id=tool_id,
        run_id=run_id,
        user_id=user_id,
    )

    def run_async():
        try:
            result = tool.execute(**params)
            logger.info(f"Async execution completed: {tool_id} - {context.execution_id}")
            get_tool_execution_store().create_pending(
                execution_id=context.execution_id,
                tool_id=tool_id,
                params=params,
                run_id=run_id,
                user_id=user_id,
            )
            get_tool_execution_store().mark_completed(context.execution_id, result.to_dict())
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
    user_id: Optional[str] = Query(None),
):
    """Approve a pending tool execution"""
    registry = get_tool_registry()
    tool = registry.get(tool_id)

    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_id}")

    try:
        store = get_tool_execution_store()
        execution = store.get(execution_id)
        if not execution or execution.tool_id != tool_id:
            raise HTTPException(status_code=404, detail="Execution request not found")
        if execution.status != "pending_approval":
            raise HTTPException(status_code=409, detail=f"Execution is not pending: {execution.status}")

        result = tool.execute(**execution.params)
        store.mark_completed(execution_id, result.to_dict())

        return Response(
            success=True,
            data={
                "execution_id": execution_id,
                "status": "approved_and_executed",
                "approved_by": user_id,
                "approved_at": datetime.utcnow().isoformat(),
                "result": result.to_dict(),
            },
        )

    except Exception as e:
        logger.error(f"Error approving execution: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{tool_id}/reject", response_model=Response)
async def reject_tool_execution(
    tool_id: str,
    execution_id: str = Query(...),
    reason: Optional[str] = Query(None),
    user_id: Optional[str] = Query(None),
):
    """Reject a pending tool execution"""
    registry = get_tool_registry()
    tool = registry.get(tool_id)

    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_id}")

    try:
        store = get_tool_execution_store()
        execution = store.get(execution_id)
        if not execution or execution.tool_id != tool_id:
            raise HTTPException(status_code=404, detail="Execution request not found")
        if execution.status != "pending_approval":
            raise HTTPException(status_code=409, detail=f"Execution is not pending: {execution.status}")
        store.mark_rejected(execution_id, reason)

        return Response(
            success=True,
            data={
                "execution_id": execution_id,
                "status": "rejected",
                "rejected_by": user_id,
                "reason": reason,
                "rejected_at": datetime.utcnow().isoformat(),
            },
        )

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
    user_id: Optional[str] = Query(None),
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
async def unregister_tool(tool_id: str):
    """Unregister a tool"""
    registry = get_tool_registry()

    if registry.unregister(tool_id):
        return Response(
            success=True,
            data={"message": f"Tool unregistered: {tool_id}"},
        )
    else:
        raise HTTPException(status_code=404, detail=f"Tool not found: {tool_id}")
