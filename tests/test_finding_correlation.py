from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest

from apps.backend.src.core.evidence_service import EvidenceService
from apps.backend.src.core.finding_correlation_service import FindingCorrelationService
from apps.backend.src.core.submission_draft_service import (
    DRAFT_STATUS_READY_FOR_REVIEW,
    SubmissionDraftService,
)
from apps.backend.src.models.campaign import Artifact, AuditEvent, CampaignRun, Observation, SubmissionDraft
from apps.backend.src.models.enums import ArtifactTypeEnum, ObservationTypeEnum, SeverityEnum
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
async def test_validation_observation_creates_finding(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    service = FindingCorrelationService(db)  # type: ignore[arg-type]
    campaign = CampaignRun(
        id=uuid4(),
        program_id=uuid4(),
        initiated_by="tester",
        declared_goal="correlate",
    )
    observation = Observation(
        id=uuid4(),
        campaign_id=campaign.id,
        branch_id=uuid4(),
        phase_job_id=uuid4(),
        tool_execution_id=uuid4(),
        category="VALIDATION",
        title="validated auth bypass path",
        summary="validated control bypass behavior",
        observation_type=ObservationTypeEnum.VALIDATION,
        payload_json={"target": "api.example.com"},
    )

    monkeypatch.setattr(service, "_campaign", AsyncMock(return_value=campaign))
    monkeypatch.setattr(service, "_program_name", AsyncMock(return_value="Example Program"))
    monkeypatch.setattr(service, "_execution", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_phase_job", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_target_identifier", AsyncMock(return_value="api.example.com"))
    monkeypatch.setattr(service, "_matching_finding", AsyncMock(return_value=(None, False)))
    monkeypatch.setattr(service, "_collect_related_artifacts", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        service.drafts,
        "upsert_draft_for_finding",
        AsyncMock(
            return_value=SubmissionDraft(
                id=uuid4(),
                campaign_id=campaign.id,
                finding_id=uuid4(),
                status="NEEDS_REVIEW",
            )
        ),
    )

    outcome = await service.process_observation(observation, actor="test.correlation")
    assert outcome.action == "CREATED"
    assert observation.finding_id is not None
    findings = [obj for obj in db.added if isinstance(obj, Finding)]
    assert len(findings) == 1
    assert findings[0].severity == SeverityEnum.LOW
    audit_events = [obj for obj in db.added if isinstance(obj, AuditEvent)]
    assert any(event.event_type == "finding.correlation.created" for event in audit_events)


@pytest.mark.asyncio
async def test_discovery_observation_does_not_create_finding(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    service = FindingCorrelationService(db)  # type: ignore[arg-type]
    campaign = CampaignRun(
        id=uuid4(),
        program_id=uuid4(),
        initiated_by="tester",
        declared_goal="correlate",
    )
    observation = Observation(
        id=uuid4(),
        campaign_id=campaign.id,
        category="DISCOVERY",
        observation_type=ObservationTypeEnum.DISCOVERY,
    )
    monkeypatch.setattr(service, "_campaign", AsyncMock(return_value=campaign))

    outcome = await service.process_observation(observation, actor="test.correlation")
    assert outcome.action == "CONTEXT_ONLY"
    assert not any(isinstance(obj, Finding) for obj in db.added)


@pytest.mark.asyncio
async def test_duplicate_observation_attaches_existing_finding(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    service = FindingCorrelationService(db)  # type: ignore[arg-type]
    campaign = CampaignRun(
        id=uuid4(),
        program_id=uuid4(),
        initiated_by="tester",
        declared_goal="correlate",
    )
    existing = Finding(
        id=uuid4(),
        program="Example Program",
        asset="api.example.com",
        title="validated auth bypass path",
        description="existing finding",
        severity=SeverityEnum.LOW,
        scope_json={
            "campaign_id": str(campaign.id),
            "normalized_title": "validated auth bypass path",
            "normalized_category": "VALIDATION",
            "target_identifier": "api.example.com",
        },
    )
    observation = Observation(
        id=uuid4(),
        campaign_id=campaign.id,
        category="VALIDATION",
        title="validated auth bypass path",
        observation_type=ObservationTypeEnum.VALIDATION,
        payload_json={"target": "api.example.com"},
    )

    monkeypatch.setattr(service, "_campaign", AsyncMock(return_value=campaign))
    monkeypatch.setattr(service, "_program_name", AsyncMock(return_value="Example Program"))
    monkeypatch.setattr(service, "_execution", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_phase_job", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_target_identifier", AsyncMock(return_value="api.example.com"))
    monkeypatch.setattr(service, "_matching_finding", AsyncMock(return_value=(existing, True)))
    monkeypatch.setattr(service, "_collect_related_artifacts", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        service.drafts,
        "upsert_draft_for_finding",
        AsyncMock(
            return_value=SubmissionDraft(
                id=uuid4(),
                campaign_id=campaign.id,
                finding_id=existing.id,
                status="SUPPRESSED_DUPLICATE",
            )
        ),
    )

    outcome = await service.process_observation(observation, actor="test.correlation")
    assert outcome.action == "ATTACHED"
    assert outcome.duplicate is True
    assert observation.finding_id == existing.id
    assert not any(isinstance(obj, Finding) for obj in db.added)


@pytest.mark.asyncio
async def test_artifact_converted_to_evidence_and_audited(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    service = EvidenceService(db)  # type: ignore[arg-type]
    artifact = Artifact(
        id=uuid4(),
        campaign_id=uuid4(),
        branch_id=uuid4(),
        phase_job_id=uuid4(),
        tool_execution_id=uuid4(),
        artifact_type=ArtifactTypeEnum.RAW_OUTPUT,
        uri="file://artifacts/run/output.json",
        content_hash="a" * 64,
        mime_type="application/json",
        details_json={},
    )
    finding_id = uuid4()

    monkeypatch.setattr(service, "_existing_evidence", AsyncMock(return_value=None))
    evidence, created = await service.attach_artifact_to_finding(
        finding_id=finding_id,
        artifact=artifact,
        actor="test.evidence",
    )
    assert created is True
    assert evidence.finding_id == finding_id
    assert artifact.finding_id == finding_id
    assert evidence.meta["synthetic"] is False
    audit_events = [obj for obj in db.added if isinstance(obj, AuditEvent)]
    assert any(event.event_type == "finding.evidence.linked" for event in audit_events)


@pytest.mark.asyncio
async def test_placeholder_artifact_marked_synthetic(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    service = EvidenceService(db)  # type: ignore[arg-type]
    artifact = Artifact(
        id=uuid4(),
        campaign_id=uuid4(),
        artifact_type=ArtifactTypeEnum.LOG,
        uri="inline://tool-execution/1/raw-result",
        content_hash=None,
        details_json={"placeholder": True},
    )

    monkeypatch.setattr(service, "_existing_evidence", AsyncMock(return_value=None))
    evidence, _created = await service.attach_artifact_to_finding(
        finding_id=uuid4(),
        artifact=artifact,
        actor="test.evidence",
    )
    assert evidence.meta["synthetic"] is True


@pytest.mark.asyncio
async def test_submission_draft_ready_for_review_when_evidence_and_validation(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    service = SubmissionDraftService(db)  # type: ignore[arg-type]
    finding = Finding(
        id=uuid4(),
        program="Example Program",
        asset="api.example.com",
        title="validated auth bypass path",
        description="desc",
        severity=SeverityEnum.LOW,
        scope_json={},
    )
    evidence = Evidence(
        id=uuid4(),
        finding_id=finding.id,
        kind="raw_output",
        uri="file://artifact.json",
        sha256=b"x" * 32,
        meta={},
    )

    monkeypatch.setattr(service.evidence, "list_finding_evidence", AsyncMock(return_value=[evidence]))
    monkeypatch.setattr(service, "_has_validation_observation", AsyncMock(return_value=True))
    monkeypatch.setattr(service, "_latest_draft", AsyncMock(return_value=None))

    draft = await service.upsert_draft_for_finding(
        finding=finding,
        campaign_id=uuid4(),
        branch_id=None,
        intention_id=None,
        actor="test.drafts",
    )
    assert draft.status == DRAFT_STATUS_READY_FOR_REVIEW


@pytest.mark.asyncio
async def test_processing_same_observation_is_idempotent(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    service = FindingCorrelationService(db)  # type: ignore[arg-type]
    campaign = CampaignRun(
        id=uuid4(),
        program_id=uuid4(),
        initiated_by="tester",
        declared_goal="correlate",
    )
    existing = Finding(
        id=uuid4(),
        program="Example Program",
        asset="api.example.com",
        title="validated auth bypass path",
        description="existing",
        severity=SeverityEnum.LOW,
        scope_json={},
    )
    observation = Observation(
        id=uuid4(),
        campaign_id=campaign.id,
        finding_id=existing.id,
        category="VALIDATION",
        title="validated auth bypass path",
        observation_type=ObservationTypeEnum.VALIDATION,
    )

    monkeypatch.setattr(service, "_campaign", AsyncMock(return_value=campaign))
    monkeypatch.setattr(service, "_program_name", AsyncMock(return_value="Example Program"))
    monkeypatch.setattr(service, "_execution", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_phase_job", AsyncMock(return_value=None))
    monkeypatch.setattr(service, "_target_identifier", AsyncMock(return_value="api.example.com"))
    monkeypatch.setattr(service, "_finding_by_id", AsyncMock(return_value=existing))
    monkeypatch.setattr(service, "_collect_related_artifacts", AsyncMock(return_value=[]))
    monkeypatch.setattr(
        service.drafts,
        "upsert_draft_for_finding",
        AsyncMock(
            return_value=SubmissionDraft(
                id=uuid4(),
                campaign_id=campaign.id,
                finding_id=existing.id,
                status="NEEDS_REVIEW",
            )
        ),
    )

    first = await service.process_observation(observation, actor="test.correlation")
    second = await service.process_observation(observation, actor="test.correlation")
    assert first.action == "ALREADY_LINKED"
    assert second.action == "ALREADY_LINKED"
    assert not any(isinstance(obj, Finding) for obj in db.added)
