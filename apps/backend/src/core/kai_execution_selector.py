"""
Deterministic execution substrate selector for Kai MissionRuntime.

This module enforces governance-first substrate selection based on the
policy defined in docs/architecture/kai_execution_selector_policy.md.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class ExecutionSubstrate(str, Enum):
    LANGGRAPH_PRIMARY = "LANGGRAPH_PRIMARY"
    DEEPAGENTS_SPECIALIST = "DEEPAGENTS_SPECIALIST"
    PRAISON_EXTERNAL = "PRAISON_EXTERNAL"
    MISSIONRUNTIME_CUSTOM = "MISSIONRUNTIME_CUSTOM"
    DENY = "DENY"


_ALLOWED_COMPLEXITY = {"low", "medium", "high"}
_ALLOWED_SCOPE_SENSITIVITY = {"low", "medium", "high"}
_ALLOWED_PRIVILEGE = {"read", "write", "intrusive"}
_ALLOWED_TENANT_MODE = {"single", "multi"}
_ALLOWED_TELEMETRY = {"standard", "strict"}
_ALLOWED_PERF_KEYS = {"failure_rate", "p95_latency_ms", "retry_frequency"}

_FALLBACK_BY_PRIMARY: dict[str, str] = {
    ExecutionSubstrate.DEEPAGENTS_SPECIALIST.value: ExecutionSubstrate.LANGGRAPH_PRIMARY.value,
    ExecutionSubstrate.PRAISON_EXTERNAL.value: ExecutionSubstrate.LANGGRAPH_PRIMARY.value,
    ExecutionSubstrate.MISSIONRUNTIME_CUSTOM.value: ExecutionSubstrate.LANGGRAPH_PRIMARY.value,
    ExecutionSubstrate.LANGGRAPH_PRIMARY.value: ExecutionSubstrate.MISSIONRUNTIME_CUSTOM.value,
    ExecutionSubstrate.DENY.value: ExecutionSubstrate.DENY.value,
}


def _normalized_str(value: Any, *, allowed: set[str], default: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in allowed:
        return normalized
    return default


def _normalized_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
    return bool(value)


def _normalized_int(value: Any, default: int, minimum: int = 0) -> int:
    try:
        return max(minimum, int(value))
    except (TypeError, ValueError):
        return default


def _normalize_risk_band(value: Any, default: int = 1) -> int:
    try:
        risk_band = int(value)
    except (TypeError, ValueError):
        risk_band = default
    return max(0, min(3, risk_band))


def _normalize_performance_profile(value: Any) -> dict[str, dict[str, float]]:
    if not isinstance(value, Mapping):
        return {}
    profile: dict[str, dict[str, float]] = {}
    for substrate_raw, metrics_raw in value.items():
        if not isinstance(metrics_raw, Mapping):
            continue
        substrate = str(substrate_raw or "").strip().upper()
        if not substrate:
            continue
        normalized_metrics: dict[str, float] = {}
        for key, metric_val in metrics_raw.items():
            metric_key = str(key or "").strip().lower()
            if metric_key not in _ALLOWED_PERF_KEYS:
                continue
            try:
                normalized_metrics[metric_key] = float(metric_val)
            except (TypeError, ValueError):
                continue
        if normalized_metrics:
            profile[substrate] = normalized_metrics
    return profile


def normalize_selector_inputs(raw_inputs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """
    Normalize selector inputs into deterministic, bounded values.
    """
    src = raw_inputs or {}
    return {
        "risk_band": _normalize_risk_band(src.get("risk_band"), default=1),
        "scope_sensitivity": _normalized_str(
            src.get("scope_sensitivity"),
            allowed=_ALLOWED_SCOPE_SENSITIVITY,
            default="medium",
        ),
        "needs_resume": _normalized_bool(src.get("needs_resume"), default=True),
        "workflow_complexity": _normalized_str(
            src.get("workflow_complexity"),
            allowed=_ALLOWED_COMPLEXITY,
            default="medium",
        ),
        "requires_protocol_bridge": _normalized_bool(src.get("requires_protocol_bridge"), default=False),
        "requires_specialist_decomposition": _normalized_bool(
            src.get("requires_specialist_decomposition"), default=False
        ),
        "latency_slo_ms": _normalized_int(src.get("latency_slo_ms"), default=1000, minimum=0),
        "is_stateless": _normalized_bool(src.get("is_stateless"), default=False),
        "tool_privilege_level": _normalized_str(
            src.get("tool_privilege_level"),
            allowed=_ALLOWED_PRIVILEGE,
            default="read",
        ),
        "tenant_mode": _normalized_str(
            src.get("tenant_mode"),
            allowed=_ALLOWED_TENANT_MODE,
            default="single",
        ),
        "telemetry_required": _normalized_str(
            src.get("telemetry_required"),
            allowed=_ALLOWED_TELEMETRY,
            default="standard",
        ),
        "scope_authorized": _normalized_bool(src.get("scope_authorized"), default=True),
        "requested_backend": str(src.get("requested_backend") or "").strip().lower(),
        "stage_id": str(src.get("stage_id") or "").strip(),
        "node_id": str(src.get("node_id") or "").strip(),
        "execution_mode": str(src.get("execution_mode") or "live").strip().lower(),
        "performance_profile": _normalize_performance_profile(src.get("performance_profile")),
    }


def select_execution_substrate(raw_inputs: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """
    Deterministically select substrate and required guardrails.
    """
    inputs = normalize_selector_inputs(raw_inputs)
    guards: list[str] = ["scope_validation_required", "wrapper_only_execution"]
    audit_tags: list[str] = [
        f"risk_band:{inputs['risk_band']}",
        f"workflow_complexity:{inputs['workflow_complexity']}",
        f"tenant_mode:{inputs['tenant_mode']}",
        f"execution_mode:{inputs['execution_mode']}",
    ]
    justification = "Default LangGraph selection."
    selected = ExecutionSubstrate.LANGGRAPH_PRIMARY.value

    # Hard guard: scope rejection.
    if not inputs["scope_authorized"]:
        return {
            "selected_substrate": ExecutionSubstrate.DENY.value,
            "fallback_substrate": ExecutionSubstrate.DENY.value,
            "policy_justification": "Scope validation failed; execution denied.",
            "required_guards": guards + ["scope_denied"],
            "audit_tags": audit_tags + ["selector:deny_scope"],
            "inputs": inputs,
            "denied": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Hard guard: high-risk operations require governance approval.
    if inputs["risk_band"] >= 3 or inputs["tool_privilege_level"] == "intrusive":
        guards.append("governance_approval_required")

    # Hard guard: multi-tenant host shell/filesystem backends are denied.
    if inputs["tenant_mode"] == "multi" and inputs["requested_backend"] in {
        "host_shell",
        "local_filesystem",
        "filesystem",
        "shell",
    }:
        return {
            "selected_substrate": ExecutionSubstrate.DENY.value,
            "fallback_substrate": ExecutionSubstrate.DENY.value,
            "policy_justification": "Requested backend is unsafe in multi-tenant mode.",
            "required_guards": guards + ["multi_tenant_backend_denied"],
            "audit_tags": audit_tags + ["selector:deny_backend"],
            "inputs": inputs,
            "denied": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Hard guard: resumable jobs must remain on checkpoint-capable substrate.
    if inputs["needs_resume"]:
        guards.append("checkpoint_resume_required")

    # Hard guard: protocol bridge is only via Praison external bridge.
    if inputs["requires_protocol_bridge"]:
        selected = ExecutionSubstrate.PRAISON_EXTERNAL.value
        justification = "Protocol bridge required; selecting bounded Praison adapter path."
    else:
        # Deterministic ordered rules.
        if (
            inputs["is_stateless"]
            and inputs["latency_slo_ms"] <= 300
            and inputs["workflow_complexity"] == "low"
            and inputs["tool_privilege_level"] == "read"
            and not inputs["needs_resume"]
        ):
            selected = ExecutionSubstrate.MISSIONRUNTIME_CUSTOM.value
            justification = "Stateless low-latency read-only request; selecting MissionRuntime custom path."
        elif (
            inputs["requires_specialist_decomposition"]
            and inputs["risk_band"] <= 2
        ):
            selected = ExecutionSubstrate.DEEPAGENTS_SPECIALIST.value
            justification = "Specialist decomposition requested within acceptable risk band."
        else:
            selected = ExecutionSubstrate.LANGGRAPH_PRIMARY.value
            justification = "Stateful/default path; selecting LangGraph as mission authority."

    # Optional deterministic performance override from benchmark profile.
    performance_profile = inputs.get("performance_profile", {})
    if isinstance(performance_profile, dict):
        selected_profile = performance_profile.get(selected, {})
        if isinstance(selected_profile, dict):
            failure_rate = float(selected_profile.get("failure_rate", 0.0) or 0.0)
            retry_frequency = float(selected_profile.get("retry_frequency", 0.0) or 0.0)
            p95_latency_ms = float(selected_profile.get("p95_latency_ms", 0.0) or 0.0)
            fallback_candidate = _FALLBACK_BY_PRIMARY.get(selected, ExecutionSubstrate.LANGGRAPH_PRIMARY.value)

            if (
                selected != ExecutionSubstrate.DENY.value
                and fallback_candidate != selected
                and (failure_rate >= 0.20 or retry_frequency >= 0.20)
            ):
                audit_tags.append("selector:perf_reliability_override")
                guards.append("performance_reliability_failover")
                justification = (
                    f"{justification} Reliability override applied from benchmark profile "
                    f"(failure_rate={failure_rate:.2f}, retry_frequency={retry_frequency:.2f})."
                )
                selected = fallback_candidate
            elif (
                selected in {
                    ExecutionSubstrate.DEEPAGENTS_SPECIALIST.value,
                    ExecutionSubstrate.PRAISON_EXTERNAL.value,
                }
                and fallback_candidate != selected
                and inputs["latency_slo_ms"] > 0
                and p95_latency_ms > (inputs["latency_slo_ms"] * 2.0)
            ):
                audit_tags.append("selector:perf_latency_override")
                guards.append("performance_latency_failover")
                justification = (
                    f"{justification} Latency override applied from benchmark profile "
                    f"(p95_latency_ms={p95_latency_ms:.0f}, slo_ms={inputs['latency_slo_ms']})."
                )
                selected = fallback_candidate

    return {
        "selected_substrate": selected,
        "fallback_substrate": _FALLBACK_BY_PRIMARY.get(selected, ExecutionSubstrate.LANGGRAPH_PRIMARY.value),
        "policy_justification": justification,
        "required_guards": sorted(set(guards)),
        "audit_tags": audit_tags + [f"selector:{selected.lower()}"],
        "inputs": inputs,
        "denied": False,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def selector_artifact_for_stage(
    *,
    stage_id: str,
    node_id: str,
    selector_inputs: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Emit a normalized selector artifact for audit/state persistence.
    """
    decision = select_execution_substrate(selector_inputs)
    return {
        "type": "execution_selector_policy",
        "stage_id": stage_id,
        "node_id": node_id,
        "selected_substrate": decision["selected_substrate"],
        "fallback_substrate": decision["fallback_substrate"],
        "policy_justification": decision["policy_justification"],
        "required_guards": list(decision.get("required_guards", [])),
        "audit_tags": list(decision.get("audit_tags", [])),
        "selector_inputs": decision.get("inputs", {}),
        "denied": bool(decision.get("denied", False)),
        "timestamp": decision.get("timestamp"),
    }
