from __future__ import annotations

from datetime import UTC, datetime
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


_ONION_DOMAIN_RE = re.compile(r"^[a-z0-9]{16,56}\.onion$", re.IGNORECASE)
_ALLOWED_RISKS = {"critical", "high", "medium", "low", "info", "unknown"}


class DiscoveryRegistry(BaseModel):
    """Normalized darknet discovery record for TOR-origin intelligence."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    discovered_domain: str = Field(min_length=10, max_length=80)
    intel_source: str = Field(default="tor")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    onion_url: str | None = None
    source_engine: str | None = None
    crawl_depth: int = Field(default=0, ge=0, le=10)

    @field_validator("discovered_domain", mode="before")
    @classmethod
    def _normalize_domain(cls, value: str) -> str:
        token = value.strip().lower().rstrip(".")
        if token.startswith("http://") or token.startswith("https://"):
            token = token.split("//", 1)[1].split("/", 1)[0]
        return token

    @field_validator("discovered_domain")
    @classmethod
    def _validate_onion_domain(cls, value: str) -> str:
        if not _ONION_DOMAIN_RE.match(value):
            raise ValueError("discovered_domain must be a valid .onion host")
        return value

    @field_validator("intel_source", mode="before")
    @classmethod
    def _normalize_intel_source(cls, value: str) -> str:
        token = value.strip().lower().replace(" ", "_")
        return token or "tor"

    @field_validator("source_engine", mode="before")
    @classmethod
    def _normalize_engine(cls, value: str | None) -> str | None:
        if value is None:
            return None
        token = value.strip().lower().replace(" ", "_")
        return token or None

    @field_validator("timestamp")
    @classmethod
    def _ensure_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class SecretLeakRegistry(BaseModel):
    """Normalized secret-leak record with mandatory masking semantics."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    vuln_type: str = Field(min_length=2, max_length=128)
    location: str = Field(min_length=1, max_length=2048)
    risk_level: str = Field(default="critical")
    source_tool: str = Field(min_length=2, max_length=64)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    masked: bool = True

    @field_validator("vuln_type", mode="before")
    @classmethod
    def _normalize_vuln_type(cls, value: str) -> str:
        token = value.strip().lower().replace(" ", "_")
        return token or "unknown_secret"

    @field_validator("location", mode="before")
    @classmethod
    def _normalize_location(cls, value: str) -> str:
        return value.strip()

    @field_validator("risk_level", mode="before")
    @classmethod
    def _normalize_risk(cls, value: str) -> str:
        token = value.strip().lower()
        if token not in _ALLOWED_RISKS:
            return "critical"
        return token

    @field_validator("risk_level")
    @classmethod
    def _enforce_critical_floor(cls, value: str) -> str:
        # Secret leaks are always treated as critical in this pipeline.
        return "critical"

    @field_validator("source_tool", mode="before")
    @classmethod
    def _normalize_source_tool(cls, value: str) -> str:
        return value.strip().lower().replace(" ", "_")

    @field_validator("observed_at")
    @classmethod
    def _ensure_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class VulnerabilityRegistry(SecretLeakRegistry):
    """Backward-compatible alias used by existing scanners/tests."""
