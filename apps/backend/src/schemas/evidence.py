from __future__ import annotations

from datetime import timezone, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ArtifactMetadata(BaseModel):
    artifact_path: str
    sha256: str
    mime_type: str
    description: str


class EvidenceObject(BaseModel):
    evidence_id: str
    type: str
    tool: str
    target: str
    timestamp: datetime
    structured_data: dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = 0.0
    artifacts: list[ArtifactMetadata] = Field(default_factory=list)
    scope_status: str = "unknown"


class Evidence(BaseModel):
    # Legacy schema retained for backward compatibility while platform migrates
    # to `EvidenceObject`.
    id: str
    title: Optional[str] = None
    description: Optional[str] = None
    type: Optional[str] = None
    source: Optional[str] = None
    finding_id: Optional[str] = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finalized: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Phase 2 — structured evidence lifecycle schemas
# ---------------------------------------------------------------------------


class EvidenceValidationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    evidence_id: UUID
    campaign_id: UUID | None = None
    finding_id: UUID | None = None
    tenant_id: UUID | None = None
    actor: str
    validation_method: str
    validation_outcome: str
    notes: str | None = None
    validated_at: datetime


class EvidenceValidationCreate(BaseModel):
    evidence_id: UUID
    campaign_id: UUID | None = None
    finding_id: UUID | None = None
    tenant_id: UUID | None = None
    actor: str = Field(..., min_length=1, max_length=255)
    validation_method: str = Field(..., min_length=1, max_length=255)
    validation_outcome: str = Field(..., min_length=1, max_length=50)
    notes: str | None = Field(default=None, max_length=8000)


class ApprovalEvidenceLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    approval_gate_id: UUID
    evidence_id: UUID | None = None
    validation_id: UUID | None = None
    campaign_id: UUID | None = None
    linked_by: str
    link_reason: str | None = None
    reviewer_intention_snapshot: str | None = None
    created_at: datetime


class ApprovalEvidenceLinkCreate(BaseModel):
    approval_gate_id: UUID
    evidence_id: UUID | None = None
    validation_id: UUID | None = None
    campaign_id: UUID | None = None
    linked_by: str = Field(..., min_length=1, max_length=255)
    link_reason: str | None = Field(default=None, max_length=4000)


class EvidenceReadinessReport(BaseModel):
    """Computed readiness report for a piece of StructuredEvidence.

    No database table — computed on-demand by EvidenceLifecycleService.
    """

    evidence_id: UUID
    lifecycle_status: str
    has_validation: bool
    has_confirmed_validation: bool
    has_replay_artifacts: bool
    has_approval_link: bool
    report_ready: bool
    validation_count: int
    approval_link_count: int


class LifecycleAdvanceRequest(BaseModel):
    to_status: str = Field(..., min_length=1, max_length=50)
    actor: str = Field(..., min_length=1, max_length=255)


class ReplayFieldsPatch(BaseModel):
    replay_request_response_uri: str | None = Field(default=None, max_length=4096)
    replay_command_transcript_uri: str | None = Field(default=None, max_length=4096)
    replay_screen_recording_uri: str | None = Field(default=None, max_length=4096)
    replay_reproduction_steps: str | None = Field(default=None, max_length=32000)
    replay_terminal_ref: str | None = Field(default=None, max_length=1024)
