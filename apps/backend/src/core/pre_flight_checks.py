from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .kai_orchestrator import ScopeGuardian
from .secret_manager import get_secret_manager
from .tool_registry_catalog import get_catalog_entry
from .tools import ToolAutonomyTier
from .auth import User


class PreFlightCheckError(RuntimeError):
    pass


class PreFlightOutcome(str, Enum):
    ALLOW = "allow"
    REQUIRE_APPROVAL = "require_approval"
    BLOCK = "block"


@dataclass
class PreFlightContext:
    tool_id: str
    params: dict[str, Any]
    user: User
    registered_tier: ToolAutonomyTier
    method: str | None = None
    program_id: str | None = None
    mission_id: str | None = None
    phase_name: str | None = None
    mission_goal: str | None = None
    allow_tier3_override: bool = False


@dataclass
class PreFlightCheckResult:
    tool_id: str
    effective_tier: ToolAutonomyTier
    outcome: PreFlightOutcome
    requires_approval: bool
    target: str
    reason: str
    details: dict[str, Any] = field(default_factory=dict)


def _extract_target(params: dict[str, Any]) -> str:
    for key in ("target", "url", "domain", "host", "ip", "rhost"):
        value = params.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _normalize_tool_name(tool_id: str) -> str:
    return (
        tool_id.strip().lower()
        .replace("_", "")
        .replace("-", "")
        .replace("framework", "")
    )


def _tier_from_string(raw: str | None) -> ToolAutonomyTier | None:
    if not raw:
        return None
    mapping = {
        "TIER_0_AUTO": ToolAutonomyTier.TIER_0_AUTO,
        "TIER_1_NOTIFY": ToolAutonomyTier.TIER_1_NOTIFY,
        "TIER_2_APPROVE": ToolAutonomyTier.TIER_2_APPROVE,
        "TIER_3_HARD_STOP": ToolAutonomyTier.TIER_3_HARD_STOP,
    }
    return mapping.get(raw.strip().upper())


def _load_authorized_scope(path: str = "config/authorized_scope.json") -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {}
    try:
        payload = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def resolve_effective_tier(
    tool_id: str,
    registered_tier: ToolAutonomyTier,
    *,
    scope_path: str = "config/authorized_scope.json",
) -> ToolAutonomyTier:
    scope = _load_authorized_scope(scope_path)
    configured = scope.get("tool_autonomy_tiers")
    if not isinstance(configured, dict):
        return registered_tier

    normalized_tool = _normalize_tool_name(tool_id)
    configured_tier: ToolAutonomyTier | None = None
    for key, value in configured.items():
        if not isinstance(key, str):
            continue
        if _normalize_tool_name(key) == normalized_tool:
            configured_tier = _tier_from_string(str(value))
            if configured_tier is not None:
                break

    if configured_tier is None:
        return registered_tier

    # Always use stricter tier to avoid downgrades.
    return configured_tier if configured_tier.value >= registered_tier.value else registered_tier


def _ensure_user_permission(user: User, tier: ToolAutonomyTier, allow_tier3_override: bool) -> None:
    roles = {role.strip().lower() for role in user.roles}
    if tier in {ToolAutonomyTier.TIER_0_AUTO, ToolAutonomyTier.TIER_1_NOTIFY}:
        if not roles.intersection({"operator", "analyst", "admin"}):
            raise PreFlightCheckError("insufficient_role_for_tier")
        return
    if tier == ToolAutonomyTier.TIER_2_APPROVE:
        if not roles.intersection({"analyst", "admin"}):
            raise PreFlightCheckError("tier2_requires_analyst_or_admin")
        return
    if tier == ToolAutonomyTier.TIER_3_HARD_STOP:
        if "admin" not in roles:
            raise PreFlightCheckError("tier3_requires_admin")
        if not allow_tier3_override:
            raise PreFlightCheckError("tier3_requires_explicit_override")


async def _validate_scope(target: str, method: str | None) -> tuple[bool, str]:
    guardian = ScopeGuardian("config/authorized_scope.json")
    if method and guardian.allowed_methods and method not in guardian.allowed_methods:
        return False, "method_not_allowed_by_scope"
    if not target:
        return False, "missing_target"
    valid, reason = await guardian.validate_target(target)
    return valid, ("" if valid else reason)


def _validate_dependencies(tool_id: str, user: User) -> tuple[bool, str, list[str]]:
    entry = get_catalog_entry(tool_id)
    if entry is None:
        return True, "", []
    missing: list[str] = []
    manager = get_secret_manager()
    tenant_id = user.tenant_id if hasattr(user, "tenant_id") else None
    for secret_name in entry.api_keys_required:
        if not manager.get_optional(secret_name, tenant_id=tenant_id):
            missing.append(secret_name)
    if missing:
        return False, "missing_api_keys", missing
    return True, "", []


async def run_pre_flight_checks(context: PreFlightContext) -> PreFlightCheckResult:
    effective_tier = resolve_effective_tier(context.tool_id, context.registered_tier)
    target = _extract_target(context.params)

    _ensure_user_permission(context.user, effective_tier, context.allow_tier3_override)

    in_scope, scope_reason = await _validate_scope(target, context.method)
    if not in_scope:
        raise PreFlightCheckError(f"scope_check_failed:{scope_reason}")

    deps_ok, dep_reason, missing_keys = _validate_dependencies(context.tool_id, context.user)
    if not deps_ok:
        raise PreFlightCheckError(f"dependency_check_failed:{dep_reason}:{','.join(missing_keys)}")

    if effective_tier == ToolAutonomyTier.TIER_3_HARD_STOP and not context.allow_tier3_override:
        return PreFlightCheckResult(
            tool_id=context.tool_id,
            effective_tier=effective_tier,
            outcome=PreFlightOutcome.BLOCK,
            requires_approval=True,
            target=target,
            reason="tier3_hard_stop",
        )

    if effective_tier == ToolAutonomyTier.TIER_2_APPROVE:
        return PreFlightCheckResult(
            tool_id=context.tool_id,
            effective_tier=effective_tier,
            outcome=PreFlightOutcome.REQUIRE_APPROVAL,
            requires_approval=True,
            target=target,
            reason="tier2_approval_required",
            details={"mission_id": context.mission_id, "phase_name": context.phase_name},
        )

    if effective_tier == ToolAutonomyTier.TIER_3_HARD_STOP:
        return PreFlightCheckResult(
            tool_id=context.tool_id,
            effective_tier=effective_tier,
            outcome=PreFlightOutcome.REQUIRE_APPROVAL,
            requires_approval=True,
            target=target,
            reason="tier3_override_requires_special_approval",
            details={"override": True},
        )

    return PreFlightCheckResult(
        tool_id=context.tool_id,
        effective_tier=effective_tier,
        outcome=PreFlightOutcome.ALLOW,
        requires_approval=False,
        target=target,
        reason="preflight_passed",
    )
