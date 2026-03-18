from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, List
import json
import os


HookCallback = Callable[[Dict[str, Any]], Dict[str, Any] | None]

# Tool execution hooks (original)
_TOOL_HOOK_TYPES = {"pre_run", "post_run", "approval_gate", "retry_gate", "safety_gate"}

# Agent lifecycle hooks (PraisonAI agent control plane)
# agent_spawn       — fires when an agent is instantiated via PraisonAgentRegistry
# agent_handoff     — fires when execution transfers between agents
# agent_memory_write — fires when an agent writes to shared memory
# agent_external_call — fires when an agent initiates an external network call
_AGENT_HOOK_TYPES = {"agent_spawn", "agent_handoff", "agent_memory_write", "agent_external_call"}

HOOK_TYPES = _TOOL_HOOK_TYPES | _AGENT_HOOK_TYPES


@dataclass(frozen=True)
class HookSpec:
    hook_type: str
    name: str
    order: int
    callback: HookCallback


class HookRegistry:
    def __init__(self) -> None:
        self._hooks: Dict[str, List[HookSpec]] = {kind: [] for kind in HOOK_TYPES}
        self._lock = Lock()

    def register(self, hook_type: str, name: str, callback: HookCallback, order: int = 100) -> None:
        if hook_type not in HOOK_TYPES:
            raise ValueError(f"unsupported hook_type: {hook_type}")
        spec = HookSpec(hook_type=hook_type, name=name, order=order, callback=callback)
        with self._lock:
            # Use .get() so new hook types added to HOOK_TYPES after __init__
            # are handled gracefully without requiring registry re-creation.
            hooks = list(self._hooks.get(hook_type, []))
            hooks = [hook for hook in hooks if hook.name != name]
            hooks.append(spec)
            hooks.sort(key=lambda hook: (hook.order, hook.name))
            self._hooks[hook_type] = hooks

    def run(self, hook_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        if hook_type not in HOOK_TYPES:
            raise ValueError(f"unsupported hook_type: {hook_type}")
        hooks = list(self._hooks.get(hook_type) or [])
        current = dict(context)
        for hook in hooks:
            maybe_update = hook.callback(dict(current))
            if isinstance(maybe_update, dict):
                current.update(maybe_update)
        return current

    def list_hooks(self, hook_type: str) -> List[str]:
        if hook_type not in HOOK_TYPES:
            raise ValueError(f"unsupported hook_type: {hook_type}")
        return [hook.name for hook in self._hooks.get(hook_type) or []]


def _hook_log_path() -> Path:
    path = Path(os.getenv("K1_HOOK_AUDIT_PATH", "artifacts/hooks/audit.jsonl")).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _audit_callback(context: Dict[str, Any]) -> Dict[str, Any]:
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hook_type": context.get("hook_type"),
        "tool_id": context.get("tool_id"),
        "run_id": context.get("run_id"),
        "status": context.get("status"),
    }
    with _hook_log_path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    return {}


def _agent_audit_callback(context: Dict[str, Any]) -> Dict[str, Any]:
    """Audit callback for agent lifecycle hooks. Logs agent_id instead of tool_id."""
    row = {
        "timestamp":    datetime.now(timezone.utc).isoformat(),
        "hook_type":    context.get("hook_type"),
        "agent_id":     context.get("agent_id"),
        "framework":    context.get("framework"),
        "workflow_id":  context.get("workflow_id"),
        "program_id":   context.get("program_id"),
        "user_id":      context.get("user_id"),
        "risk_profile": context.get("risk_profile"),
        "status":       context.get("status"),
    }
    with _hook_log_path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row) + "\n")
    return {}


def _safety_gate_enforce_hook(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    AUDIT ORDERING FIX (Phase 3.5): Enforcement hook runs at order=100, AFTER
    the audit at order=50 has captured the governance outcome.

    If the governance hook (order=5, registered in main.py) set _governance_blocked=True,
    this hook raises PraisonGovernanceError, which propagates to tool_runner.
    The audit at order=50 has already written the correct status="blocked".

    Hook execution order for safety_gate:
      order=5   governance hook    (sets _governance_blocked and status)
      order=50  audit hook         (writes status to audit log — captures true outcome)
      order=100 enforce hook       (raises PraisonGovernanceError if blocked)
    """
    if context.get("_governance_blocked"):
        # Import here to avoid circular import at module level
        from apps.backend.src.core.praison_governor import PraisonGovernanceError
        raise PraisonGovernanceError(
            reason=context.get("_governance_reason", "Governance blocked execution"),
            tool_id=context.get("tool_id", ""),
            code="GOVERNANCE_BLOCK",
        )
    return {}


_REGISTRY = HookRegistry()
# Tool execution hooks
# pre_run / post_run / approval_gate / retry_gate: audit at order=10 (no governance involvement)
_REGISTRY.register("pre_run",       "audit_pre_run",       _audit_callback,       order=10)
_REGISTRY.register("post_run",      "audit_post_run",      _audit_callback,       order=10)
_REGISTRY.register("approval_gate", "audit_approval_gate", _audit_callback,       order=10)
_REGISTRY.register("retry_gate",    "audit_retry_gate",    _audit_callback,       order=10)
# safety_gate: governance(5) → audit(50) → enforce(100)
# The governance hook is registered by main.py at order=5.
# Audit at order=50 captures the FINAL governance outcome (status set by governance hook).
# Enforce at order=100 raises PraisonGovernanceError if governance blocked.
_REGISTRY.register("safety_gate", "audit_safety_gate",   _audit_callback,            order=50)
_REGISTRY.register("safety_gate", "enforce_safety_gate", _safety_gate_enforce_hook,  order=100)
# Agent lifecycle hooks (audit at order=10, governance hooks registered by main.py at order=50)
_REGISTRY.register("agent_spawn",        "audit_agent_spawn",        _agent_audit_callback, order=10)
_REGISTRY.register("agent_handoff",      "audit_agent_handoff",      _agent_audit_callback, order=10)
_REGISTRY.register("agent_memory_write", "audit_agent_memory_write", _agent_audit_callback, order=10)
_REGISTRY.register("agent_external_call","audit_agent_external_call",_agent_audit_callback, order=10)


def get_hook_registry() -> HookRegistry:
    return _REGISTRY
