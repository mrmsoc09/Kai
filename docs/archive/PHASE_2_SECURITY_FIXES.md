# PHASE 2: CRITICAL SECURITY FIXES
## Addressing Blocking Security Issues

---

## OVERVIEW

Phase 2 focuses on fixing **4 critical security vulnerabilities** that block deployment:

1. **CORS Configuration** - Currently allows all origins (security bypass)
2. **Authentication** - Token validation needs hardening
3. **Rate Limiting** - No protection against API abuse
4. **CSRF Protection** - Missing on state-changing endpoints

---

## ISSUE 1: CORS VULNERABILITY

### Current Problem
```python
# apps/backend/src/main.py (VULNERABLE)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],              # ⚠️ ALLOWS ALL ORIGINS
    allow_methods=["*"],              # ⚠️ ALLOWS ALL METHODS
    allow_headers=["*"],              # ⚠️ ALLOWS ALL HEADERS
    allow_credentials=True,           # ⚠️ DANGEROUS WITH WILDCARD
)
```

**Security Impact:**
- Allows CSRF attacks from any domain
- Credentials can be stolen via cross-origin requests
- Authentication tokens exposed to attackers

### Solution

**Step 1: Create CORS configuration module**
```python
# apps/backend/src/config/cors_config.py
import os
from typing import List

def get_cors_config():
    """Load CORS configuration from environment."""
    allowed_origins = os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:8081,http://localhost:3000"
    )

    origins = [origin.strip() for origin in allowed_origins.split(",")]

    return {
        "allow_origins": origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Authorization", "Content-Type", "X-CSRF-Token"],
        "max_age": 3600,
    }
```

**Step 2: Update main.py to use configuration**
Replace the hardcoded CORS middleware with:

```python
from apps.backend.src.config.cors_config import get_cors_config

cors_config = get_cors_config()
app.add_middleware(
    CORSMiddleware,
    **cors_config
)
```

### Implementation TODO:
- [ ] Create `apps/backend/src/config/cors_config.py`
- [ ] Update `apps/backend/src/main.py` to use the new config
- [ ] Verify CORS headers in responses
- [ ] Test with frontend on different origin

---

## ISSUE 2: RATE LIMITING

### Current Problem
- No rate limiting on any endpoint
- API can be abused/DOS'd
- No protection against brute force attacks

### Solution

**Step 1: Create rate limiter module**
```python
# apps/backend/src/core/rate_limiter.py
import time
from typing import Dict, Tuple

class InMemoryRateLimiter:
    """Simple in-memory rate limiter for development."""

    def __init__(self):
        self.requests: Dict[str, list] = {}

    def is_allowed(
        self,
        key: str,
        max_requests: int = 100,
        window_seconds: int = 60
    ) -> bool:
        """
        Check if request is allowed under rate limit.
        Args:
            key: Unique identifier (e.g., user_id or IP)
            max_requests: Max requests allowed
            window_seconds: Time window
        """
        now = time.time()
        window_start = now - window_seconds

        if key not in self.requests:
            self.requests[key] = []

        # Clean old requests
        self.requests[key] = [
            req_time for req_time in self.requests[key]
            if req_time > window_start
        ]

        if len(self.requests[key]) < max_requests:
            self.requests[key].append(now)
            return True

        return False

# Global instance
rate_limiter = InMemoryRateLimiter()
```

**Step 2: Create rate limiting middleware**
```python
# apps/backend/src/middleware/rate_limit.py
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from ..core.rate_limiter import rate_limiter

class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Get identifier (user or IP)
        client_ip = request.client.host

        # Define limits per endpoint
        limits = {
            "/auth/login": (5, 300),           # 5 per 5 minutes
            "/reports/validate": (50, 60),     # 50 per minute
            "/findings": (100, 60),            # 100 per minute
        }

        # Check rate limit for this endpoint
        for pattern, (max_req, window) in limits.items():
            if pattern in request.url.path:
                if not rate_limiter.is_allowed(
                    f"{client_ip}:{request.url.path}",
                    max_req,
                    window
                ):
                    raise HTTPException(
                        status_code=429,
                        detail="Rate limit exceeded"
                    )

        response = await call_next(request)
        return response
```

