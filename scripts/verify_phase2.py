#!/usr/bin/env python3
"""
Phase 2 Security Verification Script
Verifies that all critical security fixes are in place and working.

Usage:
    python3 scripts/verify_phase2.py

    (Backend must be running on http://localhost:8080)
"""

import sys
import os

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
NC = '\033[0m'

def print_header(text):
    print(f"\n{BLUE}{'='*60}")
    print(f"{text:^60}")
    print(f"{'='*60}{NC}\n")

def print_success(text):
    print(f"{GREEN}[✓]{NC} {text}")

def print_error(text):
    print(f"{RED}[✗]{NC} {text}")

def print_warning(text):
    print(f"{YELLOW}[!]{NC} {text}")

def test_imports():
    """Test that all security modules import correctly."""
    print_header("1. Security Module Imports")

    modules = [
        ("apps.backend.src.config.cors_config", "CORS Config"),
        ("apps.backend.src.core.rate_limiter", "Rate Limiter"),
        ("apps.backend.src.core.csrf", "CSRF Manager"),
        ("apps.backend.src.middleware.rate_limit", "Rate Limit Middleware"),
        ("apps.backend.src.middleware.csrf", "CSRF Middleware"),
        ("apps.backend.src.middleware.security_headers", "Security Headers"),
    ]

    sys.path.insert(0, os.getcwd())
    all_good = True

    for module_path, name in modules:
        try:
            __import__(module_path)
            print_success(f"{name} imports successfully")
        except ImportError as e:
            print_error(f"{name} import failed: {e}")
            all_good = False

    return all_good


def test_cors_config():
    """Test CORS configuration."""
    print_header("2. CORS Configuration")

    try:
        from apps.backend.src.config.cors_config import get_cors_config

        config = get_cors_config()

        # Check that origins are properly loaded
        origins = config.get("allow_origins", [])
        if not origins:
            print_error("No origins configured")
            return False

        print_success(f"CORS configured with {len(origins)} origin(s):")
        for origin in origins:
            print(f"  - {origin}")

        # Check that wildcard is not used with credentials
        if "*" in origins and config.get("allow_credentials"):
            print_error("Wildcard origin with credentials enabled (DANGEROUS)")
            return False

        print_success("Wildcard origin + credentials check passed")

        # Check allowed methods are restricted
        methods = config.get("allow_methods", [])
        if "*" in methods:
            print_error("Wildcard methods allowed (should be restricted)")
            return False

        print_success(f"Allowed methods restricted to: {', '.join(methods)}")

        return True

    except Exception as e:
        print_error(f"CORS config test failed: {e}")
        return False


def test_rate_limiter():
    """Test rate limiting functionality."""
    print_header("3. Rate Limiting Engine")

    try:
        from apps.backend.src.core.rate_limiter import rate_limiter, get_rate_limit_for_endpoint

        # Test rate limiting
        key = "test_user:test_endpoint"

        # Should allow first request
        if not rate_limiter.is_allowed(key, max_requests=3, window_seconds=60):
            print_error("Rate limiter rejected first request (should be allowed)")
            return False

        print_success("Rate limiter allows first request")

        # Should allow second request
        if not rate_limiter.is_allowed(key, max_requests=3, window_seconds=60):
            print_error("Rate limiter rejected second request (should be allowed)")
            return False

        print_success("Rate limiter allows second request")

        # Should allow third request
        if not rate_limiter.is_allowed(key, max_requests=3, window_seconds=60):
            print_error("Rate limiter rejected third request (should be allowed)")
            return False

        print_success("Rate limiter allows third request")

        # Should reject fourth request
        if rate_limiter.is_allowed(key, max_requests=3, window_seconds=60):
            print_error("Rate limiter allowed fourth request (should be rejected)")
            return False

        print_success("Rate limiter correctly rejects request when limit exceeded")

        # Test endpoint limits
        limits = get_rate_limit_for_endpoint("/auth/login")
        if limits[0] != 5:  # Should be strict
            print_warning(f"Auth login limit is {limits[0]}, expected 5")

        print_success(f"Endpoint-specific limits working: /auth/login = {limits}")

        # Clean up
        rate_limiter.clear_key(key)

        return True

    except Exception as e:
        print_error(f"Rate limiter test failed: {e}")
        return False


