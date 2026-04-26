"""Routing engine selects providers/models based on policy and capabilities."""

from typing import Dict, Any
from .capability_registry import find_models


def route(task: str, privacy_tier: int = 1, cost_tier: int | None = None) -> Dict[str, Any]:
    candidates = find_models(task, min_privacy=privacy_tier)
    if cost_tier is not None:
        candidates = [c for c in candidates if c.get("capabilities", {}).get("cost_tier", 99) <= cost_tier]
    if not candidates:
        return {"status": "error", "reason": "no_route"}
    return {"status": "ok", "primary": candidates[0], "fallbacks": candidates[1:]}
