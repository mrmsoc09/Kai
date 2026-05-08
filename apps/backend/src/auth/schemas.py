from __future__ import annotations
from datetime import datetime
from uuid import UUID
from typing import Optional
from pydantic import BaseModel, EmailStr, Field

from apps.backend.src.auth.models import UserRole

class TenantCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=255)
    config_json: dict = Field(default_factory=dict)

class TenantRead(BaseModel):
    id: UUID
    name: str
    is_active: bool
    config_json: dict
    created_at: datetime
    updated_at: datetime

class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=255)
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    role: UserRole = UserRole.VIEWER
    tenant_id: UUID

class UserRead(BaseModel):
    id: UUID
    username: str
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: bool
    is_superuser: bool
    must_change_password: bool
    role: UserRole
    tenant_id: UUID
    created_at: datetime
    updated_at: datetime

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    user_id: UUID
    tenant_id: UUID
    role: UserRole
    password_setup_required: bool = False


class DevCertLoginRequest(BaseModel):
    client_certificate_pem: str


class DevCertTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    password_setup_required: bool = False


class InitialPasswordSetupRequest(BaseModel):
    new_password: str = Field(..., min_length=8, max_length=255)

class TokenData(BaseModel):
    user_id: UUID
    tenant_id: UUID
    role: UserRole

class APITokenCreate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    expires_in_hours: Optional[int] = Field(None, ge=1, le=87600) # 10 years max

class APITokenRead(BaseModel):
    id: UUID
    name: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool
    last_used_at: Optional[datetime] = None
    user_id: UUID
    tenant_id: UUID
    # token_hash is NOT exposed

class APITokenResponse(APITokenRead):
    token: str # This is only returned on creation

class SystemStatusResponse(BaseModel):
    status: str
    message: str
    tenant_id: UUID
