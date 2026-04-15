from __future__ import annotations

from datetime import UTC, datetime
import re
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


_PARAM_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_ASSET_TYPE_RE = re.compile(r"^[a-z_]{2,32}$")
_ENDPOINT_PATH_RE = re.compile(r"^/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*$")
_XSS_TYPE_RE = re.compile(r"^(reflected|stored|dom|blind)_xss$")
_RISK_RE = re.compile(r"^(critical|high|medium|low|info)$")


class CrawlRegistry(BaseModel):
    """Normalized crawl/fuzz record for URL and JS discovery."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    crawl_url: str = Field(min_length=8, max_length=2048)
    discovered_from: str = Field(min_length=2, max_length=64)
    depth: int = Field(default=0, ge=0, le=32)
    asset_type: str = Field(default="url", min_length=2, max_length=32)
    is_javascript: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("crawl_url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("crawl_url must use http or https")
        if not parsed.netloc:
            raise ValueError("crawl_url must include host")
        return value.strip()

    @field_validator("discovered_from")
    @classmethod
    def _normalize_source(cls, value: str) -> str:
        token = value.strip().lower().replace(" ", "_")
        if not token:
            raise ValueError("discovered_from must not be empty")
        return token

    @field_validator("asset_type", mode="before")
    @classmethod
    def _normalize_asset_type(cls, value: str) -> str:
        return value.strip().lower().replace(" ", "_")

    @field_validator("asset_type")
    @classmethod
    def _validate_asset_type(cls, value: str) -> str:
        if not _ASSET_TYPE_RE.match(value):
            raise ValueError("asset_type format is invalid")
        return value

    @field_validator("timestamp")
    @classmethod
    def _ensure_tz(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class ParameterRegistry(BaseModel):
    """Normalized parameter mining record for downstream injection testing."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    endpoint_url: str = Field(min_length=8, max_length=2048)
    parameter_name: str = Field(min_length=1, max_length=64)
    source: str = Field(default="paramspider")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("endpoint_url")
    @classmethod
    def _validate_endpoint_url(cls, value: str) -> str:
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("endpoint_url must use http or https")
        if not parsed.netloc:
            raise ValueError("endpoint_url must include host")
        return value.strip()

    @field_validator("parameter_name")
    @classmethod
    def _validate_parameter_name(cls, value: str) -> str:
        token = value.strip()
        if not _PARAM_RE.match(token):
            raise ValueError("parameter_name format is invalid")
        return token

    @field_validator("source")
    @classmethod
    def _normalize_source(cls, value: str) -> str:
        token = value.strip().lower().replace(" ", "_")
        if not token:
            raise ValueError("source must not be empty")
        return token

    @field_validator("timestamp")
    @classmethod
    def _ensure_tz(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class WebDiscoveryRegistry(BaseModel):
    """Canonical registry for discovered web endpoints/assets in Phase 5/6."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    endpoint_url: str = Field(min_length=8, max_length=2048)
    endpoint_path: str = Field(min_length=1, max_length=1024)
    source_tool: str = Field(min_length=2, max_length=64)
    http_status: int | None = Field(default=None, ge=100, le=599)
    content_length: int | None = Field(default=None, ge=0)
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("endpoint_url")
    @classmethod
    def _validate_endpoint_url(cls, value: str) -> str:
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("endpoint_url must use http or https")
        if not parsed.netloc:
            raise ValueError("endpoint_url must include host")
        return value.strip()

    @field_validator("endpoint_path", mode="before")
    @classmethod
    def _normalize_path(cls, value: str) -> str:
        token = value.strip()
        if not token.startswith("/"):
            token = f"/{token}"
        return token

    @field_validator("endpoint_path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        if not _ENDPOINT_PATH_RE.match(value):
            raise ValueError("endpoint_path format is invalid")
        return value

    @field_validator("source_tool")
    @classmethod
    def _normalize_source_tool(cls, value: str) -> str:
        token = value.strip().lower().replace(" ", "_")
        if not token:
            raise ValueError("source_tool must not be empty")
        return token

    @field_validator("discovered_at")
    @classmethod
    def _ensure_tz(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class XssRegistry(BaseModel):
    """Canonical registry for Dalfox-confirmed XSS candidates."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    vulnerable_url: str = Field(min_length=8, max_length=2048)
    vulnerable_parameter: str = Field(min_length=1, max_length=64)
    payload: str = Field(min_length=1, max_length=2000)
    vuln_type: str = Field(default="reflected_xss")
    risk_level: str = Field(default="high")
    confirmed: bool = True
    detected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("vulnerable_url")
    @classmethod
    def _validate_vulnerable_url(cls, value: str) -> str:
        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("vulnerable_url must use http or https")
        if not parsed.netloc:
            raise ValueError("vulnerable_url must include host")
        return value.strip()

    @field_validator("vulnerable_parameter")
    @classmethod
    def _validate_parameter(cls, value: str) -> str:
        token = value.strip()
        if not _PARAM_RE.match(token):
            raise ValueError("vulnerable_parameter format is invalid")
        return token

    @field_validator("vuln_type", mode="before")
    @classmethod
    def _normalize_vuln_type(cls, value: str) -> str:
        token = value.strip().lower().replace(" ", "_")
        if token in {"xss", "reflected"}:
            return "reflected_xss"
        if token == "stored":
            return "stored_xss"
        if token == "dom":
            return "dom_xss"
        if token == "blind":
            return "blind_xss"
        return token

    @field_validator("vuln_type")
    @classmethod
    def _validate_vuln_type(cls, value: str) -> str:
        if not _XSS_TYPE_RE.match(value):
            raise ValueError("vuln_type must be reflected_xss|stored_xss|dom_xss|blind_xss")
        return value

    @field_validator("risk_level", mode="before")
    @classmethod
    def _normalize_risk(cls, value: str) -> str:
        token = value.strip().lower()
        return token

    @field_validator("risk_level")
    @classmethod
    def _validate_risk(cls, value: str) -> str:
        if not _RISK_RE.match(value):
            raise ValueError("risk_level must be critical|high|medium|low|info")
        return value

    @field_validator("detected_at")
    @classmethod
    def _ensure_tz(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
