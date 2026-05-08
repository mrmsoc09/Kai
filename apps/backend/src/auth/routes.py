from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from apps.backend.src.core.hil_db import get_db
from apps.backend.src.auth.models import User, Tenant, APIToken, UserRole
from apps.backend.src.auth.schemas import (
    UserRead, UserCreate, Token, TokenData,
    TenantRead, TenantCreate,
    APITokenCreate, APITokenRead, APITokenResponse,
    DevCertLoginRequest, DevCertTokenResponse,
    InitialPasswordSetupRequest,
)
from apps.backend.src.auth.utils import (
    verify_password, hash_password, create_access_token,
    generate_api_token, hash_api_token,
    ACCESS_TOKEN_EXPIRE_MINUTES
)
from apps.backend.src.core.auth import issue_dev_cert_access_token
from apps.backend.src.auth.dependencies import (
    get_current_active_user, get_current_tenant,
    CurrentUser,
    require_roles
)

router = APIRouter(prefix="/auth", tags=["authentication"])
AUTH_COOKIE_NAME = "k1_token"

# -- Tenant Management --------------------------------------------------------

@router.post("/tenants", response_model=TenantRead, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    tenant_create: TenantCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.ADMIN))
):
    """Create a new tenant (Admin only)."""
    # Ensure tenant name is unique
    result = await db.execute(select(Tenant).where(Tenant.name == tenant_create.name))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tenant name already registered")
    
    new_tenant = Tenant(**tenant_create.model_dump())
    db.add(new_tenant)
    await db.commit()
    await db.refresh(new_tenant)
    return new_tenant

@router.get("/tenants/{tenant_id}", response_model=TenantRead)
async def get_tenant(
    tenant_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.ADMIN))
):
    """Get tenant details (Admin only)."""
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


# -- User Management ----------------------------------------------------------

@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    user_create: UserCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_roles(UserRole.ADMIN))
):
    """Register a new user (Admin only)."""
    # Ensure username is unique within tenant
    result = await db.execute(select(User).where(
        User.username == user_create.username,
        User.tenant_id == user_create.tenant_id
    ))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already registered in this tenant")
    
    hashed_password = hash_password(user_create.password)
    new_user = User(**user_create.model_dump(exclude={"password"}), hashed_password=hashed_password)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.get("/users/me", response_model=UserRead)
async def read_users_me(current_user: Annotated[CurrentUser, Depends(get_current_active_user)]):
    """Get details of the current authenticated user."""
    return UserRead(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_superuser=current_user.is_superuser,
        must_change_password=current_user.must_change_password,
        role=current_user.role,
        tenant_id=current_user.tenant_id,
        created_at=current_user.created_at,
        updated_at=current_user.updated_at
    )


# -- JWT Authentication -------------------------------------------------------

@router.post("/token", response_model=Token)
async def login_for_access_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    """
    Authenticate user and return JWT access token.
    Requires username, password (and tenant_id in form or path, for multi-tenant).
    For simplicity, assuming tenant_id is part of username or a default tenant.
    Here, we'll assume a default tenant for initial setup, or later pass tenant_id.
    """
    # For MVP, assume a default tenant or derive from username.
    # In a real multi-tenant app, tenant_id would be part of login form or subdomain.
    # Let's use a dummy tenant_id for now for initial user creation.
    
    # First, find user by username.
    # In a multi-tenant system, this needs to be user + tenant.
    # For now, let's assume `username@tenant_name` or similar, or a default tenant.
    
    # For current setup, let's allow "admin" for any tenant or "k1-admin" from initial setup
    # A more robust system would involve tenant selection at login.
    form = await request.form()
    username = str(form.get("username") or "").strip()
    password = form.get("password")
    password_text = "" if password is None else str(password)

    if not username:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="username_required",
        )

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()

    if not user or not verify_password(password_text, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "tid": str(user.tenant_id),
            "rol": user.role.value
        },
        expires_delta=access_token_expires
    )
    secure_cookie = os.getenv("ENVIRONMENT", "development").lower() == "production"
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        max_age=int(access_token_expires.total_seconds()),
        path="/",
    )
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_at=datetime.now(timezone.utc) + access_token_expires,
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
        password_setup_required=user.must_change_password,
    )


@router.post("/token/dev-cert", response_model=DevCertTokenResponse)
async def login_with_dev_cert(
    payload: DevCertLoginRequest,
    response: Response,
):
    """
    Dev-only login using a certificate signed by the local development CA.
    This route is intentionally non-production and requires K1_DEV_CERT_AUTH_ENABLED=true.
    """
    try:
        access_token = issue_dev_cert_access_token(payload.client_certificate_pem)
    except HTTPException as exc:
        raise exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    secure_cookie = os.getenv("ENVIRONMENT", "development").lower() == "production"
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=secure_cookie,
        samesite="lax",
        max_age=int(access_token_expires.total_seconds()),
        path="/",
    )
    return DevCertTokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_at=datetime.now(timezone.utc) + access_token_expires,
        password_setup_required=False,
    )


@router.post("/users/set-initial-password")
async def set_initial_password(
    payload: InitialPasswordSetupRequest,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Set the first password for users flagged with must_change_password=true.
    This is intended for first-login bootstrap accounts such as k1-admin.
    """
    if not current_user.must_change_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="initial_password_setup_not_required")

    new_password = payload.new_password.strip()
    if len(new_password) < 8:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="password_too_short")

    result = await db.execute(select(User).where(
        User.id == current_user.id,
        User.tenant_id == current_user.tenant_id,
    ))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user_not_found")

    if verify_password(new_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="new_password_must_differ")

    user.hashed_password = hash_password(new_password)
    user.must_change_password = False
    await db.commit()

    return {"ok": True}

# -- API Token Management -----------------------------------------------------

@router.post("/api-tokens", response_model=APITokenResponse, status_code=status.HTTP_201_CREATED)
async def create_api_token(
    payload: APITokenCreate,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new API token for the current user."""
    raw_token = generate_api_token()
    hashed_token = hash_api_token(raw_token)
    
    expires_at: datetime | None = None
    if payload.expires_in_hours:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=payload.expires_in_hours)
    
    new_api_token = APIToken(
        user_id=current_user.id,
        tenant_id=current_user.tenant_id,
        token_hash=hashed_token,
        name=payload.name,
        expires_at=expires_at
    )
    db.add(new_api_token)
    await db.commit()
    await db.refresh(new_api_token)
    
    return APITokenResponse(
        **APITokenRead.model_validate(new_api_token).model_dump(),
        token=raw_token # Return the raw token ONLY ON CREATION
    )

@router.get("/api-tokens", response_model=list[APITokenRead])
async def list_api_tokens(
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """List all API tokens for the current user."""
    result = await db.execute(select(APIToken).where(
        APIToken.user_id == current_user.id,
        APIToken.tenant_id == current_user.tenant_id
    ))
    return list(result.scalars().all())

@router.delete("/api-tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_token(
    token_id: UUID,
    current_user: CurrentUser = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke an API token for the current user."""
    result = await db.execute(select(APIToken).where(
        APIToken.id == token_id,
        APIToken.user_id == current_user.id,
        APIToken.tenant_id == current_user.tenant_id
    ))
    api_token = result.scalar_one_or_none()
    
    if not api_token:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API token not found")
    
    await db.delete(api_token)
    await db.commit()
    return {"message": "API token revoked"}
