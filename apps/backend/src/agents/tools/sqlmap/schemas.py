from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


_ALLOWED_SEVERITIES = {"critical", "high", "medium", "low", "info"}


class SqlmapRawRecord(BaseModel):
    """Normalized raw SQLMap extraction from stdout/stderr/session artifacts."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    dbms: str = "unknown"
    place: str = "unknown"
    parameter: str = "unknown"
    payload: str | None = None
    phase: str = "testing"
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    evidence: str = ""

    @field_validator("phase")
    @classmethod
    def _normalize_phase(cls, value: str) -> str:
        token = (value or "testing").strip().lower()
        if token not in {"testing", "exploitation"}:
            return "testing"
        return token


class DatabaseSecurityRegistry(BaseModel):
    """
    Canonical DB-security record for SqlmapAgent.

    Mapping contract:
      - dbms -> db_technology
      - place -> injection_point
      - parameter -> vuln_parameter
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    db_technology: str = "unknown"
    injection_point: str = "unknown"
    vuln_parameter: str = "unknown"
    phase: str = "testing"
    severity: str = "high"
    target_url: str | None = None
    payload_sample: str | None = None
    session_path: str | None = None
    is_schema_mapped: bool = False
    confirmed_injection: bool = True
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_evidence: dict[str, Any] = Field(default_factory=dict)

    @field_validator("severity")
    @classmethod
    def _normalize_severity(cls, value: str) -> str:
        token = (value or "info").strip().lower()
        if token not in _ALLOWED_SEVERITIES:
            return "info"
        return token

    @field_validator("phase")
    @classmethod
    def _normalize_phase(cls, value: str) -> str:
        token = (value or "testing").strip().lower()
        if token not in {"testing", "exploitation"}:
            return "testing"
        return token

    @classmethod
    def from_raw(
        cls,
        raw: SqlmapRawRecord,
        *,
        target_url: str,
        session_path: str,
        severity: str,
        schema_mapped: bool,
    ) -> "DatabaseSecurityRegistry":
        return cls(
            db_technology=(raw.dbms or "unknown").strip(),
            injection_point=(raw.place or "unknown").strip(),
            vuln_parameter=(raw.parameter or "unknown").strip(),
            phase=raw.phase,
            severity=severity,
            target_url=target_url,
            payload_sample=raw.payload,
            session_path=session_path,
            is_schema_mapped=schema_mapped,
            confirmed_injection=True,
            confidence=raw.confidence,
            raw_evidence=raw.model_dump(mode="json"),
        )
