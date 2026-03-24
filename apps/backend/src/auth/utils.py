from __future__ import annotations
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from passlib.context import CryptContext
from jose import JWTError, jwt

from apps.backend.src.auth.schemas import TokenData
from apps.backend.src.auth.models import UserRole

# -- Configuration Constants --------------------------------------------------
# These would typically be loaded from environment variables or a config file
# In a real app, ensure these are SECURELY managed (e.g., Docker secrets, Vault)

ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
API_TOKEN_HASH_ALGORITHM = os.getenv("API_TOKEN_HASH_ALGORITHM", "sha256")
_INSECURE_DEFAULT_SECRET = "super-secret-jwt-key"
_ALLOWED_JWT_ALGORITHMS = {"HS256", "HS384", "HS512"}

# Prefer PBKDF2 for portability across local environments where bcrypt backends
# may be missing or incompatible; keep bcrypt support for legacy hash verify.
pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")


def _is_non_production() -> bool:
    return os.getenv("ENVIRONMENT", "development").strip().lower() != "production"


def _allow_insecure_default_secret() -> bool:
    raw = os.getenv("K1_ALLOW_INSECURE_JWT_SECRET", "false").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _jwt_secret() -> str:
    secret = (os.getenv("JWT_SECRET_KEY") or os.getenv("K1_JWT_SECRET") or "").strip()
    if not secret:
        raise HTTPException(status_code=503, detail="jwt_secret_not_configured")
    if secret == _INSECURE_DEFAULT_SECRET and not (_is_non_production() and _allow_insecure_default_secret()):
        raise HTTPException(status_code=503, detail="jwt_secret_insecure_default")
    return secret


def _jwt_algorithm() -> str:
    algorithm = os.getenv("JWT_ALGORITHM", "HS256").strip().upper()
    if algorithm not in _ALLOWED_JWT_ALGORITHMS:
        raise HTTPException(status_code=503, detail="jwt_algorithm_not_allowed")
    return algorithm

# -- Password Hashing ---------------------------------------------------------

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

# -- JWT Token Management -----------------------------------------------------

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "iat": datetime.now(timezone.utc)})
    encoded_jwt = jwt.encode(to_encode, _jwt_secret(), algorithm=_jwt_algorithm())
    return encoded_jwt

def decode_access_token(token: str) -> TokenData:
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[_jwt_algorithm()])
        user_id: str = payload.get("sub")
        tenant_id: str = payload.get("tid")
        role: str = payload.get("rol")
        if user_id is None or tenant_id is None or role is None:
            raise JWTError
        return TokenData(user_id=UUID(user_id), tenant_id=UUID(tenant_id), role=UserRole(role))
    except HTTPException:
        raise
    except (JWTError, ValueError):
        raise HTTPException(status_code=401, detail="Could not validate credentials")

# -- API Token Hashing (for storing in DB) ------------------------------------

import hashlib

def hash_api_token(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()

def generate_api_token() -> str:
    return os.urandom(32).hex()

# -- RBAC Utility -------------------------------------------------------------

def has_role(required_role: UserRole, user_role: UserRole) -> bool:
    """Check if user's role meets or exceeds the required role."""
    role_hierarchy = {
        UserRole.VIEWER: 0,
        UserRole.OPERATOR: 1,
        UserRole.ANALYST: 2, # Assuming ANALYST is a higher role than OPERATOR
        UserRole.ADMIN: 3,
    }
    return role_hierarchy.get(user_role, -1) >= role_hierarchy.get(required_role, 0)
