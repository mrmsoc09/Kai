from __future__ import annotations

import os

from pydantic import BaseModel, Field


def _env_threshold() -> float:
    raw = os.getenv("K1_CONFIDENCE_VALIDATION_THRESHOLD")
    if raw is None:
        return 0.65
    try:
        value = float(raw)
    except ValueError:
        return 0.65
    return max(0.0, min(1.0, value))


class TriggerDecision(BaseModel):
    requires_validation: bool
    reason: str
    threshold: float = Field(ge=0.0, le=1.0)


def decide_validation_trigger(
    confidence_score: float,
    *,
    state_uncertain: bool = False,
    threshold: float | None = None,
) -> TriggerDecision:
    threshold_value = _env_threshold() if threshold is None else max(0.0, min(1.0, threshold))
    below_threshold = confidence_score < threshold_value
    requires_validation = below_threshold or bool(state_uncertain)

    if below_threshold and state_uncertain:
        reason = "confidence_below_threshold_and_state_uncertain"
    elif below_threshold:
        reason = "confidence_below_threshold"
    elif state_uncertain:
        reason = "state_uncertain"
    else:
        reason = "confidence_sufficient"

    return TriggerDecision(
        requires_validation=requires_validation,
        reason=reason,
        threshold=threshold_value,
    )

