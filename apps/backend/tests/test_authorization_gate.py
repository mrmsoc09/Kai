from __future__ import annotations

from datetime import datetime, timedelta

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


def test_scope_validator_rejects_missing_fields(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("apps.backend.src.core.authorization_gate.is_in_scope", lambda _: True)
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
        issued_at=datetime.utcnow() - timedelta(days=1),
        expires_at=datetime.utcnow() + timedelta(days=1),
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
    monkeypatch.setenv("K1_TEST_MODE", "true")
    monkeypatch.setenv("K1_RELAX_AUTH_GATES_FOR_TESTS", "false")
    monkeypatch.setattr("apps.backend.src.core.authorization_gate.is_in_scope", lambda _: False)

    with pytest.raises(AuthorizationGateError, match="scope_validator failed"):
        enforce_authorization_gates(
            "subfinder",
            {"target": "example.com"},
            user_id="user-1",
            program_id="program-1",
            certificate_id="cert-1",
            method="dns_enum",
        )

    monkeypatch.setattr("apps.backend.src.core.authorization_gate.is_in_scope", lambda _: True)
    with pytest.raises(AuthorizationGateError, match="authorization_certificate_check failed"):
        enforce_authorization_gates(
            "subfinder",
            {"target": "example.com"},
            user_id="user-1",
            program_id="program-1",
            certificate_id="missing-cert",
            method="dns_enum",
        )
