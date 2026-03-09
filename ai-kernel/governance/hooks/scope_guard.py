"""Scope guard hook enforces scope and authorization policies."""

from pathlib import Path
from typing import Dict, Any
from .lib.io_contracts import HookResult, ToolCall
from .lib.policy_loader import load_policy
from .lib.common import logger

POLICY_ROOT = Path(__file__).resolve().parents[1] / "policies"


def run(tool_call: Dict[str, Any]) -> HookResult:
    policy = load_policy("scope_rules", POLICY_ROOT)
    call = ToolCall(
        tool_id=tool_call.get("tool_id", ""),
        adapter_id=tool_call.get("adapter_id", ""),
        args=tool_call.get("args") or {},
    )
    scope_valid = bool(tool_call.get("scope_validated"))
    auth_valid = bool(tool_call.get("authorized"))

    if not scope_valid:
        return HookResult(ok=False, reason="scope validation missing", warnings=["policy: scope-001"])
    if not auth_valid:
        return HookResult(ok=False, reason="authorization check missing", warnings=["policy: scope-002"])

    logger.debug("scope_guard pass tool=%s adapter=%s", call.tool_id, call.adapter_id)
    return HookResult(ok=True, data={"tool_call": call})
