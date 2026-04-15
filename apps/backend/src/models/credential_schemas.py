"""Pydantic schemas for credentials API."""
from __future__ import annotations

from pydantic import BaseModel, Field


class StoreCredentialRequest(BaseModel):
    """Request to store a credential."""

    access_type: str = Field(
        ...,
        description='Type of access: "user_account", "api_key", "hunter_account", "admin_account"',
    )
    credentials: dict = Field(..., description="Dict of credential fields (username, password, api_key, etc.)")
    username: str | None = Field(None, description="Plaintext username/email for display (not the password)")
    notes: str | None = Field(None, description="Optional analyst notes")


class CredentialResponse(BaseModel):
    """Response containing credential metadata (no plaintext secrets)."""

    id: str
    program_id: str
    access_type: str
    status: str  # active, expired, invalid, needs_renewal
    credential_username: str | None
    last_validated: str | None
    validation_method: str | None
    created_at: str
    updated_at: str
    notes: str | None
    access_count: int
    last_accessed_at: str | None
    last_accessed_by: str | None


class ListCredentialsResponse(BaseModel):
    """Response containing list of credentials for a program."""

    program_id: str
    credentials: list[CredentialResponse]


class ScanningModesResponse(BaseModel):
    """Response containing available scanning modes for a program."""

    program_id: str
    available_modes: list[str]  # ["unauthenticated", "user_account", "api_key", "hunter_account"]
    warnings: list[dict]  # [{type, access_type, message, signup_url}, ...]
    recommendation: str


class ValidateCredentialRequest(BaseModel):
    """Request to validate a credential."""

    pass  # No fields needed


class ValidateCredentialResponse(BaseModel):
    """Response from credential validation."""

    valid: bool
    reason: str
    tested_at: str | None = None


class AccessMetadataRequest(BaseModel):
    """Request to create/update access metadata."""

    access_type: str = Field(
        ...,
        description='Type of access: "unauthenticated", "user_account", "api_key", "hunter_account", "admin_account"',
    )
    enabled: bool = Field(True, description="Is this access type available?")
    signup_url: str | None = Field(None, description="URL to sign up for this access type")
    signup_instructions: str | None = Field(None, description="Instructions on how to sign up")
    requires_email: bool = Field(False, description="Does signup require an email address?")
    requires_payment: bool = Field(False, description="Does this cost money?")
    rate_limits: str | None = Field(None, description='Rate limit info, e.g., "100 requests/minute"')
    available_endpoints: str | None = Field(None, description="Available API endpoints (JSON string)")
    testing_account_available: bool = Field(False, description="Is a testing account provided?")
    testing_account_url: str | None = Field(None, description="URL to apply for a testing account")
    testing_instructions: str | None = Field(None, description="Instructions for getting a testing account")


class AccessMetadataResponse(BaseModel):
    """Response containing access metadata."""

    id: str
    program_id: str
    access_type: str
    enabled: bool
    signup_url: str | None
    signup_instructions: str | None
    requires_email: bool
    requires_payment: bool
    rate_limits: str | None
    available_endpoints: str | None
    testing_account_available: bool
    testing_account_url: str | None
    testing_instructions: str | None
    created_at: str
    updated_at: str
