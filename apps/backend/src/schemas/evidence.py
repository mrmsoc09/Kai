from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    finalized: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
