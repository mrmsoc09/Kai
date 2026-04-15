from __future__ import annotations

import pytest

from apps.backend.src.services.false_positive_detector import FalsePositiveDetector
from apps.backend.src.services.submission_service import ensure_finding_approved_for_submission


class _FakeFinding:
    def __init__(self, validation_status: str | None):
        self.id = "00000000-0000-0000-0000-000000000001"
        self.validation_status = validation_status


class _FakeDB:
    def __init__(self, finding):
        self._finding = finding

    async def scalar(self, _stmt):
        return self._finding


@pytest.mark.asyncio
async def test_false_positive_detector_flags_high_risk_false_positive():
    detector = FalsePositiveDetector()
    score, reason = await detector.analyze_finding_for_false_positive(
        "finding-1",
        {
            "vulnerability_type": "XSS",
            "endpoint": "",
            "description": "Input appears sanitized and blocked by WAF",
            "proof_of_concept": "",
            "payload_used": "",
        },
    )
    assert score >= 0.60
    assert reason == "not_reproducible"


@pytest.mark.asyncio
async def test_false_positive_detector_keeps_low_score_for_strong_evidence():
    detector = FalsePositiveDetector()
    score, reason = await detector.analyze_finding_for_false_positive(
        "finding-2",
        {
            "vulnerability_type": "SQL Injection",
            "endpoint": "/api/users",
            "description": "Time-based SQLi confirmed with repeatable payload",
            "proof_of_concept": "1) send payload 2) observe 5s delay",
            "payload_used": "' OR pg_sleep(5)--",
        },
    )
    assert score < 0.60
    assert reason is None


@pytest.mark.asyncio
async def test_submission_guard_requires_approval():
    db = _FakeDB(_FakeFinding(validation_status="pending_analyst_review"))
    finding, error = await ensure_finding_approved_for_submission(
        db, "00000000-0000-0000-0000-000000000001"
    )
    assert finding is not None
    assert error is not None
    assert error["error"] == "Finding not approved for submission"


@pytest.mark.asyncio
async def test_submission_guard_rejects_excluded():
    db = _FakeDB(_FakeFinding(validation_status="excluded"))
    finding, error = await ensure_finding_approved_for_submission(
        db, "00000000-0000-0000-0000-000000000001"
    )
    assert finding is not None
    assert error is not None
    assert error["error"] == "Finding is excluded"

