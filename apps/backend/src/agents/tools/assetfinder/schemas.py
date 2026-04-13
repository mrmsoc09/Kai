from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DiscoveryRegistry(BaseModel):
    """
    Canonical passive discovery finding model for AssetfinderAgent.

    Mapping contract:
      - line -> discovered_domain
      - source -> passive_assetfinder
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    discovered_domain: str = Field(min_length=1)
    source: str = "passive_assetfinder"
    root_domain: str | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_evidence: dict[str, Any] = Field(default_factory=dict)

    @field_validator("discovered_domain")
    @classmethod
    def _validate_discovered_domain(cls, value: str) -> str:
        token = value.strip().lower()
        if token.startswith("*."):
            token = token[2:]
        if "." not in token:
            raise ValueError("discovered_domain must be a domain-like value")
        if " " in token:
            raise ValueError("discovered_domain cannot contain spaces")
        return token

