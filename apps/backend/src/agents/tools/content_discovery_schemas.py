from __future__ import annotations

from datetime import UTC, datetime
from urllib.parse import urlparse
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


_PARAM_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")
_ASSET_TYPE_RE = re.compile(r"^[a-z_]{2,32}$")


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
