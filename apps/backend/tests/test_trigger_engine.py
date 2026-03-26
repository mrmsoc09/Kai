from __future__ import annotations

from apps.backend.src.core.trigger_engine import decide_validation_trigger


def test_trigger_requires_validation_when_below_threshold():
    decision = decide_validation_trigger(0.41, state_uncertain=False, threshold=0.6)
    assert decision.requires_validation is True
    assert decision.reason == "confidence_below_threshold"


def test_trigger_requires_validation_when_state_uncertain():
    decision = decide_validation_trigger(0.95, state_uncertain=True, threshold=0.6)
    assert decision.requires_validation is True
    assert decision.reason == "state_uncertain"


def test_trigger_not_required_when_confident_and_stable():
    decision = decide_validation_trigger(0.95, state_uncertain=False, threshold=0.6)
    assert decision.requires_validation is False
    assert decision.reason == "confidence_sufficient"

