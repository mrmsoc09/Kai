from __future__ import annotations

from apps.backend.src.core.finalize import finalize_report


def _payload(risk_level: str, status: str = "duplicate_suspected", **extra):
    base = {
        "mitigation_plan": "patch",
        "has_recording": True,
        "duplicate_check": {"status": status, "risk_level": risk_level},
    }
    base.update(extra)
    return base


def test_duplicate_high_risk_requires_override():
    result = finalize_report("run-1", "generic", _payload("high"))
    assert result["ok"] is False
    assert result["reason"] == "duplicate_high_risk_override_required"


def test_duplicate_high_risk_override_requires_reason():
    result = finalize_report(
        "run-1",
        "generic",
        _payload("high", duplicate_override=True, duplicate_override_reason=""),
    )
    assert result["ok"] is False
    assert result["reason"] == "duplicate_override_reason_required"


def test_duplicate_high_risk_with_reason_allows_finalize():
    result = finalize_report(
        "run-1",
        "generic",
        _payload("high", duplicate_override=True, duplicate_override_reason="new reproduction evidence"),
    )
    assert result["ok"] is True