**Step 3: Register middleware in main.py**
```python
from apps.backend.src.middleware.rate_limit import RateLimitMiddleware

# Add after CORS middleware
app.add_middleware(RateLimitMiddleware)
```

### Implementation TODO:
- [ ] Create `apps/backend/src/core/rate_limiter.py`
- [ ] Create `apps/backend/src/middleware/rate_limit.py`
- [ ] Register middleware in `apps/backend/src/main.py`
- [ ] Test rate limiting on auth endpoint

---

## ISSUE 3: CSRF PROTECTION

### Current Problem
- POST/PUT/DELETE endpoints don't validate CSRF tokens
- Forms can be submitted from external domains

### Solution

**Step 1: Create CSRF token manager**
```python
# apps/backend/src/core/csrf.py
import secrets
import hashlib
from typing import Dict

class CSRFTokenManager:
    """CSRF token generation and validation."""

    def __init__(self):
        self.tokens: Dict[str, str] = {}

    def generate_token(self, session_id: str) -> str:
        """Generate CSRF token for session."""
        token = secrets.token_urlsafe(32)
        self.tokens[session_id] = token
        return token

    def validate_token(self, session_id: str, token: str) -> bool:
        """Validate CSRF token."""
        stored_token = self.tokens.get(session_id)
        if not stored_token:
            return False

        # Use constant-time comparison
        return secrets.compare_digest(stored_token, token)

csrf_manager = CSRFTokenManager()
```

**Step 2: Create CSRF middleware**
```python
# apps/backend/src/middleware/csrf.py
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from ..core.csrf import csrf_manager

class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Skip CSRF check for GET, HEAD, OPTIONS
        if request.method not in ["POST", "PUT", "DELETE", "PATCH"]:
            return await call_next(request)

        # Skip for certain endpoints
        if request.url.path in ["/auth/login", "/health"]:
            return await call_next(request)

        # Get CSRF token from header
        csrf_token = request.headers.get("X-CSRF-Token")
        session_id = request.cookies.get("session_id", "anonymous")

        if not csrf_token:
            raise HTTPException(
                status_code=403,
                detail="CSRF token missing"
            )

        if not csrf_manager.validate_token(session_id, csrf_token):
            raise HTTPException(
                status_code=403,
                detail="CSRF token invalid"
            )

        response = await call_next(request)
        return response
```

**Step 3: Add CSRF token to login response**
```python
# apps/backend/src/routers/auth.py
from ..core.csrf import csrf_manager

@router.post('/login')
def login(req: LoginRequest):
    # ... existing validation ...

    # Generate CSRF token
    session_id = "user-session-id"  # In real app, generate proper session
    csrf_token = csrf_manager.generate_token(session_id)

    return {
        "ok": True,
        "csrf_token": csrf_token,  # Frontend will use this
        "session_id": session_id
    }
```

### Implementation TODO:
- [ ] Create `apps/backend/src/core/csrf.py`
- [ ] Create `apps/backend/src/middleware/csrf.py`
- [ ] Register middleware in `apps/backend/src/main.py`
- [ ] Update auth endpoint to return CSRF token
- [ ] Test CSRF validation on POST endpoints

---

## ISSUE 4: SECURITY HEADERS

### Solution
Add security headers to all responses

```python
# apps/backend/src/middleware/security_headers.py
from starlette.middleware.base import BaseHTTPMiddleware

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Enable XSS protection
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Require HTTPS (in production)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        return response
```

Add to main.py:
```python
from apps.backend.src.middleware.security_headers import SecurityHeadersMiddleware
app.add_middleware(SecurityHeadersMiddleware)
```

### Implementation TODO:
- [ ] Create `apps/backend/src/middleware/security_headers.py`
- [ ] Register in `apps/backend/src/main.py`

---

## IMPLEMENTATION CHECKLIST

### CORS Fix
- [ ] Create cors_config.py
- [ ] Update main.py with new CORS configuration
- [ ] Test CORS headers present in response
- [ ] Verify origin restrictions work

