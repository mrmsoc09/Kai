from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from apps.backend.src.core.authorization_gate import (
    authorization_certificate_check,
    enforce_authorization_gates,
    scope_validator,
    AuthorizationGateError,
)
from apps.backend.src.core.kai_security_guardrails import (
    AuthorizationCertificate,
    ScanAuthorization,
    ScanScope,
    get_guardrail_engine,
)


@pytest.fixture
def guardrails():
    engine = get_guardrail_engine()
    engine.authorized_certificates.clear()
    engine.audit_logs.clear()
    engine.blocked_operations.clear()
    yield engine
    engine.authorized_certificates.clear()
    engine.audit_logs.clear()
    engine.blocked_operations.clear()


def test_scope_validator_rejects_missing_fields():
    # Empty target/program_id/method are rejected before any scope lookup.
    assert scope_validator("", "program-1", "dns_enum") is False
    assert scope_validator("example.com", "", "dns_enum") is False
    assert scope_validator("example.com", "program-1", "") is False


def test_authorization_certificate_check_accepts_valid_certificate(guardrails):
    cert = AuthorizationCertificate(
        certificate_id="cert-1",
        authorization_type=ScanAuthorization.BUG_BOUNTY_PLATFORM,
        target="example.com",
        scope=ScanScope.SINGLE_DOMAIN,
        authorized_by="operator",
        issued_at=datetime.now(timezone.utc) - timedelta(days=1),
        expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        allowed_methods=["dns_enum"],
        metadata={"user_id": "user-1"},
    )
    guardrails.authorized_certificates[cert.certificate_id] = cert

    assert authorization_certificate_check(
        user_id="user-1",
        certificate_id="cert-1",
        target="example.com",
        method="dns_enum",
    )


def test_enforce_authorization_gates_blocks_without_valid_scope_or_cert(
    guardrails,
    monkeypatch: pytest.MonkeyPatch,
):
    from apps.backend.src.core.scope_guardrails import ScopeDecision

    monkeypatch.setenv("K1_TEST_MODE", "true")
    monkeypatch.setenv("K1_RELAX_AUTH_GATES_FOR_TESTS", "false")

    # Simulate out-of-scope: evaluate_target_scope returns allowed=False.
    monkeypatch.setattr(
        "apps.backend.src.core.authorization_gate.evaluate_target_scope",
        lambda target, policy, **kw: ScopeDecision(
            target=target, normalized_host=target, allowed=False, reason="test_out_of_scope"
        ),
    )

    with pytest.raises(AuthorizationGateError, match="scope_validator failed"):
        enforce_authorization_gates(
            "subfinder",
            {"target": "example.com"},
            user_id="user-1",
            program_id="program-1",
            certificate_id="cert-1",
            method="dns_enum",
        )

    # Simulate in-scope but missing cert → certificate check fails.
    monkeypatch.setattr(
        "apps.backend.src.core.authorization_gate.evaluate_target_scope",
        lambda target, policy, **kw: ScopeDecision(
            target=target, normalized_host=target, allowed=True, reason="test_in_scope"
        ),
    )
    with pytest.raises(AuthorizationGateError, match="authorization_certificate_check failed"):
        enforce_authorization_gates(
            "subfinder",
            {"target": "example.com"},
            user_id="user-1",
            program_id="program-1",
            certificate_id="missing-cert",
            method="dns_enum",
        )
