from __future__ import annotations

from datetime import UTC, datetime
import re
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


_DOMAIN_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$"
)
_HANDLE_PATTERN = re.compile(r"^[A-Za-z0-9._-]{2,64}$")
_PLATFORM_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{1,31}$")


class DiscoveryRegistry(BaseModel):
    """Normalized passive discovery record used by OSINT fixture stubs."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    discovered_domain: str = Field(min_length=1)
    intel_source: str = Field(min_length=2, max_length=64)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("discovered_domain", mode="before")
    @classmethod
    def _normalize_domain(cls, value: str) -> str:
        candidate = value.strip().lower().rstrip(".")
        if candidate.startswith("*."):
            candidate = candidate[2:]
        if len(candidate) > 253:
            raise ValueError("discovered_domain exceeds maximum DNS length")
        return candidate

    @field_validator("intel_source")
    @classmethod
    def _normalize_intel_source(cls, value: str) -> str:
        token = value.strip().lower().replace(" ", "_")
        if not token:
            raise ValueError("intel_source must not be empty")
        return token

    @field_validator("timestamp")
    @classmethod
    def _ensure_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    @field_validator("discovered_domain")
    @classmethod
    def _validate_domain_pattern(cls, value: str) -> str:
        if not _DOMAIN_PATTERN.match(value):
            raise ValueError("discovered_domain must be a valid domain-like value")
        return value


class IdentityRegistry(BaseModel):
    """Normalized social identity profile record for OSINT fixture stubs."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    social_handle: str = Field(min_length=2, max_length=64)
    platform_detected: str = Field(min_length=2, max_length=32)
    profile_url: str = Field(min_length=8, max_length=2048)

    @field_validator("social_handle", mode="before")
    @classmethod
    def _normalize_handle(cls, value: str) -> str:
        token = value.strip()
        if token.startswith("@"):
            token = token[1:]
        return token

    @field_validator("platform_detected", mode="before")
    @classmethod
    def _normalize_platform(cls, value: str) -> str:
        return value.strip().lower().replace(" ", "_")

    @field_validator("social_handle")
    @classmethod
    def _validate_handle_pattern(cls, value: str) -> str:
        if not _HANDLE_PATTERN.match(value):
            raise ValueError("social_handle format is invalid")
        return value

    @field_validator("platform_detected")
    @classmethod
    def _validate_platform_pattern(cls, value: str) -> str:
        if not _PLATFORM_PATTERN.match(value):
            raise ValueError("platform_detected format is invalid")
        return value

    @field_validator("profile_url")
    @classmethod
    def _validate_profile_url(cls, value: str) -> str:
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("profile_url must use http or https")
        if not parsed.netloc:
            raise ValueError("profile_url must include a host")
        return value.strip()
