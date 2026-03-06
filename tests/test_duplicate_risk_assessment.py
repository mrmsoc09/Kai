from __future__ import annotations

from apps.backend.src.core import duplicates


def test_assess_duplicate_risk_none(monkeypatch):
    monkeypatch.setattr(duplicates, "check_title_duplicate", lambda title: {"status": "clear", "matches": [], "count": 0})
    monkeypatch.setattr(duplicates, "vector_duplicate", lambda title, summary=None: {"status": "clear", "matches": [], "count": 0})
    res = duplicates.assess_duplicate_risk("title", "summary")
    assert res["risk_level"] == "none"
    assert res["override_required"] is False


def test_assess_duplicate_risk_high(monkeypatch):
    monkeypatch.setattr(
        duplicates,
        "check_title_duplicate",
        lambda title: {"status": "duplicate_suspected", "matches": [{"similarity": 0.95}], "count": 1},
    )
    monkeypatch.setattr(
        duplicates,
        "vector_duplicate",
        lambda title, summary=None: {"status": "duplicate_suspected", "matches": [{"similarity": 0.90}], "count": 2},
    )
    res = duplicates.assess_duplicate_risk("title", "summary")
    assert res["risk_level"] in {"medium", "high"}
    assert res["status"] == "duplicate_suspected"
