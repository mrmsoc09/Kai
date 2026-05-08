"""
CSRF Protection Middleware
Validates CSRF tokens on state-changing requests (POST, PUT, DELETE, PATCH).
"""

from __future__ import annotations

import os
from urllib.parse import urlparse

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..config.csrf_policy import csrf_policy_registry
from ..core.csrf import (
    CSRF_EXEMPT_ENDPOINTS,
    CSRF_EXEMPT_METHODS,
    csrf_challenge_manager,
    csrf_manager,
    csrf_nonce_manager,
)


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection middleware using token validation.

    Validates X-CSRF-Token header on state-changing requests.
    Skips validation for exempt methods (GET, HEAD, etc.) and endpoints.
    """

    def __init__(self, app):
        super().__init__(app)
        trusted = os.getenv("CSRF_TRUSTED_ORIGINS") or os.getenv("CORS_ALLOWED_ORIGINS", "")
        self._trusted_origins = {
            origin.strip()
            for origin in trusted.split(",")
            if origin.strip()
        }
        self._require_origin_for_cookie = (
            os.getenv("CSRF_REQUIRE_ORIGIN_FOR_COOKIE", "true").strip().lower() in {"1", "true", "yes", "on"}
        )

    @staticmethod
    def _is_browser_request(request: Request) -> bool:
        return bool(
            request.headers.get("Origin")
            or request.headers.get("Referer")
            or request.headers.get("Sec-Fetch-Site")
        )

    def _validate_browser_origin(self, request: Request) -> tuple[bool, str]:
        """
        Validate Origin/Referer against trusted origins for cookie-authenticated
        browser requests.
        """
        origin = request.headers.get("Origin")
        referer = request.headers.get("Referer")

        if origin:
            if origin in self._trusted_origins:
                return True, ""
            return False, "invalid_origin"

        if referer:
            parsed = urlparse(referer)
            if parsed.scheme and parsed.netloc:
                referer_origin = f"{parsed.scheme}://{parsed.netloc}"
                if referer_origin in self._trusted_origins:
                    return True, ""
            return False, "invalid_referer"

        if self._require_origin_for_cookie:
            return False, "missing_origin_header"
        return True, ""

    async def dispatch(self, request: Request, call_next):
        """
        Process request through CSRF validation.

        Args:
            request: The incoming request
            call_next: Next middleware/handler to call

        Returns:
            Response or 403 if CSRF validation fails
        """

        # Skip CSRF check for GET, HEAD, OPTIONS, TRACE
        if request.method in CSRF_EXEMPT_METHODS:
            return await call_next(request)

        # Skip CSRF check for exempt endpoints
        if any(request.url.path.startswith(path) for path in CSRF_EXEMPT_ENDPOINTS):
            return await call_next(request)

        policy = csrf_policy_registry.resolve(request.url.path, request.method)
        request.state.csrf_policy = policy

        session_id = request.cookies.get("session_id")
        auth_cookie = request.cookies.get("k1_token")

        has_cookie_auth = bool(session_id or auth_cookie)
        auth = request.headers.get("Authorization", "")
        has_bearer = auth.startswith("Bearer ")

        # Explicit Bearer token with no auth cookies: treat as API client flow.
        if has_bearer and not has_cookie_auth:
            return await call_next(request)

        # CSRF mitigation applies only to cookie-authenticated state-changing requests.
        if not has_cookie_auth:
            return await call_next(request)

        if policy.require_origin_check:
            valid_origin, error_code = self._validate_browser_origin(request)
            if not valid_origin:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Origin/Referer validation failed",
                        "code": error_code,
                    },
                )

        if not session_id:
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "Session cookie is required for CSRF validation",
                    "code": "missing_session_cookie",
                },
            )

        csrf_token = request.headers.get("X-CSRF-Token")
        if not csrf_token:
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "CSRF token missing",
                    "code": "missing_csrf_token",
                },
            )

        if not csrf_manager.validate_token(session_id, csrf_token):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "CSRF token invalid or expired",
                    "code": "invalid_csrf_token",
                },
            )

        if policy.require_challenge and self._is_browser_request(request):
            challenge = request.headers.get("X-CSRF-Challenge")
            if not challenge:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "CSRF challenge token missing",
                        "code": "missing_csrf_challenge",
                    },
                )
            if not csrf_challenge_manager.validate_challenge(
                session_id=session_id,
                method=request.method,
                path=request.url.path,
                token=challenge,
            ):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "CSRF challenge token invalid or expired",
                        "code": "invalid_csrf_challenge",
                    },
                )

        if policy.require_nonce:
            nonce = request.headers.get("X-CSRF-Nonce")
            if not nonce:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "CSRF nonce missing for high-risk endpoint",
                        "code": "missing_csrf_nonce",
                    },
                )
            if not csrf_nonce_manager.validate_nonce(
                session_id=session_id,
                method=request.method,
                path=request.url.path,
                nonce=nonce,
            ):
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "CSRF nonce invalid or expired",
                        "code": "invalid_csrf_nonce",
                    },
                )

        # Token is valid, proceed
        response = await call_next(request)
        return response
