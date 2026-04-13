from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SubfinderRawRecord(BaseModel):
    """Raw Subfinder JSON line record."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    host: str = Field(min_length=1)
    source: str | list[str] | None = None
    ip: str | list[str] | None = None
    input: str | None = None

    @field_validator("host")
    @classmethod
    def _normalize_host(cls, value: str) -> str:
        token = value.strip().lower()
        if not token:
            raise ValueError("host must not be empty")
        if token.startswith(".") or token.endswith(".") or ".." in token:
            raise ValueError("host is not a valid fqdn")
        return token


class IntelRegistry(BaseModel):
    """
    Canonical passive-intelligence registry record for Subfinder.

    Mapping contract:
      - host -> fqdn
      - source -> intel_origin
      - ip -> resolved_ips
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    fqdn: str = Field(min_length=1, max_length=253)
    intel_origin: str = Field(min_length=1)
    resolved_ips: list[str] = Field(default_factory=list)
    target_domain: str | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_evidence: dict[str, Any] = Field(default_factory=dict)

    @field_validator("fqdn")
    @classmethod
    def _validate_fqdn(cls, value: str) -> str:
        token = value.strip().lower()
        if not token:
            raise ValueError("fqdn must not be empty")
        if token.startswith(".") or token.endswith(".") or ".." in token:
            raise ValueError("fqdn format is invalid")
        return token

    @classmethod
    def from_raw(cls, raw: SubfinderRawRecord) -> "IntelRegistry":
        source_candidates: list[str] = []
        if isinstance(raw.source, list):
            source_candidates.extend(str(item).strip() for item in raw.source if str(item).strip())
        elif isinstance(raw.source, str) and raw.source.strip():
            source_candidates.append(raw.source.strip())
        intel_origin = source_candidates[0] if source_candidates else "subfinder"

        resolved_ips: list[str] = []
        if isinstance(raw.ip, list):
            resolved_ips.extend(str(item).strip() for item in raw.ip if str(item).strip())
        elif isinstance(raw.ip, str) and raw.ip.strip():
            resolved_ips.append(raw.ip.strip())

        return cls(
            fqdn=raw.host,
            intel_origin=intel_origin,
            resolved_ips=sorted(set(resolved_ips)),
            target_domain=(raw.input or "").strip() or None,
            raw_evidence=raw.model_dump(mode="json"),
        )
