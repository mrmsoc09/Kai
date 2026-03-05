"""Dispatch tool executions to Celery with rate limits and approvals."""
from __future__ import annotations

from typing import Dict, Any, Optional
from fastapi import HTTPException

from apps.backend.src.worker.celery_app import run_tool_task
from apps.backend.src.core.tools import get_registry, initialize_default_tools, ToolAutonomyTier
from apps.backend.src.core.kai_security_guardrails import (
    get_tool_tier,
    ToolRiskTier,
)
from apps.backend.src.core.toolpacks import get_toolpack_manager, ToolpackValidationError
from apps.backend.src.core.authorization_gate import (
    enforce_authorization_gates,
    AuthorizationGateError,
)


class ToolRunner:
    """Thin async-friendly facade to enqueue tool runs."""

    def __init__(self, default_queue: str = "tools"):
        self.default_queue = default_queue

    def enqueue(
        self,
        tool_id: str,
        params: Dict[str, Any],
        program_id: Optional[str] = None,
        certificate_id: Optional[str] = None,
        method: Optional[str] = None,
        user_id: Optional[str] = None,
        require_approval: bool = True,
        approved: bool = False,
    ) -> str:
        initialize_default_tools()
        registry = get_registry()
        manager = get_toolpack_manager()
        try:
            if manager.config is None:
                manager.load()
                manager.resolve_mappings(registry.get_all_schemas().keys())
        except ToolpackValidationError as exc:
            raise HTTPException(status_code=503, detail=f"Toolpack policy unavailable: {exc}") from exc

        tool = registry.get(tool_id)
        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool not found: {tool_id}")
        if not manager.is_adapter_enabled(tool_id):
            raise HTTPException(status_code=403, detail=f"Tool disabled by toolpack policy: {tool_id}")
        try:
            enforce_authorization_gates(
                tool_id,
                params,
                program_id=program_id,
                certificate_id=certificate_id,
                method=method,
                user_id=user_id,
            )
        except AuthorizationGateError as exc:
            raise HTTPException(status_code=403, detail=f"Authorization gate blocked execution: {exc}") from exc

        risk_tier = get_tool_tier(tool_id)
        needs_approval = risk_tier == ToolRiskTier.TIER_2_INTRUSIVE or tool.autonomy_tier in {
            ToolAutonomyTier.TIER_2_APPROVE,
            ToolAutonomyTier.TIER_3_HARD_STOP,
        }
        if require_approval and needs_approval and not approved:
            raise HTTPException(status_code=403, detail="Approval required for this tool/run")

        queue = self.default_queue
        if risk_tier == ToolRiskTier.TIER_2_INTRUSIVE:
            queue = "intrusive"

        async_result = run_tool_task.apply_async((tool_id, params), queue=queue)
        return async_result.id


tool_runner = ToolRunner()
