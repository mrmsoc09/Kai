from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


_ALLOWED_SEVERITIES = {"critical", "high", "medium", "low", "info", "unknown"}


class NucleiInfoRecord(BaseModel):
    """Inner `info` object emitted by nuclei JSONL."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    name: str = ""
    severity: str = "unknown"
    description: str = ""
    reference: list[str] = Field(default_factory=list)

    @field_validator("severity")
    @classmethod
    def _normalize_severity(cls, value: str) -> str:
        token = (value or "unknown").strip().lower()
        if token not in _ALLOWED_SEVERITIES:
            return "unknown"
        return token


class NucleiRawRecord(BaseModel):
    """Raw line-delimited JSON object emitted by nuclei."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True, populate_by_name=True)

    template_id: str = Field(alias="template-id", min_length=1)
    template_path: str | None = Field(default=None, alias="template")
    matched_at: str = Field(alias="matched-at", min_length=1)
    host: str | None = None
    ip: str | None = None
    type: str | None = None
    curl_command: str | None = Field(default=None, alias="curl-command")
    info: NucleiInfoRecord = Field(default_factory=NucleiInfoRecord)


class VulnerabilityRegistry(BaseModel):
    """
    Canonical vulnerability registry record for NucleiScanAgent.

    Mapping contract:
      - template-id -> vuln_id
      - info.name -> vuln_name
      - info.severity -> risk_level
      - matched-at -> target_endpoint
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    vuln_id: str = Field(min_length=1)
    vuln_name: str = ""
    risk_level: str = "unknown"
    target_endpoint: str = Field(min_length=1)
    target_host: str | None = None
    target_ip: str | None = None
    vuln_type: str | None = None
    template_path: str | None = None
    references: list[str] = Field(default_factory=list)
    description: str = ""
    curl_command: str | None = None
    dedupe_hash: str = Field(min_length=8)
    scanned_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_evidence: dict[str, Any] = Field(default_factory=dict)

    @field_validator("risk_level")
    @classmethod
    def _normalize_risk(cls, value: str) -> str:
        token = (value or "unknown").strip().lower()
        if token not in _ALLOWED_SEVERITIES:
            return "unknown"
        return token

    @classmethod
    def from_raw(cls, raw: NucleiRawRecord, *, dedupe_hash: str) -> "VulnerabilityRegistry":
        return cls(
            vuln_id=raw.template_id,
            vuln_name=(raw.info.name or "").strip(),
            risk_level=(raw.info.severity or "unknown").strip().lower(),
            target_endpoint=raw.matched_at,
            target_host=raw.host,
            target_ip=raw.ip,
            vuln_type=raw.type,
            template_path=raw.template_path,
            references=[str(item).strip() for item in (raw.info.reference or []) if str(item).strip()],
            description=(raw.info.description or "").strip(),
            curl_command=raw.curl_command,
            dedupe_hash=dedupe_hash,
            raw_evidence=raw.model_dump(by_alias=True, mode="json"),
        )
