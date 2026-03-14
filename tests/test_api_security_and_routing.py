from __future__ import annotations

from datetime import datetime, timedelta
import importlib

import pytest
from tests.asgi_test_client import ASGITestClient


def _app():
    from apps.backend.src.main import app

    return app


def test_mutation_endpoints_require_authentication(auth_headers):
    app = _app()
    authed = ASGITestClient(app)
    authed.headers.update(auth_headers)
    anonymous = ASGITestClient(app)

    requests = [
        ("POST", "/api/v1/campaigns/start", {}),
        (
            "POST",
            "/api/v1/findings/00000000-0000-0000-0000-000000000000/review",
            {"json": {"action": "APPROVE", "reviewer_id": "u1"}},
        ),
        ("POST", "/api/v1/tools/finding_validator/execute", {"json": {"target": "example.com"}}),
        ("POST", "/findings/set_status", {"json": {"run_id": "r1", "status": "SIGNAL"}}),
    ]

    for method, path, kwargs in requests:
        anon_resp = anonymous.request(method, path, **kwargs)
        assert anon_resp.status_code in {401, 403}, (path, anon_resp.status_code, anon_resp.text)

        # Avoid asserting success for endpoints that can legitimately fail deeper dependencies
        # in lightweight test environments (e.g., DB-backed campaign routes).
        if path.startswith("/api/v1/campaigns/") or path.startswith("/api/v1/findings/"):
            continue
        authed_resp = authed.request(method, path, **kwargs)
        assert authed_resp.status_code not in {401, 403}, (path, authed_resp.status_code, authed_resp.text)


def test_tools_static_routes_not_shadowed(client):
    categories = client.get("/api/v1/tools/categories")
    assert categories.status_code == 200, categories.text
    cat_payload = categories.json()
    assert cat_payload.get("success") is True
    assert isinstance(cat_payload.get("data", {}).get("categories"), list)

    stats = client.get("/api/v1/tools/stats")
    assert stats.status_code in {200, 422}, stats.text
    if stats.status_code == 200:
        stats_payload = stats.json()
        assert stats_payload.get("success") is True
        assert isinstance(stats_payload.get("data"), dict)
    else:
        # Ensure static route resolved (not dynamic /{tool_id} "tool not found").
        assert "Tool not found: stats" not in stats.text

    catalog = client.get("/api/v1/tools/catalog/list")
    assert catalog.status_code == 200, catalog.text
    catalog_payload = catalog.json()
    assert catalog_payload.get("success") is True
    assert isinstance(catalog_payload.get("data", {}).get("tools"), list)


def test_tools_approve_reject_preserve_http_errors(client):
    listed = client.get("/api/v1/tools")
    assert listed.status_code == 200, listed.text
    tools = listed.json().get("data", {}).get("tools", [])
    assert tools, "expected at least one registered tool"
    tool_id = tools[0]["id"]

    approve = client.post(f"/api/v1/tools/{tool_id}/approve", params={"execution_id": "missing-exec"})
    assert approve.status_code in {404, 500}, approve.text
    if approve.status_code == 500:
        assert "Execution request not found" in approve.text or "driver missing" in approve.text.lower()

    reject = client.post(
        f"/api/v1/tools/{tool_id}/reject",
        params={"execution_id": "missing-exec", "reason": "test"},
    )
    assert reject.status_code in {404, 500}, reject.text
    if reject.status_code == 500:
        assert "Execution request not found" in reject.text or "driver missing" in reject.text.lower()


def test_tools_registry_degrades_without_anthropic_key(client, monkeypatch):
    tools_router = importlib.import_module("apps.backend.src.routers.tools")

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    tools_router._registry = None
    listed = client.get("/api/v1/tools")
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    assert payload.get("success") is True
    assert isinstance(payload.get("data", {}).get("tools"), list)
    tools_router._registry = None


def test_tools_registry_degrades_when_optional_tool_import_fails(client, monkeypatch):
    tools_router = importlib.import_module("apps.backend.src.routers.tools")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    def _boom():
        raise ImportError("anthropic package required")

    monkeypatch.setattr(tools_router, "FindingValidatorTool", _boom)
    monkeypatch.setattr(tools_router, "QuickClassifierTool", _boom)
    monkeypatch.setattr(tools_router, "VulnerabilityAnalyzerTool", _boom)
    monkeypatch.setattr(tools_router, "ChainAnalyzerTool", _boom)
    monkeypatch.setattr(tools_router, "ProgramMatcherTool", _boom)

    tools_router._registry = None
    listed = client.get("/api/v1/tools")
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    assert payload.get("success") is True
    assert isinstance(payload.get("data", {}).get("tools"), list)
    tools_router._registry = None


def test_tools_authorization_context_rejects_spoofed_program_id():
    tools_router = importlib.import_module("apps.backend.src.routers.tools")
    from apps.backend.src.core.auth import User
    from apps.backend.src.core.kai_security_guardrails import (
        AuthorizationCertificate,
        ScanAuthorization,
        ScanScope,
        get_guardrail_engine,
    )

    guardrails = get_guardrail_engine()
    original_certs = dict(guardrails.authorized_certificates)
    cert = AuthorizationCertificate(
        certificate_id="cert-test-tools-spoof",
        authorization_type=ScanAuthorization.BUG_BOUNTY_PLATFORM,
        target="*.example.com",
        scope=ScanScope.DOMAIN_WILDCARD,
        authorized_by="owner@example.com",
        issued_at=datetime.utcnow() - timedelta(minutes=5),
        expires_at=datetime.utcnow() + timedelta(days=1),
        allowed_methods=["tool_execution"],
        metadata={"user_id": "dev", "program_id": "program-real"},
    )
    guardrails.authorized_certificates = {cert.certificate_id: cert}
    try:
        with pytest.raises(Exception) as exc_info:
            tools_router._resolve_authorization_hints(
                tool_id="dummy",
                params={"target": "api.example.com"},
                method="tool_execution",
                current_user=User(id="dev", roles=["operator"]),
                requested_program_id="program-spoofed",
                requested_certificate_id=cert.certificate_id,
            )
        assert getattr(exc_info.value, "status_code", None) == 403
    finally:
        guardrails.authorized_certificates = original_certs
