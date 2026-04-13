from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator


class HttpxRawRecord(BaseModel):
    """Raw JSON line emitted by httpx."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    url: str = Field(min_length=1)
    title: str | None = None
    tech: list[str] | str | None = None
    status_code: int | str | None = None
    ip: str | list[str] | None = None
    cname: str | list[str] | None = None
    server: str | None = None
    webserver: str | None = None
    content_length: int | str | None = None
    cdn: bool | str | None = None
    cdn_name: str | None = None

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        token = value.strip()
        parsed = urlparse(token)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be a valid http/https URL")
        return token


class ServiceRegistry(BaseModel):
    """
    Canonical web-service registry record for HttpxProbeAgent.

    Mapping contract:
      - url -> service_url
      - title -> page_title
      - tech -> tech_stack
      - status_code -> http_status
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    service_url: str = Field(min_length=1)
    page_title: str = ""
    tech_stack: list[str] = Field(default_factory=list)
    http_status: int = Field(ge=0, le=599)
    resolved_ips: list[str] = Field(default_factory=list)
    cname_records: list[str] = Field(default_factory=list)
    server_header: str = ""
    content_length: int | None = Field(default=None, ge=0)
    target_domain: str | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_evidence: dict[str, Any] = Field(default_factory=dict)

    @field_validator("service_url")
    @classmethod
    def _validate_service_url(cls, value: str) -> str:
        token = value.strip()
        parsed = urlparse(token)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("service_url must be a valid http/https URL")
        return token

    @classmethod
    def from_raw(cls, raw: HttpxRawRecord, target_domain: str | None = None) -> "ServiceRegistry":
        tech_stack: list[str] = []
        if isinstance(raw.tech, list):
            tech_stack.extend(str(item).strip() for item in raw.tech if str(item).strip())
        elif isinstance(raw.tech, str):
            tech_stack.extend(
                token.strip() for token in raw.tech.replace(";", ",").split(",") if token.strip()
            )

        resolved_ips: list[str] = []
        if isinstance(raw.ip, list):
            resolved_ips.extend(str(item).strip() for item in raw.ip if str(item).strip())
        elif isinstance(raw.ip, str) and raw.ip.strip():
            resolved_ips.append(raw.ip.strip())

        cname_records: list[str] = []
        if isinstance(raw.cname, list):
            cname_records.extend(str(item).strip().lower() for item in raw.cname if str(item).strip())
        elif isinstance(raw.cname, str) and raw.cname.strip():
            cname_records.append(raw.cname.strip().lower())

        status = 0
        if isinstance(raw.status_code, int):
            status = raw.status_code
        elif isinstance(raw.status_code, str) and raw.status_code.strip().isdigit():
            status = int(raw.status_code.strip())

        content_length: int | None = None
        if isinstance(raw.content_length, int):
            content_length = raw.content_length
        elif isinstance(raw.content_length, str):
            token = raw.content_length.strip()
            if token.isdigit():
                content_length = int(token)

        server_header = (raw.server or raw.webserver or "").strip()

        return cls(
            service_url=raw.url,
            page_title=(raw.title or "").strip(),
            tech_stack=sorted(set(tech_stack)),
            http_status=status,
            resolved_ips=sorted(set(resolved_ips)),
            cname_records=sorted(set(cname_records)),
            server_header=server_header,
            content_length=content_length,
            target_domain=target_domain,
            raw_evidence=raw.model_dump(mode="json"),
        )