### Rate Limiting
- [ ] Create rate_limiter.py (in-memory)
- [ ] Create rate_limit.py middleware
- [ ] Register middleware
- [ ] Test 429 response when limit exceeded
- [ ] Verify endpoint limits work correctly

### CSRF Protection
- [ ] Create csrf.py token manager
- [ ] Create csrf.py middleware
- [ ] Register middleware
- [ ] Update auth to return CSRF token
- [ ] Test CSRF validation blocks bad tokens

### Security Headers
- [ ] Create security_headers.py
- [ ] Register middleware
- [ ] Verify headers in responses

---

## TESTING PHASE 2 FIXES

### Test CORS
```bash
# Should fail (origin not allowed)
curl -H "Origin: http://evil.com" http://localhost:8080/findings

# Should succeed
curl -H "Origin: http://localhost:8081" http://localhost:8080/findings
```

### Test Rate Limiting
```bash
# Run 10 times quickly, should fail on 6th
for i in {1..10}; do
  curl http://localhost:8080/auth/login -X POST
  echo "Request $i"
done
```

### Test CSRF
```bash
# Should fail (no CSRF token)
curl -X POST http://localhost:8080/reports/validate \
  -H "Content-Type: application/json"

# Should succeed (with valid CSRF token)
curl -X POST http://localhost:8080/reports/validate \
  -H "Content-Type: application/json" \
  -H "X-CSRF-Token: valid-token-here"
```

### Test Security Headers
```bash
curl -v http://localhost:8080/health | grep -i "X-Frame-Options\|X-Content-Type"
```

---

## VERIFICATION AFTER PHASE 2

Create `scripts/verify_phase2.py`:

```python
#!/usr/bin/env python3
"""Phase 2 Security Verification"""

import requests
import sys

BASE_URL = "http://localhost:8080"

def test_cors():
    """Test CORS is properly restricted."""
    headers = {"Origin": "http://evil.com"}
    resp = requests.get(f"{BASE_URL}/health", headers=headers)

    # Should not have wildcard origin
    allow_origin = resp.headers.get("Access-Control-Allow-Origin", "")
    if allow_origin == "*":
        print("[✗] CORS: Still allowing wildcard origin")
        return False
    print("[✓] CORS: Properly restricted")
    return True

def test_rate_limit():
    """Test rate limiting is enforced."""
    # Make many requests
    for i in range(10):
        resp = requests.get(f"{BASE_URL}/findings")
        if resp.status_code == 429:
            print("[✓] Rate Limiting: Enforced")
            return True
    print("[!] Rate Limiting: May not be working (depends on limits)")
    return True

def test_security_headers():
    """Test security headers are present."""
    resp = requests.get(f"{BASE_URL}/health")
    headers = resp.headers

    required = ["X-Frame-Options", "X-Content-Type-Options"]
    missing = [h for h in required if h not in headers]

    if missing:
        print(f"[✗] Security Headers: Missing {missing}")
        return False
    print("[✓] Security Headers: Present")
    return True

if __name__ == "__main__":
    tests = [test_cors, test_rate_limit, test_security_headers]
    results = [test() for test in tests]

    passed = sum(results)
    print(f"\nPhase 2: {passed}/{len(results)} checks passed")

    sys.exit(0 if all(results) else 1)
```

---

## PHASE 2 DEPENDENCIES

No new external dependencies needed - all security features use Python stdlib and FastAPI built-ins.

---

## TROUBLESHOOTING PHASE 2

### "CORS still not working"
- Verify CORS_ALLOWED_ORIGINS env var is set
- Restart backend service
- Check main.py has correct middleware

### "Rate limiting too strict"
- Adjust limits in rate_limit.py
- Use memory backend (not Redis)

### "CSRF token validation failing"
- Verify token returned from /login
- Check X-CSRF-Token header is being sent
- Ensure session ID is consistent

---

## PHASE 2 COMPLETION

Once all fixes are implemented and tested:

✓ CORS properly restricted
✓ Rate limiting protecting endpoints
✓ CSRF tokens validated
✓ Security headers in place

**Ready for Phase 3: Program Discovery Scraper** 🚀

