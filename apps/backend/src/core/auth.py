from __future__ import annotations

from typing import List, Optional
import os
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

security = HTTPBearer(auto_error=True)

class User(BaseModel):
    id: str
    roles: List[str] = []

ROLE_VIEWER = 'viewer'
ROLE_OPERATOR = 'operator'
ROLE_ANALYST = 'analyst'
ROLE_ADMIN = 'admin'

DEV_TOKEN_ENV = 'K1_DEV_TOKEN'


def _expected_token() -> Optional[str]:
    # Do not hardcode. Expect provided via environment/.env at runtime.
    return os.getenv(DEV_TOKEN_ENV)


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(security)) -> User:
    token = creds.credentials or ''
    expected = _expected_token()
    if not expected:
        # Locked-down default if no dev token configured.
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail='auth_not_configured')
    if token != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid_token')
    # In dev mode, grant admin; production should derive from token/JWT/IdP
    return User(id='dev', roles=[ROLE_ADMIN, ROLE_ANALYST, ROLE_OPERATOR, ROLE_VIEWER])


def require_roles(*required: str):
    def _dep(user: User = Depends(get_current_user)) -> User:
        if not required:
            return user
        if not any(r in user.roles for r in required):
            raise HTTPException(status_code=403, detail='forbidden')
        return user
    return _dep
