from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
import ipaddress

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class NaabuRawRecord(BaseModel):
    """Raw JSON line emitted by naabu."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    ip: str | None = None
    host: str | None = None
    port: int | str
    protocol: str | None = "tcp"

    @field_validator("ip")
    @classmethod
    def _validate_ip(cls, value: str | None) -> str | None:
        if value is None:
            return value
        token = value.strip()
        if not token:
            return None
        try:
            ipaddress.ip_address(token)
        except ValueError as exc:
            raise ValueError("ip must be a valid IPv4 or IPv6 address") from exc
        return token

    @field_validator("host")
    @classmethod
    def _normalize_host(cls, value: str | None) -> str | None:
        if value is None:
            return value
        token = value.strip().lower()
        return token or None

    @field_validator("port")
    @classmethod
    def _validate_port(cls, value: int | str) -> int:
        if isinstance(value, int):
            port = value
        elif isinstance(value, str) and value.strip().isdigit():
            port = int(value.strip())
        else:
            raise ValueError("port must be an integer")
        if port < 1 or port > 65535:
            raise ValueError("port must be between 1 and 65535")
        return port

    @field_validator("protocol")
    @classmethod
    def _normalize_protocol(cls, value: str | None) -> str:
        token = (value or "tcp").strip().lower()
        return token or "tcp"

    @model_validator(mode="after")
    def _ensure_target_present(self) -> "NaabuRawRecord":
        if not self.ip and not self.host:
            raise ValueError("either ip or host is required")
        return self


class PortRegistry(BaseModel):
    """
    Canonical open-port registry record for NaabuAgent.

    Mapping contract:
      - ip -> target_ip
      - port -> port_number
      - protocol -> proto_type
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    target_ip: str = Field(min_length=1)
    port_number: int = Field(ge=1, le=65535)
    proto_type: str = "tcp"
    target_host: str | None = None
    service_hint: str = "unknown"
    is_web_port: bool = False
    target_scope: str | None = None
    scanned_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_evidence: dict[str, Any] = Field(default_factory=dict)

    @field_validator("target_ip")
    @classmethod
    def _validate_target_ip(cls, value: str) -> str:
        token = value.strip()
        if not token:
            raise ValueError("target_ip is required")
        return token

    @field_validator("proto_type")
    @classmethod
    def _normalize_proto(cls, value: str) -> str:
        token = value.strip().lower()
        return token or "tcp"

    @classmethod
    def from_raw(
        cls,
        raw: NaabuRawRecord,
        *,
        target_scope: str | None,
        service_hint: str,
        is_web_port: bool,
    ) -> "PortRegistry":
        target_ip = raw.ip or (raw.host or "")
        return cls(
            target_ip=target_ip,
            port_number=int(raw.port),
            proto_type=(raw.protocol or "tcp"),
            target_host=raw.host,
            service_hint=service_hint,
            is_web_port=is_web_port,
            target_scope=target_scope,
            raw_evidence=raw.model_dump(mode="json"),
        )
