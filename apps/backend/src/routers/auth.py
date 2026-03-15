from __future__ import annotations

import os
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from ..core.auth import (
    User,
    access_expiry_minutes,
    create_access_token,
    extract_jti_and_exp,
    get_current_user,
    issue_dev_access_token,
)
from ..core.csrf import csrf_manager
from ..core.token_blocklist import revoke_token

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    token: str


SESSION_COOKIE_NAME = "session_id"
AUTH_COOKIE_NAME = "k1_token"
CSRF_COOKIE_TTL_SECONDS = 60 * 60  # align with default CSRF token expiry window


@router.post("/login")
def login(req: LoginRequest, response: Response):
    access_token = issue_dev_access_token(req.token)
    
    # Set JWT as HttpOnly; Secure; SameSite=Strict cookie
    # Secure=True in production, False in dev if no HTTPS
    secure = os.getenv("ENVIRONMENT", "development").lower() == "production"
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=access_token,
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=access_expiry_minutes() * 60,
        path="/",
    )
    
    return {
        "ok": True,
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in_minutes": access_expiry_minutes(),
    }


@router.get("/csrf-token")
def get_csrf_token(request: Request, response: Response):
    session_id = request.cookies.get(SESSION_COOKIE_NAME) or uuid4().hex
    csrf_token = csrf_manager.generate_token(session_id)

    secure = os.getenv("COOKIE_SECURE", "false").lower() == "true"
    same_site = os.getenv("COOKIE_SAMESITE", "lax").lower()
    if same_site not in {"lax", "strict", "none"}:
        same_site = "lax"

    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        secure=secure,
        samesite=same_site,  # type: ignore[arg-type]
        max_age=CSRF_COOKIE_TTL_SECONDS,
        path="/",
    )
    return {"csrf_token": csrf_token}


@router.post("/logout")
def logout(request: Request, response: Response, user: User = Depends(get_current_user)):
    """Revoke the current access token and clear the auth cookie."""
    # Revoke via header or cookie
    token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header.removeprefix("Bearer ").strip()
    else:
        token = request.cookies.get(AUTH_COOKIE_NAME)
        
    if token:
        jti, exp = extract_jti_and_exp(token)
        if jti:
            revoke_token(jti, exp)
            
    response.delete_cookie(AUTH_COOKIE_NAME)
    return {"ok": True}


@router.post("/refresh")
def refresh(response: Response, user: User = Depends(get_current_user)):
    """Issue a new access token and update the auth cookie."""
    new_token = create_access_token(subject=user.id, roles=user.roles)
    
    secure = os.getenv("ENVIRONMENT", "development").lower() == "production"
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=new_token,
        httponly=True,
        secure=secure,
        samesite="strict",
        max_age=access_expiry_minutes() * 60,
        path="/",
    )
    
    return {
        "ok": True,
        "access_token": new_token,
        "token_type": "bearer",
        "expires_in_minutes": access_expiry_minutes(),
    }


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user.model_dump()
