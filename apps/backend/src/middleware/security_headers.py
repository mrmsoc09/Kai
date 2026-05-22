"""
Security Headers Middleware
Adds important security headers to all responses.
"""

import os

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Add security-related HTTP headers to responses.

    Headers added:
    - X-Frame-Options: Prevent clickjacking attacks
    - X-Content-Type-Options: Prevent MIME type sniffing
    - X-XSS-Protection: Enable XSS protection
    - Strict-Transport-Security: Enforce HTTPS
    - Content-Security-Policy: Restrict resource loading
    """

    def __init__(self, app):
        super().__init__(app)
        self._csp_policy = os.getenv(
            "CONTENT_SECURITY_POLICY",
            (
                "default-src 'self'; "
                "script-src 'self'; "
                "style-src 'self'; "
                "img-src 'self' data: https:; "
                "font-src 'self' data:; "
                "connect-src 'self' wss: https:; "
                "object-src 'none'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self'"
            ),
        )

    async def dispatch(self, request: Request, call_next):
        """
        Add security headers to response.

        Args:
            request: The incoming request
            call_next: Next middleware/handler to call

        Returns:
            Response with security headers added
        """
        response = await call_next(request)

        # Prevent clickjacking attacks
        # DENY: The page cannot be displayed in a frame, regardless of the site attempting to do so
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        # The browser should not attempt to interpret files as a different MIME type than what is specified
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Enable XSS protection
        # 1; mode=block: If XSS attack is detected, stop rendering the page
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Enforce HTTPS (in production)
        # max-age=31536000: HSTS valid for 1 year
        # includeSubDomains: Apply to all subdomains
        # preload: Allow inclusion in HSTS preload lists
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

        # Content Security Policy
        # Restrict what resources can be loaded
        response.headers["Content-Security-Policy"] = self._csp_policy

        # Referrer Policy
        # strict-no-referrer: Never send referrer information
        response.headers["Referrer-Policy"] = "strict-no-referrer"

        # Additional security headers
        response.headers["Permissions-Policy"] = (
            "geolocation=(), "
            "microphone=(), "
            "camera=(), "
            "payment=(), "
            "usb=(), "
            "magnetometer=(), "
            "gyroscope=(), "
            "accelerometer=()"
        )

        return response
