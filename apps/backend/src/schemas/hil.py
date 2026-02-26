from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


SeverityLiteral = Literal["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]


class FindingCreate(BaseModel):
    program: str = Field(..., min_length=1)
    asset: str = Field(..., min_length=1)
    title: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    severity: SeverityLiteral


class EvidenceCreate(BaseModel):
    kind: str = Field(..., min_length=1)
    uri: str = Field(..., min_length=1)
    sha256_hex: str = Field(..., min_length=64, max_length=64)
    meta: dict = Field(default_factory=dict)


class Checklist(BaseModel):
    repro_steps: bool
    http_traces_or_logs: bool
    poc_or_screencap: bool
    scope_confirmation: bool
    impact_rationale: bool


class HILRequest(BaseModel):
    notes: Optional[str] = None


class HILApprove(BaseModel):
    checklist: Checklist
    notes: Optional[str] = None


class SubmitBody(BaseModel):
    report_content_hash_hex: str = Field(..., min_length=64, max_length=64)


class ScopeUpsert(BaseModel):
    allowed_assets: Optional[list[str]] = None
    excluded_assets: Optional[list[str]] = None
    allowed_domains: Optional[list[str]] = None
    excluded_domains: Optional[list[str]] = None
    min_severity: Optional[SeverityLiteral] = "LOW"
    notes: Optional[str] = None
