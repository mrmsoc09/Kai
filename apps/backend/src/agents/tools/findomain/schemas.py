from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DiscoveryRegistry(BaseModel):
    """
    Canonical discovery record for FindomainAgent.

    Mapping contract:
      - subdomain/domain/host -> discovered_domain
      - source -> passive_findomain
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    discovered_domain: str = Field(min_length=1)
    source: str = "passive_findomain"
    root_domain: str | None = None
    resolved_ips: list[str] = Field(default_factory=list)
    http_status: int | None = Field(default=None, ge=0, le=599)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_evidence: dict[str, Any] = Field(default_factory=dict)

    @field_validator("discovered_domain")
    @classmethod
    def _normalize_domain(cls, value: str) -> str:
        token = value.strip().lower()
        if token.startswith("*."):
            token = token[2:]
        if "." not in token or " " in token:
            raise ValueError("discovered_domain must be a valid domain-like value")
        return token

