from __future__ import annotations

import inspect
from dataclasses import dataclass
from functools import wraps
from typing import Any, Awaitable, Callable

from fastapi import HTTPException

from .approval_request import ApprovalScope
from .hil_approval_gateway import get_hil_approval_gateway
from .pre_flight_checks import (
    PreFlightCheckError,
    PreFlightContext,
    PreFlightOutcome,
    run_pre_flight_checks,
)
from .tools import ToolAutonomyTier


@dataclass
class AutonomyEnforcementResult:
    allowed: bool
    requires_approval: bool
    status: str
    message: str
    details: dict[str, Any]


class AutonomyTierEnforcer:
    async def enforce(
        self,
        *,
        tool_id: str,
        params: dict[str, Any],
        user: Any,
        registered_tier: ToolAutonomyTier,
        method: str | None = None,
        mission_id: str | None = None,
        phase_name: str | None = None,
        mission_goal: str | None = None,
        allow_tier3_override: bool = False,
        approval_scope: ApprovalScope = ApprovalScope.TOOL,
    ) -> AutonomyEnforcementResult:
        try:
            preflight = await run_pre_flight_checks(
                PreFlightContext(
                    tool_id=tool_id,
                    params=params,
                    user=user,
                    registered_tier=registered_tier,
                    method=method,
                    mission_id=mission_id,
                    phase_name=phase_name,
                    mission_goal=mission_goal,
                    allow_tier3_override=allow_tier3_override,
                )
            )
        except PreFlightCheckError as exc:
            return AutonomyEnforcementResult(
                allowed=False,
                requires_approval=False,
                status="blocked",
                message=str(exc),
                details={},
            )

        if preflight.outcome == PreFlightOutcome.ALLOW:
            return AutonomyEnforcementResult(
                allowed=True,
                requires_approval=False,
                status="allowed",
                message=preflight.reason,
                details={
                    "effective_tier": preflight.effective_tier.name,
                    "target": preflight.target,
                },
            )

        if preflight.outcome == PreFlightOutcome.BLOCK:
            return AutonomyEnforcementResult(
                allowed=False,
                requires_approval=True,
                status="blocked",
                message=preflight.reason,
                details={
                    "effective_tier": preflight.effective_tier.name,
                    "target": preflight.target,
                },
            )

        impact = "high" if preflight.effective_tier == ToolAutonomyTier.TIER_3_HARD_STOP else "medium"
        request = await get_hil_approval_gateway().create_approval_request(
            execution_id=str(params.get("_execution_id", "")),
            tool_id=tool_id,
            requested_by=str(getattr(user, "id", "unknown")),
            target=preflight.target,
            autonomy_tier=preflight.effective_tier.name,
            estimated_impact=impact,
            mission_id=mission_id,
            phase_name=phase_name,
            mission_goal=mission_goal,
            scope=approval_scope,
            metadata={
                "method": method,
                "preflight_reason": preflight.reason,
            },
        )
        return AutonomyEnforcementResult(
            allowed=False,
            requires_approval=True,
            status="pending_approval",
            message=preflight.reason,
            details={
                "approval_id": request.approval_id,
                "expires_at": request.expires_at.isoformat(),
                "effective_tier": preflight.effective_tier.name,
                "approval_scope": approval_scope.value,
            },
        )


def get_autonomy_tier_enforcer() -> AutonomyTierEnforcer:
    return AutonomyTierEnforcer()


def require_autonomy_approval(minimum_tier: ToolAutonomyTier = ToolAutonomyTier.TIER_0_AUTO):
    """
    Decorator for async tool execution methods.
    Expects `execution_context` keyword argument with:
      tool_id, params, user, registered_tier, method, mission_id, phase_name, mission_goal,
      allow_tier3_override, approval_scope.
    """

    def _decorator(func: Callable[..., Awaitable[Any]]):
        if not inspect.iscoroutinefunction(func):
            raise TypeError("require_autonomy_approval only supports async callables")

        @wraps(func)
        async def _wrapped(*args: Any, **kwargs: Any):
            execution_context = kwargs.get("execution_context")
            if not isinstance(execution_context, dict):
                raise HTTPException(status_code=500, detail="missing_execution_context")

            registered_tier = execution_context.get("registered_tier", ToolAutonomyTier.TIER_2_APPROVE)
            if isinstance(registered_tier, int):
                registered_tier = ToolAutonomyTier(registered_tier)
            if not isinstance(registered_tier, ToolAutonomyTier):
                registered_tier = ToolAutonomyTier.TIER_2_APPROVE

            if registered_tier.value < minimum_tier.value:
                raise HTTPException(
                    status_code=403,
                    detail=f"minimum autonomy tier {minimum_tier.name} required",
                )

            enforcer = get_autonomy_tier_enforcer()
            raw_scope = execution_context.get("approval_scope", ApprovalScope.TOOL)
            if isinstance(raw_scope, str):
                approval_scope = ApprovalScope.PHASE if raw_scope.strip().lower() == "phase" else ApprovalScope.TOOL
            elif isinstance(raw_scope, ApprovalScope):
                approval_scope = raw_scope
            else:
                approval_scope = ApprovalScope.TOOL
            result = await enforcer.enforce(
                tool_id=str(execution_context.get("tool_id")),
                params=dict(execution_context.get("params") or {}),
                user=execution_context.get("user"),
                registered_tier=registered_tier,
                method=execution_context.get("method"),
                mission_id=execution_context.get("mission_id"),
                phase_name=execution_context.get("phase_name"),
                mission_goal=execution_context.get("mission_goal"),
                allow_tier3_override=bool(execution_context.get("allow_tier3_override", False)),
                approval_scope=approval_scope,
            )
            kwargs["_autonomy_enforcement"] = result
            return await func(*args, **kwargs)

        return _wrapped

    return _decorator
