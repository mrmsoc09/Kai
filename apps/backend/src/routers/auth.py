from __future__ import annotations

import os
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from ..core.auth import (
    User,
    access_expiry_minutes,
    get_current_user,
    issue_dev_access_token,
)
from ..core.csrf import csrf_manager

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    token: str


SESSION_COOKIE_NAME = "session_id"
CSRF_COOKIE_TTL_SECONDS = 60 * 60  # align with default CSRF token expiry window


@router.post("/login")
def login(req: LoginRequest):
    access_token = issue_dev_access_token(req.token)
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


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user.model_dump()
