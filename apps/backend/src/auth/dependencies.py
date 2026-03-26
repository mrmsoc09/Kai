"""
Auth Dependencies — FastAPI dependency injection for authentication + RBAC.

Strategy: try API Key header first (X-API-Key), then Bearer JWT.
Both paths resolve to a CurrentUser object with tenant_id and role.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jwt.exceptions import PyJWTError as JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from apps.backend.src.core.hil_db import get_db
from apps.backend.src.auth.models import APIToken, Tenant, User, UserRole
from apps.backend.src.auth.schemas import TokenData
from apps.backend.src.auth.utils import decode_access_token, hash_api_token

# ---------------------------------------------------------------------------
# Security schemes
# ---------------------------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token", auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

# ---------------------------------------------------------------------------
# Role hierarchy (ADMIN > ANALYST > OPERATOR > VIEWER)
# ---------------------------------------------------------------------------

_ROLE_RANK: dict[str, int] = {
    UserRole.VIEWER: 0,
    UserRole.OPERATOR: 1,
    UserRole.ANALYST: 2,
    UserRole.ADMIN: 3,
}


def _role_satisfies(user_role: str, required_role: str) -> bool:
    """Return True if user_role is >= required_role in the hierarchy."""
    return _ROLE_RANK.get(user_role, -1) >= _ROLE_RANK.get(required_role, 0)


# ---------------------------------------------------------------------------
# CurrentUser — lightweight representation; avoids inheriting SQLAlchemy model
# ---------------------------------------------------------------------------

class CurrentUser:
    """Authenticated user resolved from JWT or API Key."""

    def __init__(
        self,
        id: UUID,
        tenant_id: UUID,
        username: str,
        email: str | None,
        full_name: str | None,
        is_active: bool,
        is_superuser: bool,
        must_change_password: bool,
        role: str,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        self.id = id
        self.tenant_id = tenant_id
        self.username = username
        self.email = email
        self.full_name = full_name
        self.is_active = is_active
        self.is_superuser = is_superuser
        self.must_change_password = must_change_password
        self.role = role
        self.created_at = created_at
        self.updated_at = updated_at


def _user_to_current(user: User) -> CurrentUser:
    role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
    return CurrentUser(
        id=user.id,
        tenant_id=user.tenant_id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        is_superuser=user.is_superuser,
        must_change_password=user.must_change_password,
        role=role_val,
        created_at=getattr(user, "created_at", None),
        updated_at=getattr(user, "updated_at", None),
    )


# ---------------------------------------------------------------------------
# Core resolution logic
# ---------------------------------------------------------------------------

async def _resolve_from_api_key(api_key: str, db: AsyncSession) -> CurrentUser | None:
    """Resolve CurrentUser from X-API-Key header. Returns None if invalid."""
    hashed = hash_api_token(api_key)
    result = await db.execute(
        select(APIToken).where(
            APIToken.token_hash == hashed,
            APIToken.is_active == True,  # noqa: E712
        )
    )
    token_obj = result.scalar_one_or_none()
    if not token_obj:
        return None
    # Check expiry
    if token_obj.expires_at and token_obj.expires_at < datetime.now(timezone.utc):
        return None
    # Update last_used_at
    token_obj.last_used_at = datetime.now(timezone.utc)
    await db.commit()
    # Load user
    result = await db.execute(
        select(User).where(
            User.id == token_obj.user_id,
            User.tenant_id == token_obj.tenant_id,
            User.is_active == True,  # noqa: E712
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        return None
    return _user_to_current(user)


async def _resolve_from_jwt(token: str, db: AsyncSession) -> CurrentUser | None:
    """Resolve CurrentUser from Bearer JWT. Returns None if invalid."""
    try:
        token_data: TokenData = decode_access_token(token)
    except (JWTError, HTTPException):
        return None
    result = await db.execute(
        select(User).where(
            User.id == token_data.user_id,
            User.tenant_id == token_data.tenant_id,
            User.is_active == True,  # noqa: E712
        )
    )
    user = result.scalar_one_or_none()
    if not user:
        return None
    return _user_to_current(user)


# ---------------------------------------------------------------------------
# Public dependencies
# ---------------------------------------------------------------------------

async def get_current_active_user(
    request: Request,
    api_key: Annotated[str | None, Depends(api_key_scheme)] = None,
    jwt_token: Annotated[str | None, Depends(oauth2_scheme)] = None,
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    """
    Resolve the current authenticated user from API Key or JWT Bearer token.
    API Key takes priority when both are present.
    Raises HTTP 401 if neither is valid.
    """
    # 1. Try API Key
    if api_key:
        user = await _resolve_from_api_key(api_key, db)
        if user:
            _enforce_password_setup_gate(user, request)
            return user

    # 2. Try JWT Bearer
    if jwt_token:
        user = await _resolve_from_jwt(jwt_token, db)
        if user:
            _enforce_password_setup_gate(user, request)
            return user

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Provide a valid Bearer token or X-API-Key.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _enforce_password_setup_gate(user: CurrentUser, request: Request) -> None:
    """Restrict authenticated access until initial password setup is completed."""
    if not user.must_change_password:
        return

    allowed_paths = {
        "/auth/token",
        "/auth/users/set-initial-password",
    }
    request_path = request.url.path.rstrip("/") or "/"
    if request_path in allowed_paths:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="password_setup_required",
    )


async def get_current_tenant(
    current_user: Annotated[CurrentUser, Depends(get_current_active_user)],
    db: AsyncSession = Depends(get_db),
) -> Tenant:
    """Dependency to retrieve the current user's Tenant record."""
    result = await db.execute(select(Tenant).where(Tenant.id == current_user.tenant_id))
    tenant = result.scalar_one_or_none()
    if not tenant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
    return tenant


def require_roles(*required_roles: str):
    """
    RBAC dependency factory. Uses role hierarchy: ADMIN > ANALYST > OPERATOR > VIEWER.
    Pass one or more roles; user needs to satisfy AT LEAST ONE.
    """
    def _checker(current_user: Annotated[CurrentUser, Depends(get_current_active_user)]) -> CurrentUser:
        if not required_roles:
            return current_user
        for role in required_roles:
            if _role_satisfies(current_user.role, role):
                return current_user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Insufficient privileges. Required one of: "
                f"{[r for r in required_roles]}, got: {current_user.role}"
            ),
        )
    return _checker


def validate_tenant_id_param(tenant_id: UUID, current_user: Annotated[CurrentUser, Depends(get_current_active_user)]) -> UUID:
    """Ensure the tenant_id path parameter matches the authenticated user's tenant."""
    if current_user.tenant_id != tenant_id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access denied")
    return tenant_id
