from __future__ import annotations

from apps.backend.src.core.confidence_policy import evaluate_confidence_policy


def test_confidence_policy_stop():
    d = evaluate_confidence_policy(0.1, security_sensitive=True, has_local_fallback=True)
    assert d.action == "stop"


def test_confidence_policy_escalate():
    d = evaluate_confidence_policy(0.5, security_sensitive=False, has_local_fallback=False)
    assert d.action == "escalate_hil"


def test_confidence_policy_fallback_local():
    d = evaluate_confidence_policy(0.6, security_sensitive=True, has_local_fallback=True)
    assert d.action == "fallback_local"


def test_confidence_policy_allow():
    d = evaluate_confidence_policy(0.9, security_sensitive=True, has_local_fallback=True)
    assert d.action == "allow"
