"""
Canonical persona/agent contract validation for Kai runtime enforcement.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


_ALLOWED_CLASSES = {"governor", "director", "coordinator", "specialist"}
_ALLOWED_APPROVAL_POLICIES = {"always", "on_request", "never"}
_ALLOWED_AUTONOMY = {"suggest", "auto_edit", "full_auto"}
_ALLOWED_MEMORY_SCOPE = {"session", "phase", "workflow", "mission", "persistent"}
_ALLOWED_DELEGATION_SCOPE = {"none", "phase", "global"}

_CRITICAL_LOSS_CODES = {
    "LOSS_APPROVAL_SEMANTICS",
    "LOSS_DELEGATION_SCOPE",
    "LOSS_MEMORY_ISOLATION",
    "LOSS_TOOL_DENYLIST",
    "LOSS_AUDIT_ATTRIBUTION",
}


@dataclass(frozen=True)
class TranslationLossWarning:
    code: str
    severity: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "severity": self.severity, "message": self.message}


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _add_error(errors: list[str], field: str, message: str) -> None:
    errors.append(f"{field}: {message}")


def _emit_warning(
    warnings: list[TranslationLossWarning],
    code: str,
    message: str,
    *,
    severity: str = "critical",
) -> None:
    warnings.append(TranslationLossWarning(code=code, severity=severity, message=message))


def validate_persona_contract(
    payload: Mapping[str, Any] | None,
    *,
    tenant_mode: str = "single",
) -> dict[str, Any]:
    """
    Validate canonical persona schema and detect translation-loss hazards.
    Blocks deployment on schema errors or critical translation-loss warnings.
    """
    raw = dict(payload or {})
    errors: list[str] = []
    warnings: list[TranslationLossWarning] = []

    required = (
        "persona_id",
        "name",
        "class",
        "objective",
        "instructions",
        "capabilities",
        "policy",
        "memory",
        "delegation",
        "handoff",
        "observability",
        "compatibility",
    )
    for key in required:
        if key not in raw:
            _add_error(errors, key, "field is required")

    persona_class = str(raw.get("class") or "").strip().lower()
    if persona_class not in _ALLOWED_CLASSES:
        _add_error(errors, "class", f"must be one of {sorted(_ALLOWED_CLASSES)}")

    capabilities = _dict(raw.get("capabilities"))
    tools_allowed = set(_list_str(capabilities.get("tools_allowed")))
    tools_denied = set(_list_str(capabilities.get("tools_denied")))
    if tools_allowed.intersection(tools_denied):
        _add_error(errors, "capabilities", "tools_allowed and tools_denied overlap")

    policy = _dict(raw.get("policy"))
    approval_policy = str(policy.get("approval_policy") or "").strip().lower()
    if approval_policy and approval_policy not in _ALLOWED_APPROVAL_POLICIES:
        _add_error(errors, "policy.approval_policy", f"must be one of {sorted(_ALLOWED_APPROVAL_POLICIES)}")

    autonomy_mode = str(policy.get("autonomy_mode") or "").strip().lower()
    if autonomy_mode and autonomy_mode not in _ALLOWED_AUTONOMY:
        _add_error(errors, "policy.autonomy_mode", f"must be one of {sorted(_ALLOWED_AUTONOMY)}")

    memory = _dict(raw.get("memory"))
    memory_scope = str(memory.get("scope") or "").strip().lower()
    if memory_scope and memory_scope not in _ALLOWED_MEMORY_SCOPE:
        _add_error(errors, "memory.scope", f"must be one of {sorted(_ALLOWED_MEMORY_SCOPE)}")

    delegation = _dict(raw.get("delegation"))
    delegation_scope = str(delegation.get("delegation_scope") or "none").strip().lower()
    if delegation_scope not in _ALLOWED_DELEGATION_SCOPE:
        _add_error(errors, "delegation.delegation_scope", f"must be one of {sorted(_ALLOWED_DELEGATION_SCOPE)}")
    if persona_class == "specialist" and delegation_scope != "none":
        _add_error(errors, "delegation.delegation_scope", "specialist personas must use delegation_scope=none")

    observability = _dict(raw.get("observability"))
    emit_metrics = bool(observability.get("emit_metrics", False))

    compatibility = _dict(raw.get("compatibility"))
    framework_targets = {entry.lower() for entry in _list_str(compatibility.get("framework_targets"))}
    external_targets = framework_targets.intersection({"praison", "crewai", "langstudio"})

    # Translation-loss checks (critical categories block deployment).
    if persona_class == "governor" and approval_policy != "always":
        _emit_warning(
            warnings,
            "LOSS_APPROVAL_SEMANTICS",
            "Governor persona without approval_policy=always loses approval authority semantics.",
        )

    if tools_denied and "crewai" in framework_targets:
        _emit_warning(
            warnings,
            "LOSS_TOOL_DENYLIST",
            "CrewAI target may not preserve denylist semantics without Kai wrapper enforcement.",
        )

    if delegation_scope == "global" and "crewai" in framework_targets:
        _emit_warning(
            warnings,
            "LOSS_DELEGATION_SCOPE",
            "Global delegation in CrewAI target risks delegation-boundary loss.",
        )

    if tenant_mode == "multi" and memory_scope == "persistent" and bool(memory.get("persistence", False)) and external_targets:
        _emit_warning(
            warnings,
            "LOSS_MEMORY_ISOLATION",
            "Persistent memory with external targets is unsafe for multi-tenant deployments.",
        )

    if external_targets and not emit_metrics:
        _emit_warning(
            warnings,
            "LOSS_AUDIT_ATTRIBUTION",
            "External targets require metrics emission for audit attribution.",
        )

    warning_dicts = [warning.to_dict() for warning in warnings]
    critical_warnings = [warning for warning in warning_dicts if warning["code"] in _CRITICAL_LOSS_CODES]
    blocked = bool(errors or critical_warnings)
    block_reasons = list(errors) + [w["code"] for w in critical_warnings]

    return {
        "valid": not errors,
        "blocked": blocked,
        "errors": errors,
        "translation_loss_warnings": warning_dicts,
        "block_reasons": block_reasons,
        "normalized": {
            "persona_id": str(raw.get("persona_id") or "").strip(),
            "class": persona_class,
            "approval_policy": approval_policy or "on_request",
            "autonomy_mode": autonomy_mode or "suggest",
            "memory_scope": memory_scope or "session",
            "delegation_scope": delegation_scope,
            "framework_targets": sorted(framework_targets),
            "tenant_mode": tenant_mode,
        },
    }
