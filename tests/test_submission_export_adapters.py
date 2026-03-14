from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from apps.backend.src.core.submission_export_service import (
    READY_DRAFT_STATUS,
    SubmissionExportService,
)
from apps.backend.src.models.campaign import Artifact, AuditEvent, Observation, SubmissionDraft
from apps.backend.src.models.enums import (
    ArtifactTypeEnum,
    FindingStatusEnum,
    ObservationTypeEnum,
    SeverityEnum,
)
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


def _package_json(campaign_id: str, branch_id: str) -> dict:
    return {
        "finding": {
            "title": "Validated auth bypass",
            "severity": "HIGH",
            "asset": "api.example.com",
            "description": "Validated authorization bypass with deterministic reproduction",
        },
        "campaign_context": {
            "campaign_id": campaign_id,
            "branch_id": branch_id,
        },
        "reproduction_notes": [
            "Authenticate as low-privileged user and request /admin endpoint with crafted header.",
            "Observe unauthorized response body containing restricted data.",
        ],
        "observations": [
            {
                "category": "VALIDATION",
                "summary": "Authorization bypass confirmed on API v2 endpoint.",
            }
        ],
    }


def _build_context(
    *,
    finding_status: FindingStatusEnum = FindingStatusEnum.HIL_APPROVED,
    include_cwe: bool = True,
):
    campaign_id = uuid4()
    branch_id = uuid4()
    scope_json = {"campaign_id": str(campaign_id), "branch_id": str(branch_id)}
    if include_cwe:
        scope_json["cwe"] = "CWE-285"
    finding = Finding(
        id=uuid4(),
        program="Example Program",
        asset="api.example.com",
        title="Validated auth bypass",
        description="Validated authorization bypass with deterministic reproduction",
        severity=SeverityEnum.HIGH,
        status=finding_status,
        scope_json=scope_json,
    )
    draft = SubmissionDraft(
        id=uuid4(),
        campaign_id=campaign_id,
        branch_id=branch_id,
        finding_id=finding.id,
        status=READY_DRAFT_STATUS,
        details_json={"package_json": _package_json(str(campaign_id), str(branch_id))},
    )
    evidence = Evidence(
        id=uuid4(),
        finding_id=finding.id,
        kind="raw_output",
        uri="file://artifact/output.json",
        sha256=b"x" * 32,
        meta={"synthetic": False},
    )
    artifact = Artifact(
        id=uuid4(),
        campaign_id=campaign_id,
        branch_id=branch_id,
        finding_id=finding.id,
        artifact_type=ArtifactTypeEnum.RAW_OUTPUT,
        uri="file://artifact/output.json",
        content_hash="a" * 64,
        mime_type="application/json",
        details_json={},
    )
    observation = Observation(
        id=uuid4(),
        campaign_id=campaign_id,
        branch_id=branch_id,
        finding_id=finding.id,
        observation_type=ObservationTypeEnum.VALIDATION,
        category="VALIDATION",
        title="Validated auth bypass",
        summary="Authorization bypass confirmed on API v2 endpoint.",
    )
    return finding, draft, evidence, artifact, observation


def _stub_service_context(
    monkeypatch: pytest.MonkeyPatch,
    service: SubmissionExportService,
    *,
    finding: Finding,
    draft: SubmissionDraft,
    evidence: list[Evidence],
    artifacts: list[Artifact],
    observations: list[Observation],
) -> None:
    monkeypatch.setattr(
        service,
        "_resolve_finding_draft",
        AsyncMock(return_value=(finding, draft)),
    )
    monkeypatch.setattr(service, "_finding_evidence", AsyncMock(return_value=evidence))
    monkeypatch.setattr(service, "_finding_artifacts", AsyncMock(return_value=artifacts))
    monkeypatch.setattr(service, "_finding_observations", AsyncMock(return_value=observations))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("provider", "expected_key"),
    [
        ("hackerone", "affected_assets"),
        ("bugcrowd", "steps_to_reproduce"),
        ("intigriti", "supporting_materials"),
    ],
)
async def test_provider_preview_generation_for_approved_finding(
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    expected_key: str,
):
    db = FakeDB()
    service = SubmissionExportService(db)  # type: ignore[arg-type]
    finding, draft, evidence, artifact, observation = _build_context()
    _stub_service_context(
        monkeypatch,
        service,
        finding=finding,
        draft=draft,
        evidence=[evidence],
        artifacts=[artifact],
        observations=[observation],
    )

    result = await service.preview_payload(
        provider=provider,
        finding_id=finding.id,
        actor="operator.preview@test",
    )

    assert result.provider == provider
    assert result.ready is True
    assert expected_key in result.payload
    audit_events = [obj for obj in db.added if isinstance(obj, AuditEvent)]
    assert any(event.event_type == "submission_export.previewed" for event in audit_events)