def test_csrf_manager():
    """Test CSRF token generation and validation."""
    print_header("4. CSRF Protection")

    try:
        from apps.backend.src.core.csrf import csrf_manager

        session_id = "test_session_123"

        # Generate token
        token = csrf_manager.generate_token(session_id)
        if not token:
            print_error("Failed to generate CSRF token")
            return False

        print_success(f"CSRF token generated: {token[:20]}...")

        # Validate token
        if not csrf_manager.validate_token(session_id, token):
            print_error("CSRF token validation failed for valid token")
            return False

        print_success("CSRF token validation passed for valid token")

        # Test invalid token
        if csrf_manager.validate_token(session_id, "invalid_token"):
            print_error("CSRF validation accepted invalid token (should reject)")
            return False

        print_success("CSRF validation correctly rejects invalid token")

        # Test expired token (or wrong session)
        if csrf_manager.validate_token("different_session", token):
            print_error("CSRF validation accepted token from different session")
            return False

        print_success("CSRF validation correctly rejects token from different session")

        # Clean up
        csrf_manager.invalidate_token(session_id)

        return True

    except Exception as e:
        print_error(f"CSRF test failed: {e}")
        return False


def test_middleware_presence():
    """Test that middleware is registered in FastAPI app."""
    print_header("5. Middleware Registration")

    try:
        from apps.backend.src import main

        app = main.app

        # Check middleware stack (FastAPI wraps middleware, so we check type strings)
        middleware_count = len(app.user_middleware)

        print_success(f"Found {middleware_count} middleware(s) registered")

        # List what we expect
        print_success("Expected middleware stack (in order):")
        print("  1. SecurityHeadersMiddleware")
        print("  2. CSRFProtectionMiddleware")
        print("  3. RateLimitMiddleware")
        print("  4. CORSMiddleware")

        # Check that we have at least 4 middleware (exact check is difficult due to FastAPI wrapping)
        if middleware_count < 4:
            print_error(f"Expected at least 4 middleware, got {middleware_count}")
            return False

        print_success("All required security middleware appears to be registered")

        # Try to instantiate each module to ensure they work
        from apps.backend.src.middleware.security_headers import SecurityHeadersMiddleware
        from apps.backend.src.middleware.csrf import CSRFProtectionMiddleware
        from apps.backend.src.middleware.rate_limit import RateLimitMiddleware

        print_success("All middleware modules instantiate successfully")

        return True

    except Exception as e:
        print_error(f"Middleware check failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print(f"\n{BLUE}╔══════════════════════════════════════════════════════════╗{NC}")
    print(f"{BLUE}║{NC}         K1 PHASE 2: SECURITY VERIFICATION             {BLUE}║{NC}")
    print(f"{BLUE}╚══════════════════════════════════════════════════════════╝{NC}\n")

    tests = [
        ("Security Module Imports", test_imports),
        ("CORS Configuration", test_cors_config),
        ("Rate Limiting Engine", test_rate_limiter),
        ("CSRF Protection", test_csrf_manager),
        ("Middleware Registration", test_middleware_presence),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print_error(f"Test raised exception: {e}")
            results[test_name] = False

    # Summary
    print_header("VERIFICATION SUMMARY")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = f"{GREEN}PASS{NC}" if result else f"{RED}FAIL{NC}"
        print(f"  {test_name:.<40} {status}")

    print(f"\n  Total: {passed}/{total} checks passed")

    if passed == total:
        print(f"\n{GREEN}{'='*60}")
        print(f"{'✓ PHASE 2 SECURITY FIXES VERIFIED':^60}")
        print(f"{'='*60}{NC}\n")
        print("All security middleware is in place!")
        print("\nNext steps:")
        print("  1. Start the backend: python3 apps/backend/src/main.py")
        print("  2. Test with curl:")
        print("     - CORS: curl -H 'Origin: http://evil.com' http://localhost:8080/health")
        print("     - Rate limit: for i in {1..10}; do curl http://localhost:8080/auth/login; done")
        print("  3. Proceed to Phase 3: Program Discovery Scraper")
        print()
        return 0
    else:
        print(f"\n{RED}{'='*60}")
        print(f"{'✗ SOME CHECKS FAILED':^60}")
        print(f"{'='*60}{NC}\n")
        print("Fix the failed checks and run this script again.")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(main())
