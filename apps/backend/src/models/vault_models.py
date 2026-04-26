"""
Pydantic models for Vault API endpoints.

Defines request/response schemas for secret management operations.
All models validate input and never include secret values in responses.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class StoreSecretRequest(BaseModel):
    """Request to store a new secret in Vault."""

    name: str = Field(..., description="Secret name (e.g., OPENAI_API_KEY)")
    type: str = Field(..., description="Secret type (e.g., api_key, token)")
    value: Optional[str] = Field(None, description="The secret value (never logged)")
    fields: Optional[Dict[str, str]] = Field(
        None,
        description=(
            "Optional structured secret fields (e.g., username/token pairs). "
            "When provided, all non-empty fields are stored."
        ),
    )
    description: Optional[str] = Field(None, description="Human-readable description")
    tags: Optional[List[str]] = Field(None, description="Tags for categorization")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "OPENAI_API_KEY",
                "type": "api_key",
                "value": "sk-...",
                "description": "OpenAI API key for chat completions",
                "tags": ["ai", "openai"],
            }
        }


class StoreNetworkCredentialRequest(BaseModel):
    """Request to store VPN/Proxy network credential payload in Vault."""

    username: Optional[str] = Field(None, description="Provider username or account id")
    password: Optional[str] = Field(None, description="Provider password/secret")
    pat: Optional[str] = Field(None, description="Personal access token")
    api_key: Optional[str] = Field(None, description="Provider API key")
    endpoint: Optional[str] = Field(None, description="Endpoint URL or host")
    proxy_url: Optional[str] = Field(None, description="Full proxy URL")
    notes: Optional[str] = Field(None, description="Operational notes")

    class Config:
        json_schema_extra = {
            "example": {
                "username": "acct_123456",
                "pat": "ptk_live_xxx",
                "endpoint": "us-proxy.decodo.com:10000",
                "notes": "Residential pool",
            }
        }


class SecretResponse(BaseModel):
    """Response containing secret metadata (never includes actual value)."""

    name: str
    type: str
    status: str  # stored, missing, expires_soon
    last_updated: datetime
    environment: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "name": "OPENAI_API_KEY",
                "type": "api_key",
                "status": "stored",
                "last_updated": "2026-04-11T12:00:00Z",
                "environment": "production",
            }
        }


class ListSecretsResponse(BaseModel):
    """Response with list of secret names."""

    secrets: List[str]
    count: int


class SecretMetadataResponse(BaseModel):
    """Response with secret metadata (no values)."""

    name: str
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None
    current_version: Optional[int] = None
    versions: Optional[List[Dict[str, Any]]] = None


class TestSecretRequest(BaseModel):
    """Request to validate a secret."""

    service: str = Field(..., description="Service name (openai, gemini, shodan, etc.)")
    value: str = Field(..., description="Secret value to test")

    class Config:
        json_schema_extra = {"example": {"service": "openai", "value": "sk-..."}}


class TestSecretResponse(BaseModel):
    """Response from secret validation."""

    valid: bool
    message: str
    details: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {"valid": True, "message": "OpenAI API key is valid", "details": {}}
        }


class RotateSecretRequest(BaseModel):
    """Request to rotate a secret."""

    new_value: str = Field(..., description="New secret value")


class RotateSecretResponse(BaseModel):
    """Response from secret rotation."""

    success: bool
    message: str
    new_version: Optional[int] = None


class SyncSecretsResponse(BaseModel):
    """Response from syncing secrets to environment."""

    success: bool
    synced_count: int
    message: str


class VaultHealthResponse(BaseModel):
    """Response from Vault health check."""

    connected: bool
    status: str  # ready, sealed, standby, etc.
    version: Optional[str] = None
    sealed: Optional[bool] = None
    initialized: Optional[bool] = None
    standby: Optional[bool] = None
    cluster_name: Optional[str] = None


class VaultErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    code: int
    details: Optional[Dict[str, Any]] = None


class AuditLogEntry(BaseModel):
    """Single audit log entry."""

    timestamp: datetime
    action: str
    secret: str
    user: Optional[str] = None
    ip_address: Optional[str] = None
    auth_method: Optional[str] = None


class AuditLogResponse(BaseModel):
    """Response containing audit log entries."""

    entries: List[AuditLogEntry]
    total: int
