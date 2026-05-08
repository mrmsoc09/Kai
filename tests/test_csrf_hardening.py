from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from apps.backend.src.middleware.cookie_security import CookieSecurityMiddleware
from apps.backend.src.middleware.csrf import CSRFProtectionMiddleware
from apps.backend.src.middleware.security_headers import SecurityHeadersMiddleware
from apps.backend.src.routers import auth
from apps.backend.src.testing.csrf_test_utils import (
    build_csrf_headers,
    error_code,
    issue_csrf_challenge,
    issue_csrf_nonce,
    issue_csrf_token,
)


def _build_test_client() -> TestClient:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CookieSecurityMiddleware)
    app.add_middleware(CSRFProtectionMiddleware)
    app.include_router(auth.router)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/notes")
    def notes():
        return {"ok": True}

    @app.post("/tools/execute")
    def tools_execute():
        return {"ok": True}

    return TestClient(app)


def test_cookie_auth_rejects_missing_origin_header(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("CSRF_REQUIRE_ORIGIN_FOR_COOKIE", "true")

    client = _build_test_client()
    csrf_token = issue_csrf_token(client)

    response = client.post("/notes", headers={"X-CSRF-Token": csrf_token})

    assert response.status_code == 403
    assert error_code(response) == "missing_origin_header"


def test_cookie_auth_rejects_untrusted_origin(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "http://localhost:3000")

    client = _build_test_client()
    csrf_token = issue_csrf_token(client)

    response = client.post(
        "/notes",
        headers={
            "Origin": "http://evil.example",
            "X-CSRF-Token": csrf_token,
        },
    )

    assert response.status_code == 403
    assert error_code(response) == "invalid_origin"


def test_bearer_only_request_bypasses_csrf(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "http://localhost:3000")

    client = _build_test_client()

    response = client.post(
        "/notes",
        headers={"Authorization": "Bearer test-api-token"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_browser_cookie_request_requires_challenge(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "http://localhost:3000")

    client = _build_test_client()
    csrf_token = issue_csrf_token(client)
    headers = build_csrf_headers(csrf_token, "http://localhost:3000")

    first_try = client.post("/notes", headers=headers)
    assert first_try.status_code == 403
    assert error_code(first_try) == "missing_csrf_challenge"

    challenge = issue_csrf_challenge(client, path="/notes", method="POST")
    headers["X-CSRF-Challenge"] = challenge
    second_try = client.post("/notes", headers=headers)
    assert second_try.status_code == 200
    assert second_try.json()["ok"] is True


def test_high_risk_endpoint_requires_nonce(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "http://localhost:3000")

    client = _build_test_client()
    csrf_token = issue_csrf_token(client)
    challenge = issue_csrf_challenge(client, path="/tools/execute", method="POST")
    headers = build_csrf_headers(
        csrf_token,
        "http://localhost:3000",
        challenge=challenge,
    )

    first_try = client.post("/tools/execute", headers=headers)
    assert first_try.status_code == 403
    assert error_code(first_try) == "missing_csrf_nonce"

    nonce = issue_csrf_nonce(client, path="/tools/execute", method="POST")
    headers["X-CSRF-Nonce"] = nonce
    second_try = client.post("/tools/execute", headers=headers)
    assert second_try.status_code == 200
    assert second_try.json()["ok"] is True


def test_cookie_security_middleware_enforces_samesite_strict(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "http://localhost:3000")

    client = _build_test_client()
    response = client.get("/auth/csrf-token")

    assert response.status_code == 200
    set_cookie = response.headers.get("set-cookie", "")
    assert "session_id=" in set_cookie
    assert "SameSite=Strict" in set_cookie
    assert "HttpOnly" in set_cookie


def test_csp_header_present(monkeypatch):
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
    monkeypatch.setenv("CSRF_TRUSTED_ORIGINS", "http://localhost:3000")

    client = _build_test_client()
    response = client.get("/health")

    assert response.status_code == 200
    csp = response.headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp

