from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


_ASSET_TYPES = {"subdomain", "ip", "web", "screenshot", "provider", "cloud_bucket", "darknet_link"}


class AssetInventoryRegistry(BaseModel):
    """Canonical asset inventory record produced by ReconftwAgent."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    asset_type: str = Field(min_length=2, max_length=32)
    asset_value: str = Field(min_length=1, max_length=2048)
    target_root: str = Field(min_length=1, max_length=255)
    intel_source: str = Field(default="reconftw_meta_orchestrator", min_length=2, max_length=64)
    phase: str = Field(default="UNKNOWN", min_length=2, max_length=64)
    provider: str | None = Field(default=None, max_length=255)
    screenshot_path: str | None = Field(default=None, max_length=4096)
    metadata: dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("asset_type", mode="before")
    @classmethod
    def _normalize_asset_type(cls, value: str) -> str:
        token = str(value).strip().lower()
        if token == "darknet":
            token = "darknet_link"
        if token not in _ASSET_TYPES:
            # Fallback for dynamic types if needed, or strict enforcement
            return token
        return token

    @field_validator("asset_value", mode="before")
    @classmethod
    def _normalize_asset_value(cls, value: str) -> str:
        return str(value).strip()

    @field_validator("target_root", mode="before")
    @classmethod
    def _normalize_target_root(cls, value: str) -> str:
        return str(value).strip().lower()

    @field_validator("intel_source", mode="before")
    @classmethod
    def _normalize_intel_source(cls, value: str) -> str:
        return str(value).strip().lower().replace(" ", "_")

    @field_validator("phase", mode="before")
    @classmethod
    def _normalize_phase(cls, value: str) -> str:
        return str(value).strip().upper().replace(" ", "_")

    @field_validator("observed_at")
    @classmethod
    def _ensure_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
