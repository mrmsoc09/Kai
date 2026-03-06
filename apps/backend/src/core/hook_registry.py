from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Dict, List
import json
import os


HookCallback = Callable[[Dict[str, Any]], Dict[str, Any] | None]
HOOK_TYPES = {"pre_run", "post_run", "approval_gate", "retry_gate", "safety_gate"}


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
            hooks = list(self._hooks[hook_type])
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


_REGISTRY = HookRegistry()
_REGISTRY.register("pre_run", "audit_pre_run", _audit_callback, order=10)
_REGISTRY.register("post_run", "audit_post_run", _audit_callback, order=10)
_REGISTRY.register("approval_gate", "audit_approval_gate", _audit_callback, order=10)
_REGISTRY.register("retry_gate", "audit_retry_gate", _audit_callback, order=10)
_REGISTRY.register("safety_gate", "audit_safety_gate", _audit_callback, order=10)


def get_hook_registry() -> HookRegistry:
    return _REGISTRY
