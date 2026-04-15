from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class BountyWalletRegistry(BaseModel):
    """
    K1 Dual-Ledger Bounty Wallet Registry.
    Tracks expected income from BBP platforms and validated credits from exchanges/banks.
    """
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    finding_id: str = Field(min_length=1, max_length=128)
    run_id: str = Field(min_length=1, max_length=128)
    program_name: str = Field(min_length=1, max_length=255)
    platform: str = Field(default="custom", description="HackerOne, Bugcrowd, Intigriti, etc.")
    
    # Dual-Ledger Fields
    expected_amount: float = Field(default=0.0, ge=0.0)
    validated_amount: float = Field(default=0.0, ge=0.0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    
    status: str = Field(default="triaged", description="triaged, pending_payout, validated, rejected")
    verification_required: bool = Field(default=True)
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("currency")
    @classmethod
    def _normalize_currency(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("observed_at", "verified_at", "updated_at")
    @classmethod
    def _ensure_timezone_aware(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
