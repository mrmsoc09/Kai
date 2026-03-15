from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import List, Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from .token_blocklist import is_revoked

try:
    from jose import JWTError, jwt  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - environment/bootstrap safeguard
    class JWTError(Exception):
        """Fallback JWT error when python-jose is unavailable."""

    jwt = None  # type: ignore[assignment]

security = HTTPBearer(auto_error=True)


class User(BaseModel):
    id: str
    roles: List[str] = Field(default_factory=list)


ROLE_VIEWER = "viewer"
ROLE_OPERATOR = "operator"
ROLE_ANALYST = "analyst"
ROLE_ADMIN = "admin"
ALLOWED_ROLES = {ROLE_VIEWER, ROLE_OPERATOR, ROLE_ANALYST, ROLE_ADMIN}

DEV_TOKEN_ENV = "K1_DEV_TOKEN"
JWT_SECRET_ENV = "JWT_SECRET_KEY"
JWT_FALLBACK_SECRET_ENV = "K1_JWT_SECRET"
JWT_ALGORITHM_ENV = "JWT_ALGORITHM"
JWT_ACCESS_EXP_MIN_ENV = "K1_ACCESS_TOKEN_EXPIRY_MINUTES"


class AuthConfigError(RuntimeError):
    pass


def _require_jose() -> None:
    if jwt is None:
        raise AuthConfigError("jwt_library_not_installed")


def _is_non_production() -> bool:
    return os.getenv("ENVIRONMENT", "development").lower() != "production"


def _expected_token() -> Optional[str]:
    return os.getenv(DEV_TOKEN_ENV)


def assert_bootstrap_auth_safe() -> None:
    """
    Call at application startup. Raises AuthConfigError if bootstrap auth is
    enabled in a production environment — prevents accidental production backdoor.
    """
    bootstrap_enabled = os.getenv("K1_ENABLE_BOOTSTRAP_AUTH", "false").lower() == "true"
    is_production = not _is_non_production()
    if bootstrap_enabled and is_production:
        raise AuthConfigError(
            "K1_ENABLE_BOOTSTRAP_AUTH=true is not permitted when ENVIRONMENT=production. "
            "Remove this flag before deploying."
        )


def _jwt_secret() -> str:
    secret = os.getenv(JWT_SECRET_ENV) or os.getenv(JWT_FALLBACK_SECRET_ENV)
    if not secret:
        raise AuthConfigError("jwt_secret_not_configured")
    return secret


def _jwt_algorithm() -> str:
    algorithm = os.getenv(JWT_ALGORITHM_ENV, "HS256")
    if algorithm not in {"HS256", "HS384", "HS512"}:
        raise AuthConfigError("jwt_algorithm_not_allowed")
    return algorithm


def _access_expiry_minutes() -> int:
    raw = os.getenv(JWT_ACCESS_EXP_MIN_ENV, "60")
    try:
        return max(1, int(raw))
    except ValueError:
        return 60


def access_expiry_minutes() -> int:
    return _access_expiry_minutes()


def _normalize_roles(roles: List[str]) -> List[str]:
    normalized: List[str] = []
    for role in roles:
        if role not in ALLOWED_ROLES:
            raise AuthConfigError("invalid_role")
        if role not in normalized:
            normalized.append(role)
    if not normalized:
        raise AuthConfigError("empty_roles")
    return normalized


def create_access_token(subject: str, roles: List[str], expires_delta: timedelta | None = None) -> str:
    _require_jose()
    now = datetime.now(timezone.utc)
    exp_delta = expires_delta or timedelta(minutes=_access_expiry_minutes())
    normalized_roles = _normalize_roles(roles)
    payload = {
        "sub": subject,
        "roles": normalized_roles,
        "jti": str(uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + exp_delta).timestamp()),
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=_jwt_algorithm())


def issue_dev_access_token(bootstrap_token: str) -> str:
    bootstrap_enabled = os.getenv("K1_ENABLE_BOOTSTRAP_AUTH", "false").lower() == "true"
    if not bootstrap_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not_found")
    expected = _expected_token()
    if not expected:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="auth_not_configured")
    if bootstrap_token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")

    try:
        return create_access_token(
            subject="dev",
            roles=[ROLE_ADMIN, ROLE_ANALYST, ROLE_OPERATOR, ROLE_VIEWER],
        )
    except AuthConfigError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="auth_not_configured")


def decode_access_token(token: str) -> User:
    try:
        _require_jose()
        payload = jwt.decode(token, _jwt_secret(), algorithms=[_jwt_algorithm()])
    except AuthConfigError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="auth_not_configured")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")

    subject = payload.get("sub")
    roles = payload.get("roles", [])
    jti = payload.get("jti")

    if not isinstance(subject, str) or not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token_subject")
    if not isinstance(roles, list) or any(not isinstance(role, str) for role in roles):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token_roles")

    if is_revoked(jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token_revoked")

    try:
        normalized_roles = _normalize_roles(roles)
    except AuthConfigError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token_roles")
    return User(id=subject, roles=normalized_roles)


def extract_jti_and_exp(token: str) -> tuple[Optional[str], int]:
    """
    Decode a token WITHOUT blocklist/expiry enforcement (for use in logout).
    Returns (jti, exp). Does not raise on expired tokens.
    """
    try:
        _require_jose()
    except AuthConfigError:
        return None, 0
    try:
        payload = jwt.decode(
            token,
            _jwt_secret(),
            algorithms=[_jwt_algorithm()],
            options={"verify_exp": False},
        )
        return payload.get("jti"), int(payload.get("exp", 0))
    except Exception:
        return None, 0


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> User:
    token = creds.credentials or ""
    return decode_access_token(token)


def require_roles(*required: str):
    def _dep(user: User = Depends(get_current_user)) -> User:
        if not required:
            return user
        if not any(role in user.roles for role in required):
            raise HTTPException(status_code=403, detail="forbidden")
        return user

    return _dep