@pytest.mark.asyncio
async def test_validation_failure_reports_missing_fields(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    service = SubmissionExportService(db)  # type: ignore[arg-type]
    finding, draft, evidence, artifact, observation = _build_context()
    draft.status = "NEEDS_REVIEW"
    draft.details_json = {"package_json": {}}

    _stub_service_context(
        monkeypatch,
        service,
        finding=finding,
        draft=draft,
        evidence=[],
        artifacts=[artifact],
        observations=[observation],
    )

    result = await service.preview_payload(
        provider="bugcrowd",
        finding_id=finding.id,
        actor="operator.preview@test",
    )

    assert result.ready is False
    assert "submission_draft.status:READY_FOR_SUBMISSION" in result.missing_fields
    assert "submission_draft.details_json.package_json" in result.missing_fields
    assert "finding.evidence" in result.missing_fields


@pytest.mark.asyncio
async def test_provider_required_field_validation_failure(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    service = SubmissionExportService(db)  # type: ignore[arg-type]
    finding, draft, evidence, artifact, observation = _build_context(include_cwe=False)
    _stub_service_context(
        monkeypatch,
        service,
        finding=finding,
        draft=draft,
        evidence=[evidence],
        artifacts=[artifact],
        observations=[observation],
    )

    result = await service.preview_payload(
        provider="bugcrowd",
        finding_id=finding.id,
        actor="operator.preview@test",
    )

    assert result.ready is False
    assert "vulnerability_type" in result.missing_fields


@pytest.mark.asyncio
async def test_export_persists_metadata_and_audit(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    service = SubmissionExportService(db)  # type: ignore[arg-type]
    finding, draft, evidence, artifact, observation = _build_context()
    _stub_service_context(
        monkeypatch,
        service,
        finding=finding,
        draft=draft,
        evidence=[evidence],
        artifacts=[artifact],
        observations=[observation],
    )

    result = await service.export_payload(
        provider="hackerone",
        finding_id=finding.id,
        actor="operator.export@test",
    )

    assert result.ready is True
    assert result.stored is True
    assert result.exported_at is not None
    provider_exports = draft.details_json["provider_exports"]["hackerone"]
    assert provider_exports[-1]["ready"] is True
    assert provider_exports[-1]["payload"]["provider"] == "hackerone"
    audit_events = [obj for obj in db.added if isinstance(obj, AuditEvent)]
    assert any(event.event_type == "submission_export.staged" for event in audit_events)


@pytest.mark.asyncio
async def test_export_refuses_non_approved_findings(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    service = SubmissionExportService(db)  # type: ignore[arg-type]
    finding, draft, evidence, artifact, observation = _build_context(
        finding_status=FindingStatusEnum.IN_REVIEW
    )
    _stub_service_context(
        monkeypatch,
        service,
        finding=finding,
        draft=draft,
        evidence=[evidence],
        artifacts=[artifact],
        observations=[observation],
    )

    result = await service.export_payload(
        provider="intigriti",
        finding_id=finding.id,
        actor="operator.export@test",
    )

    assert result.ready is False
    assert "finding.status:HIL_APPROVED" in result.missing_fields
    audit_events = [obj for obj in db.added if isinstance(obj, AuditEvent)]
    assert any(event.event_type == "submission_export.validation_failed" for event in audit_events)


@pytest.mark.asyncio
async def test_export_refuses_incomplete_draft(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    service = SubmissionExportService(db)  # type: ignore[arg-type]
    finding, draft, evidence, artifact, observation = _build_context()
    draft.status = "NEEDS_REVIEW"
    draft.details_json = {"package_json": {}}
    _stub_service_context(
        monkeypatch,
        service,
        finding=finding,
        draft=draft,
        evidence=[evidence],
        artifacts=[artifact],
        observations=[observation],
    )

    result = await service.export_payload(
        provider="hackerone",
        finding_id=finding.id,
        actor="operator.export@test",
    )

    assert result.ready is False
    assert result.stored is True
    assert "submission_draft.status:READY_FOR_SUBMISSION" in result.missing_fields
    assert "submission_draft.details_json.package_json" in result.missing_fields
    latest = draft.details_json["latest_provider_export"]
    assert latest["ready"] is False
    assert latest["provider"] == "hackerone"
    audit_events = [obj for obj in db.added if isinstance(obj, AuditEvent)]
    assert any(event.event_type == "submission_export.validation_failed" for event in audit_events)


@pytest.mark.asyncio
async def test_export_refuses_missing_evidence(monkeypatch: pytest.MonkeyPatch):
    db = FakeDB()
    service = SubmissionExportService(db)  # type: ignore[arg-type]
    finding, draft, evidence, artifact, observation = _build_context()
    _stub_service_context(
        monkeypatch,
        service,
        finding=finding,
        draft=draft,
        evidence=[],
        artifacts=[artifact],
        observations=[observation],
    )

    result = await service.export_payload(
        provider="intigriti",
        finding_id=finding.id,
        actor="operator.export@test",
    )

    assert result.ready is False
    assert result.stored is True
    assert "finding.evidence" in result.missing_fields
    provider_exports = draft.details_json["provider_exports"]["intigriti"]
    assert provider_exports[-1]["ready"] is False
    audit_events = [obj for obj in db.added if isinstance(obj, AuditEvent)]
    assert any(event.event_type == "submission_export.validation_failed" for event in audit_events)
