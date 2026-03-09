from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from apps.backend.src.core.finding_review_service import FindingReviewService
from apps.backend.src.core.review_queue_service import ReviewQueueService
from apps.backend.src.core.submission_package_service import SubmissionPackageService
from apps.backend.src.models.campaign import Artifact, AuditEvent, Observation, SubmissionDraft
from apps.backend.src.models.enums import FindingStatusEnum, ObservationTypeEnum, SeverityEnum
from apps.backend.src.models.hil import Evidence, Finding


class FakeDB:
    def __init__(self):
        self.added: list[object] = []

    def add(self, obj: object) -> None:
        now = datetime.now(timezone.utc)
        if hasattr(obj, "id") and getattr(obj, "id", None) is None:
            setattr(obj, "id", uuid4())
        if hasattr(obj, "created_at") and getattr(obj, "created_at", None) is None:
            setattr(obj, "created_at", now)
        if hasattr(obj, "updated_at") and getattr(obj, "updated_at", None) is None:
            setattr(obj, "updated_at", now)
        self.added.append(obj)

    async def flush(self) -> None:
        return None

    async def execute(self, *_args, **_kwargs):
        raise AssertionError("Unexpected SQL execution in FakeDB test path")


@pytest.mark.asyncio
async def test_review_queue_retrieval(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    service = ReviewQueueService(db)  # type: ignore[arg-type]
    campaign_id = uuid4()
    finding = Finding(
        id=uuid4(),
        program="Example Program",
        asset="api.example.com",
        title="validated auth bypass path",
        description="desc",
        severity=SeverityEnum.LOW,
        status=FindingStatusEnum.IN_REVIEW,
    )
    draft = SubmissionDraft(
        id=uuid4(),
        campaign_id=campaign_id,
        finding_id=finding.id,
        status="READY_FOR_REVIEW",
        details_json={},
    )
    monkeypatch.setattr(service, "_draft_candidates", AsyncMock(return_value=[draft]))
    monkeypatch.setattr(service, "_finding", AsyncMock(return_value=finding))
    monkeypatch.setattr(service, "_evidence_count", AsyncMock(return_value=2))
    monkeypatch.setattr(
        service,
        "_observation_summary",
        AsyncMock(return_value={"count": 1, "items": [{"category": "VALIDATION"}]}),
    )

    queue = await service.list_review_queue(campaign_id=campaign_id, limit=100)
    assert len(queue) == 1
    assert queue[0]["finding_id"] == str(finding.id)
    assert queue[0]["evidence_count"] == 2
    assert queue[0]["readiness_status"] == "READY_FOR_REVIEW"


@pytest.mark.asyncio
async def test_finding_approval_workflow_generates_audit(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    service = FindingReviewService(db)  # type: ignore[arg-type]
    campaign_id = uuid4()
    finding = Finding(
        id=uuid4(),
        program="Example Program",
        asset="api.example.com",
        title="validated auth bypass path",
        description="desc",
        severity=SeverityEnum.LOW,
        status=FindingStatusEnum.NEW,
        scope_json={"campaign_id": str(campaign_id)},
    )
    draft = SubmissionDraft(
        id=uuid4(),
        campaign_id=campaign_id,
        finding_id=finding.id,
        status="NEEDS_REVIEW",
        details_json={},
    )
    monkeypatch.setattr(service, "_get_finding", AsyncMock(return_value=finding))
    monkeypatch.setattr(service, "_latest_draft", AsyncMock(return_value=draft))

    result = await service.review_finding(
        finding_id=finding.id,
        action="APPROVE",
        reviewer_id="reviewer@example.com",
        review_notes="Validated exploit path and impact.",
    )

    assert result.finding_status == FindingStatusEnum.HIL_APPROVED
    assert result.draft_status == "READY_FOR_SUBMISSION"
    audit_events = [obj for obj in db.added if isinstance(obj, AuditEvent)]
    assert any(event.event_type == "finding.review.started" for event in audit_events)
    assert any(event.event_type == "finding.review.action" for event in audit_events)


@pytest.mark.asyncio
async def test_rejection_workflow_updates_draft_state(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    service = FindingReviewService(db)  # type: ignore[arg-type]
    campaign_id = uuid4()
    finding = Finding(
        id=uuid4(),
        program="Example Program",
        asset="api.example.com",
        title="invalid signal",
        description="desc",
        severity=SeverityEnum.INFO,
        status=FindingStatusEnum.IN_REVIEW,
        scope_json={"campaign_id": str(campaign_id)},
    )
    draft = SubmissionDraft(
        id=uuid4(),
        campaign_id=campaign_id,
        finding_id=finding.id,
        status="NEEDS_REVIEW",
        details_json={},
    )
    monkeypatch.setattr(service, "_get_finding", AsyncMock(return_value=finding))
    monkeypatch.setattr(service, "_latest_draft", AsyncMock(return_value=draft))

    result = await service.review_finding(
        finding_id=finding.id,
        action="REJECT",
        reviewer_id="reviewer@example.com",
        review_notes="Could not reproduce.",
    )

    assert result.finding_status == FindingStatusEnum.REJECTED
    assert result.draft_status == "CLOSED"


@pytest.mark.asyncio
async def test_duplicate_suppression_updates_status(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    service = FindingReviewService(db)  # type: ignore[arg-type]
    campaign_id = uuid4()
    finding = Finding(
        id=uuid4(),
        program="Example Program",
        asset="api.example.com",
        title="duplicate issue",
        description="desc",
        severity=SeverityEnum.INFO,
        status=FindingStatusEnum.IN_REVIEW,
        scope_json={"campaign_id": str(campaign_id)},
    )
    draft = SubmissionDraft(
        id=uuid4(),
        campaign_id=campaign_id,
        finding_id=finding.id,
        status="NEEDS_REVIEW",
        details_json={},
    )
    monkeypatch.setattr(service, "_get_finding", AsyncMock(return_value=finding))
    monkeypatch.setattr(service, "_latest_draft", AsyncMock(return_value=draft))

    result = await service.review_finding(
        finding_id=finding.id,
        action="DUPLICATE",
        reviewer_id="reviewer@example.com",
        review_notes="Matches known report",
        duplicate_of_finding_id=uuid4(),
    )
    assert result.finding_status == FindingStatusEnum.DUPLICATE
    assert result.draft_status == "SUPPRESSED_DUPLICATE"


@pytest.mark.asyncio
async def test_submission_package_generation(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    service = SubmissionPackageService(db)  # type: ignore[arg-type]
    campaign_id = uuid4()
    finding = Finding(
        id=uuid4(),
        program="Example Program",
        asset="api.example.com",
        title="approved finding",
        description="desc",
        severity=SeverityEnum.LOW,
        status=FindingStatusEnum.HIL_APPROVED,
        scope_json={"campaign_id": str(campaign_id), "branch_id": str(uuid4())},
    )
    draft = SubmissionDraft(
        id=uuid4(),
        campaign_id=campaign_id,
        finding_id=finding.id,
        status="READY_FOR_REVIEW",
        details_json={},
    )
    evidence = Evidence(
        id=uuid4(),
        finding_id=finding.id,
        kind="raw_output",
        uri="file://artifact.json",
        sha256=b"x" * 32,
        meta={"synthetic": False},
    )
    observation = Observation(
        id=uuid4(),
        campaign_id=campaign_id,
        finding_id=finding.id,
        category="VALIDATION",
        summary="validated reproduction path",
        observation_type=ObservationTypeEnum.VALIDATION,
    )
    artifact = Artifact(
        id=uuid4(),
        campaign_id=campaign_id,
        finding_id=finding.id,
        uri="file://artifact.json",
        artifact_type=None,
    )

    monkeypatch.setattr(service, "_get_finding", AsyncMock(return_value=finding))
    monkeypatch.setattr(service, "_get_or_create_draft", AsyncMock(return_value=draft))
    monkeypatch.setattr(service, "_evidence_rows", AsyncMock(return_value=[evidence]))
    monkeypatch.setattr(service, "_observation_rows", AsyncMock(return_value=[observation]))
    monkeypatch.setattr(service, "_artifact_rows", AsyncMock(return_value=[artifact]))

    result = await service.prepare_submission_package(
        finding_id=finding.id,
        prepared_by="reviewer@example.com",
    )

    assert result.draft_status == "READY_FOR_SUBMISSION"
    assert "finding" in result.package_json
    assert "evidence" in result.package_json
    assert draft.status == "READY_FOR_SUBMISSION"
    audit_events = [obj for obj in db.added if isinstance(obj, AuditEvent)]
    assert any(event.event_type == "submission_package.prepared" for event in audit_events)
