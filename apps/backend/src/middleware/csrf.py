"""
CSRF Protection Middleware
Validates CSRF tokens on state-changing requests (POST, PUT, DELETE, PATCH).
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..core.csrf import csrf_manager, CSRF_EXEMPT_ENDPOINTS, CSRF_EXEMPT_METHODS


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection middleware using token validation.

    Validates X-CSRF-Token header on state-changing requests.
    Skips validation for exempt methods (GET, HEAD, etc.) and endpoints.
    """

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

        # Get CSRF token from request headers
        csrf_token = request.headers.get("X-CSRF-Token")

        if not csrf_token:
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "CSRF token missing",
                    "code": "missing_csrf_token",
                },
            )

        # Get session ID from cookies or headers
        session_id = request.cookies.get("session_id")

        if not session_id:
            # Try to get from Authorization header or create temp one
            session_id = request.headers.get("Authorization", "").split(" ")[-1]

        if not session_id:
            session_id = "anonymous"

        # Validate CSRF token
        if not csrf_manager.validate_token(session_id, csrf_token):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "CSRF token invalid or expired",
                    "code": "invalid_csrf_token",
                },
            )

        # Token is valid, proceed
        response = await call_next(request)
        return response
