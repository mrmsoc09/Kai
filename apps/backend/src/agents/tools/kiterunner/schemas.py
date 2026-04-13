from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


class KiterunnerRawRecord(BaseModel):
    """Raw kiterunner record from JSONL or line-adapted parser."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    url: str | None = None
    path: str | None = None
    method: str | None = None
    status: int | str | None = None
    status_code: int | str | None = None
    length: int | str | None = None
    content_length: int | str | None = None

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        token = value.strip()
        parsed = urlparse(token)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be a valid http/https URL")
        return token


class EndpointRegistry(BaseModel):
    """
    Canonical endpoint finding model for KiterunnerAgent.

    Mapping contract:
      - path -> endpoint_path
      - status/status_code -> http_status
      - method -> http_method
      - content_length/length -> response_size
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    endpoint_path: str = Field(min_length=1)
    http_status: int = Field(ge=0, le=599)
    http_method: str = "GET"
    response_size: int | None = Field(default=None, ge=0)
    service_url: str = Field(min_length=1)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_evidence: dict[str, Any] = Field(default_factory=dict)

    @field_validator("endpoint_path")
    @classmethod
    def _validate_endpoint_path(cls, value: str) -> str:
        token = value.strip()
        if not token.startswith("/"):
            token = f"/{token}"
        return token

    @field_validator("service_url")
    @classmethod
    def _validate_service_url(cls, value: str) -> str:
        token = value.strip()
        parsed = urlparse(token)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("service_url must be a valid http/https URL")
        return token

    @classmethod
    def from_raw(cls, raw: KiterunnerRawRecord, *, target_url: str) -> "EndpointRegistry":
        status_value = raw.status_code if raw.status_code is not None else raw.status
        status = 0
        if isinstance(status_value, int):
            status = status_value
        elif isinstance(status_value, str) and status_value.strip().isdigit():
            status = int(status_value.strip())

        size_value = raw.content_length if raw.content_length is not None else raw.length
        size: int | None = None
        if isinstance(size_value, int):
            size = size_value
        elif isinstance(size_value, str) and size_value.strip().isdigit():
            size = int(size_value.strip())

        method = (raw.method or "GET").strip().upper() or "GET"

        service_url = target_url
        endpoint_path = "/"
        if raw.url:
            parsed = urlparse(raw.url)
            service_url = f"{parsed.scheme}://{parsed.netloc}"
            endpoint_path = parsed.path or "/"
        elif raw.path:
            endpoint_path = raw.path
        elif raw.url is None and raw.path is None:
            parsed_target = urlparse(target_url)
            endpoint_path = parsed_target.path or "/"

        return cls(
            endpoint_path=endpoint_path,
            http_status=status,
            http_method=method,
            response_size=size,
            service_url=service_url,
            raw_evidence=raw.model_dump(mode="json"),
        )
