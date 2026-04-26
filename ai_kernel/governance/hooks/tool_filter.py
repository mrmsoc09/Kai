"""Tool filter hook ensures adapter-bound execution and forbidden flags."""

from pathlib import Path
from typing import Dict, Any
from .lib.io_contracts import HookResult
from .lib.policy_loader import load_policy
from .lib.common import logger

POLICY_ROOT = Path(__file__).resolve().parents[1] / "policies"


def run(tool_call: Dict[str, Any]) -> HookResult:
    policy = load_policy("tool_policy", POLICY_ROOT)
    adapter_id = tool_call.get("adapter_id")
    if not adapter_id:
        return HookResult(ok=False, reason="adapter_id required")

    forbidden = []
    args = tool_call.get("args") or {}
    for rule in policy.get("rules", []):
        if rule["id"] == "tool-004":
            # example: check flag presence
            for bad in rule.get("forbidden_flags", []):
                if bad in args.get("flags", []):
                    forbidden.append(bad)
    if forbidden:
        return HookResult(ok=False, reason=f"forbidden flags: {forbidden}")

    logger.debug("tool_filter pass adapter=%s", adapter_id)
    return HookResult(ok=True, data={"adapter_id": adapter_id})
