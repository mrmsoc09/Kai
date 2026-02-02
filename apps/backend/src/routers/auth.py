from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from ..core.auth import get_current_user, User

router = APIRouter(prefix='/auth', tags=['auth'])

class LoginRequest(BaseModel):
    token: str

@router.post('/login')
def login(req: LoginRequest):
    # Frontend should POST a token provided by human; backend validates against env var.
    from ..core.auth import _expected_token
    expected = _expected_token()
    if not expected:
        raise HTTPException(status_code=503, detail='auth_not_configured')
    if req.token != expected:
        raise HTTPException(status_code=401, detail='invalid_token')
    # Echo minimal session model (frontend stores in memory)
    return { 'ok': True }

@router.get('/me')
def me(user: User = Depends(get_current_user)):
    return user.dict()
