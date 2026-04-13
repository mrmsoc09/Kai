from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


_ALLOWED_RISK = {"critical", "high", "medium", "low", "info"}
_ALLOWED_LEAK = {"high", "medium", "low"}


class CorsyRawRecord(BaseModel):
    """Normalized raw CORSY finding object."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    url: str
    type: str = "cors_misconfig"
    severity: str = "medium"
    allow_credentials: bool | None = None
    access_control_allow_origin: str | None = None
    access_control_allow_credentials: str | None = None
    reflected_origin: str | None = None

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        token = value.strip()
        parsed = urlparse(token)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be a valid http/https URL")
        return token

    @field_validator("severity")
    @classmethod
    def _normalize_severity(cls, value: str) -> str:
        token = (value or "medium").strip().lower()
        if token not in _ALLOWED_RISK:
            return "medium"
        return token


class WebPolicyRegistry(BaseModel):
    """
    Canonical CORS policy finding model for CorsyAgent.

    Mapping contract:
      - url -> target_endpoint
      - type -> misconfig_type
      - severity -> risk_level
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    target_endpoint: str = Field(min_length=1)
    misconfig_type: str = "cors_misconfig"
    risk_level: str = "medium"
    allows_credentials: bool = False
    reflected_origin: str | None = None
    acao_header: str | None = None
    acac_header: str | None = None
    data_leak_potential: str = "low"
    poc_javascript: str = ""
    source: str = "corsy"
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_evidence: dict[str, Any] = Field(default_factory=dict)

    @field_validator("target_endpoint")
    @classmethod
    def _validate_target_endpoint(cls, value: str) -> str:
        token = value.strip()
        parsed = urlparse(token)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("target_endpoint must be a valid http/https URL")
        return token

    @field_validator("risk_level")
    @classmethod
    def _normalize_risk(cls, value: str) -> str:
        token = (value or "medium").strip().lower()
        if token not in _ALLOWED_RISK:
            return "medium"
        return token

    @field_validator("data_leak_potential")
    @classmethod
    def _normalize_leak(cls, value: str) -> str:
        token = (value or "low").strip().lower()
        if token not in _ALLOWED_LEAK:
            return "low"
        return token

    @classmethod
    def from_raw(
        cls,
        raw: CorsyRawRecord,
        *,
        allows_credentials: bool,
        data_leak_potential: str,
        poc_javascript: str,
    ) -> "WebPolicyRegistry":
        return cls(
            target_endpoint=raw.url,
            misconfig_type=raw.type,
            risk_level=raw.severity,
            allows_credentials=allows_credentials,
            reflected_origin=raw.reflected_origin,
            acao_header=raw.access_control_allow_origin,
            acac_header=raw.access_control_allow_credentials,
            data_leak_potential=data_leak_potential,
            poc_javascript=poc_javascript,
            raw_evidence=raw.model_dump(mode="json"),
        )
