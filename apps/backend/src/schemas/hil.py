from __future__ import annotations

import json
import re
from typing import Literal, Optional

import pydantic
from pydantic import BaseModel, Field


SeverityLiteral = Literal["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]

_URI_RE = re.compile(r'^(https?|file|evidence|ftp)://.{1,2000}$')
_SHA256_RE = re.compile(r'^[0-9a-f]{64}$')
_MAX_META_BYTES = 10_240  # 10 KB


class FindingCreate(BaseModel):
    program: str = Field(..., min_length=1, max_length=100)
    asset: str = Field(..., min_length=1, max_length=500)
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=10_000)
    severity: SeverityLiteral

    @classmethod
    def __get_validators__(cls):
        yield from super().__get_validators__()


class EvidenceCreate(BaseModel):
    kind: str = Field(..., min_length=1, max_length=64)
    uri: str = Field(..., min_length=1, max_length=2048)
    sha256_hex: str = Field(..., min_length=64, max_length=64)
    meta: dict = Field(default_factory=dict)

    @pydantic.field_validator('uri')
    @classmethod
    def validate_uri(cls, v: str) -> str:
        if not _URI_RE.match(v):
            raise ValueError('uri must start with http://, https://, file://, or evidence://')
        return v

    @pydantic.field_validator('sha256_hex')
    @classmethod
    def validate_sha256(cls, v: str) -> str:
        if not _SHA256_RE.match(v.lower()):
            raise ValueError('sha256_hex must be exactly 64 lowercase hex characters')
        return v.lower()

    @pydantic.field_validator('meta')
    @classmethod
    def validate_meta_size(cls, v: dict) -> dict:
        if len(json.dumps(v)) > _MAX_META_BYTES:
            raise ValueError(f'meta field exceeds {_MAX_META_BYTES} byte limit')
        return v


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
