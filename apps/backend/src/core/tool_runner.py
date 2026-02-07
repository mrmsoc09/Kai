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


class ToolRunner:
    """Thin async-friendly facade to enqueue tool runs."""

    def __init__(self, default_queue: str = "tools"):
        self.default_queue = default_queue

    def enqueue(
        self,
        tool_id: str,
        params: Dict[str, Any],
        require_approval: bool = True,
        approved: bool = False,
    ) -> str:
        initialize_default_tools()
        registry = get_registry()
        tool = registry.get(tool_id)
        if not tool:
            raise HTTPException(status_code=404, detail=f"Tool not found: {tool_id}")

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
