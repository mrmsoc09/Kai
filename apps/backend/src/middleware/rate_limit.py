"""
Rate Limiting Middleware
Enforces rate limits on API endpoints to prevent abuse and DOS attacks.
"""

import ipaddress
import os

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..core.rate_limiter import rate_limiter, get_rate_limit_for_endpoint

# CIDRs of trusted reverse proxies that may set X-Forwarded-For.
# Loaded from K1_TRUSTED_PROXY_CIDRS env (comma-separated), default to loopback.
_TRUSTED_PROXY_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
_raw = os.getenv("K1_TRUSTED_PROXY_CIDRS", "127.0.0.1/32,::1/128")
for _cidr in _raw.split(","):
    try:
        _TRUSTED_PROXY_NETWORKS.append(ipaddress.ip_network(_cidr.strip(), strict=False))
    except ValueError:
        pass


def _is_trusted_proxy(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return any(addr in net for net in _TRUSTED_PROXY_NETWORKS)
    except ValueError:
        return False


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using sliding window algorithm.

    Tracks requests by real client IP and enforces per-endpoint limits.
    Returns 429 (Too Many Requests) when limit is exceeded.
    X-Forwarded-For is only trusted when the connecting IP is a known proxy.
    """

    # Endpoints that don't require rate limiting
    EXEMPT_PATHS = [
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
    ]

    def _get_client_ip(self, request: Request) -> str:
        """Return the real client IP, validating X-Forwarded-For against trusted proxies."""
        direct_ip = request.client.host if request.client else "unknown"
        if _is_trusted_proxy(direct_ip):
            xff = request.headers.get("X-Forwarded-For", "")
            if xff:
                # Take the leftmost (originating) address
                candidate = xff.split(",")[0].strip()
                try:
                    ipaddress.ip_address(candidate)
                    return candidate
                except ValueError:
                    pass
        return direct_ip

    async def dispatch(self, request: Request, call_next):
        """
        Process request through rate limiter.

        Args:
            request: The incoming request
            call_next: Next middleware/handler to call

        Returns:
            Response or 429 if rate limit exceeded
        """

        # Check if path is exempt
        if any(request.url.path.startswith(path) for path in self.EXEMPT_PATHS):
            return await call_next(request)

        # Get validated client IP address
        client_ip = self._get_client_ip(request)

        # Create rate limit key: "{IP}:{endpoint}"
        rate_limit_key = f"{client_ip}:{request.url.path}"

        # Get rate limit for this endpoint
        max_requests, window_seconds = get_rate_limit_for_endpoint(request.url.path)

        # Check rate limit
        if not rate_limiter.is_allowed(rate_limit_key, max_requests, window_seconds):
            # Calculate reset time
            reset_time = rate_limiter.get_reset_time(rate_limit_key, window_seconds)

            # Return 429 Too Many Requests
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "retry_after": int(reset_time) + 1,
                },
                headers={
                    "Retry-After": str(int(reset_time) + 1),
                    "X-RateLimit-Limit": str(max_requests),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(reset_time) + 1),
                },
            )

        # Request is allowed, proceed
        response = await call_next(request)

        # Add rate limit headers to response
        response.headers["X-RateLimit-Limit"] = str(max_requests)

        # Get remaining requests after the current request was recorded
        remaining = max_requests - rate_limiter.get_count(rate_limit_key, window_seconds)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))

        reset_time = rate_limiter.get_reset_time(rate_limit_key, window_seconds)
        response.headers["X-RateLimit-Reset"] = str(int(reset_time) + 1)

        return response
