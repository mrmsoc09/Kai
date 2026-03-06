from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class ConfidencePolicyDecision:
    action: str
    reason: str
    threshold: float


def evaluate_confidence_policy(confidence_score: float, security_sensitive: bool, has_local_fallback: bool) -> ConfidencePolicyDecision:
    """
    Deterministic confidence policy:
    - stop: confidence too low
    - escalate_hil: confidence below review threshold
    - fallback_local: security-sensitive and confidence below strict threshold
    - allow: normal execution
    """
    stop_threshold = _env_float("K1_CONFIDENCE_STOP_THRESHOLD", 0.35)
    review_threshold = _env_float("K1_CONFIDENCE_REVIEW_THRESHOLD", 0.55)
    sensitive_threshold = _env_float("K1_CONFIDENCE_SENSITIVE_THRESHOLD", 0.70)

    if confidence_score < stop_threshold:
        return ConfidencePolicyDecision("stop", "confidence_below_stop_threshold", stop_threshold)
    if confidence_score < review_threshold:
        return ConfidencePolicyDecision("escalate_hil", "confidence_below_review_threshold", review_threshold)
    if security_sensitive and confidence_score < sensitive_threshold and has_local_fallback:
        return ConfidencePolicyDecision("fallback_local", "security_sensitive_confidence_below_threshold", sensitive_threshold)
    return ConfidencePolicyDecision("allow", "confidence_within_policy", review_threshold)


def apply_policy_metadata(base: Dict[str, Any], decision: ConfidencePolicyDecision) -> Dict[str, Any]:
    out = dict(base)
    out.update(
        {
            "policy_action": decision.action,
            "policy_reason": decision.reason,
            "policy_threshold": decision.threshold,
        }
    )
    return out
