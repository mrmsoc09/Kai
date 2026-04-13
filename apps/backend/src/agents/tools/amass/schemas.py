from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AmassAddress(BaseModel):
    """Canonical address payload emitted by amass JSON lines."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    ip: str = Field(min_length=1)
    cidr: str | None = None
    asn: int | None = None
    desc: str | None = None

    @field_validator("ip")
    @classmethod
    def _clean_ip(cls, value: str) -> str:
        token = value.strip()
        if not token:
            raise ValueError("ip must not be empty")
        return token


class AmassRawRecord(BaseModel):
    """Raw amass line object before K1 normalization."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    name: str = Field(min_length=1)
    domain: str | None = None
    addresses: list[AmassAddress | str | dict[str, Any]] = Field(default_factory=list)
    source: str | list[str] | None = None
    sources: list[str] = Field(default_factory=list)
    tag: str | None = None

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        token = value.strip()
        if not token:
            raise ValueError("name must not be empty")
        return token


class AmassNormalizedAsset(BaseModel):
    """
    K1-normalized representation used by AmassAgent.

    Mapping contract:
      - name -> fqdn
      - addresses -> ip_registry
      - source -> intel_origin
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    fqdn: str = Field(min_length=1)
    ip_registry: list[str] = Field(default_factory=list)
    intel_origin: str = Field(min_length=1)
    domain: str | None = None
    tag: str | None = None

    @classmethod
    def from_raw(cls, raw: AmassRawRecord) -> "AmassNormalizedAsset":
        ip_registry: list[str] = []
        for address in raw.addresses:
            if isinstance(address, AmassAddress):
                ip_registry.append(address.ip.strip())
                continue
            if isinstance(address, dict):
                ip = str(address.get("ip", "")).strip()
                if ip:
                    ip_registry.append(ip)
                continue
            if isinstance(address, str):
                token = address.strip()
                if token:
                    ip_registry.append(token)

        source_candidates: list[str] = []
        if isinstance(raw.source, list):
            source_candidates.extend(str(item).strip() for item in raw.source if str(item).strip())
        elif isinstance(raw.source, str) and raw.source.strip():
            source_candidates.append(raw.source.strip())

        source_candidates.extend(item.strip() for item in raw.sources if item.strip())
        intel_origin = source_candidates[0] if source_candidates else "amass"

        return cls(
            fqdn=raw.name.strip(),
            ip_registry=sorted(set(ip_registry)),
            intel_origin=intel_origin,
            domain=raw.domain,
            tag=raw.tag,
        )
