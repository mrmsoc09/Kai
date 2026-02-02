"""
Rate Limiting Middleware
Enforces rate limits on API endpoints to prevent abuse and DOS attacks.
"""

from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..core.rate_limiter import rate_limiter, get_rate_limit_for_endpoint


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiting middleware using sliding window algorithm.

    Tracks requests by IP address and enforces per-endpoint limits.
    Returns 429 (Too Many Requests) when limit is exceeded.
    """

    # Endpoints that don't require rate limiting
    EXEMPT_PATHS = [
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
    ]

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

        # Get client IP address
        client_ip = request.client.host if request.client else "unknown"

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

        # Get remaining requests (need to check again as request was made)
        remaining = max_requests - len(rate_limiter.requests.get(rate_limit_key, []))
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))

        reset_time = rate_limiter.get_reset_time(rate_limit_key, window_seconds)
        response.headers["X-RateLimit-Reset"] = str(int(reset_time) + 1)

        return response
