from __future__ import annotations

from datetime import UTC, datetime
import ipaddress
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


_HOST_OR_CIDR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$")
_PROTOCOL_RE = re.compile(r"^(tcp|udp)$")
_CATEGORY_RE = re.compile(r"^[a-z_]{2,32}$")


class PortServiceRegistry(BaseModel):
    """Normalized open port/service record for fixture-based scan stubs."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    target_ip: str = Field(min_length=2, max_length=253)
    port_number: int = Field(ge=1, le=65535)
    proto_type: str = Field(default="tcp")
    service_name: str | None = None
    product: str | None = None
    version: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("target_ip")
    @classmethod
    def _validate_ip_or_host(cls, value: str) -> str:
        token = value.strip().lower().rstrip(".")
        try:
            ipaddress.ip_address(token)
            return token
        except ValueError:
            if not _HOST_OR_CIDR_RE.match(token):
                raise ValueError("target_ip must be an IP address or host")
            return token

    @field_validator("proto_type", mode="before")
    @classmethod
    def _normalize_proto(cls, value: str) -> str:
        token = value.strip().lower()
        return token

    @field_validator("proto_type")
    @classmethod
    def _validate_proto(cls, value: str) -> str:
        if not _PROTOCOL_RE.match(value):
            raise ValueError("proto_type must be tcp or udp")
        return value

    @field_validator("timestamp")
    @classmethod
    def _ensure_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class TargetRegistry(BaseModel):
    """Normalized target posture record for WAF pre-checks."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    target: str = Field(min_length=2, max_length=512)
    waf_present: bool
    waf_name: str | None = None
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("target")
    @classmethod
    def _normalize_target(cls, value: str) -> str:
        token = value.strip().lower()
        if not token:
            raise ValueError("target must not be empty")
        return token

    @field_validator("checked_at")
    @classmethod
    def _ensure_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class TechStackRegistry(BaseModel):
    """Normalized technology fingerprint record from WhatWeb fixtures."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    target: str = Field(min_length=2, max_length=512)
    technology_name: str = Field(min_length=2, max_length=128)
    category: str = Field(min_length=2, max_length=32)
    version: str | None = None
    source: str = Field(default="whatweb")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("target")
    @classmethod
    def _normalize_target(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("technology_name")
    @classmethod
    def _normalize_tech_name(cls, value: str) -> str:
        return value.strip()

    @field_validator("category", mode="before")
    @classmethod
    def _normalize_category(cls, value: str) -> str:
        return value.strip().lower().replace(" ", "_")

    @field_validator("category")
    @classmethod
    def _validate_category(cls, value: str) -> str:
        if not _CATEGORY_RE.match(value):
            raise ValueError("category format is invalid")
        return value

    @field_validator("source")
    @classmethod
    def _normalize_source(cls, value: str) -> str:
        token = value.strip().lower().replace(" ", "_")
        if not token:
            raise ValueError("source must not be empty")
        return token

    @field_validator("timestamp")
    @classmethod
    def _ensure_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
