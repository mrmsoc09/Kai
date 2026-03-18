"""Dispatch tool executions to Celery with rate limits and approvals."""
from __future__ import annotations

import hashlib
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
from apps.backend.src.core.hook_registry import get_hook_registry
from apps.backend.src.core.praison_governor import PraisonGovernanceError


class ToolRunner:
    """Thin async-friendly facade to enqueue tool runs."""

    def __init__(self, default_queue: str = "tools"):
        self.default_queue = default_queue

    def _get_scope_hash(self) -> str:
        """Get SHA-256 hash of the current scope policy file."""
        from apps.backend.src.core.scope_guardrails import default_scope_policy_path
        path = default_scope_policy_path()
        if not path.exists():
            return "none"
        try:
            return hashlib.sha256(path.read_bytes()).hexdigest()
        except Exception:
            return "error"

    def enqueue(
        self,
        tool_id: str,
        params: Dict[str, Any],
        program_id: Optional[str] = None,
        certificate_id: Optional[str] = None,
        method: Optional[str] = None,
        user_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        require_approval: bool = True,
        approved: bool = False,
    ) -> str:
        initialize_default_tools()
        hooks = get_hook_registry()
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
                workflow_id=workflow_id,
            )
        except AuthorizationGateError as exc:
            raise HTTPException(status_code=403, detail=f"Authorization gate blocked execution: {exc}") from exc

        # Compute risk tier before safety gate so PraisonAI governor can use it.
        risk_tier = get_tool_tier(tool_id)

        # Map ToolRiskTier + ToolAutonomyTier to a single 0-3 band integer
        # that PraisonGovernor understands. Take the maximum of both signals.
        _RISK_TIER_TO_BAND: Dict[str, int] = {
            ToolRiskTier.TIER_0_SAFE.value: 0,
            ToolRiskTier.TIER_1_NOTIFY.value: 1,
            ToolRiskTier.TIER_2_INTRUSIVE.value: 2,
        }
        # ToolAutonomyTier values are integers 0-3; take max of both signals.
        _risk_band = _RISK_TIER_TO_BAND.get(risk_tier.value, 0)
        _autonomy_band = (
            tool.autonomy_tier.value
            if hasattr(tool.autonomy_tier, "value") and isinstance(tool.autonomy_tier.value, int)
            else 0
        )
        effective_band = max(_risk_band, _autonomy_band)

        try:
            hook_ctx = hooks.run(
                "safety_gate",
                {
                    "hook_type": "safety_gate",
                    "tool_id": tool_id,
                    "run_id": params.get("run_id"),
                    "status": "pending",
                    # Enriched context for PraisonAI governance hook
                    "tool_tier": effective_band,
                    "program_id": program_id or "",
                    "workflow_id": workflow_id or "",
                    "user_id": user_id or "",
                    "target": params.get("target") or params.get("domain") or params.get("host") or "",
                    "params": params,
                },
            )
        except PraisonGovernanceError as exc:
            raise HTTPException(
                status_code=403,
                detail=f"Governance gate blocked execution: {exc}",
            ) from exc
        params = dict(params)
        params.update(hook_ctx.get("params_patch") or {})

        needs_approval = risk_tier == ToolRiskTier.TIER_2_INTRUSIVE or tool.autonomy_tier in {
            ToolAutonomyTier.TIER_2_APPROVE,
            ToolAutonomyTier.TIER_3_HARD_STOP,
        }
        hooks.run(
            "approval_gate",
            {
                "hook_type": "approval_gate",
                "tool_id": tool_id,
                "run_id": params.get("run_id"),
                "status": "required" if needs_approval else "not_required",
            },
        )
        if require_approval and needs_approval and not approved:
            raise HTTPException(status_code=403, detail="Approval required for this tool/run")

        hooks.run(
            "pre_run",
            {
                "hook_type": "pre_run",
                "tool_id": tool_id,
                "run_id": params.get("run_id"),
                "status": "queued",
            },
        )
        queue = self.default_queue
        if risk_tier == ToolRiskTier.TIER_2_INTRUSIVE:
            queue = "intrusive"

        async_result = run_tool_task.apply_async(
            (tool_id, params),
            queue=queue,
            kwargs={
                "user_id": user_id or "",
                "program_id": program_id or "",
                "certificate_id": certificate_id or "",
                "workflow_id": workflow_id or "",
                "scope_policy_hash": self._get_scope_hash(),
            },
        )
        return async_result.id


tool_runner = ToolRunner()
