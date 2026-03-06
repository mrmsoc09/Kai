from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from apps.backend.src.core.kai_security_guardrails import (
    AuthorizationCertificate,
    GuardRailEngine,
    ScanAuthorization,
    ScanScope,
)


def test_authorization_ledger_persists_certificates(monkeypatch, tmp_path: Path):
    ledger = tmp_path / "auth_ledger.json"
    monkeypatch.setenv("K1_AUTH_LEDGER_PATH", str(ledger))

    engine = GuardRailEngine()
    cert = AuthorizationCertificate(
        certificate_id="cert-123",
        authorization_type=ScanAuthorization.BUG_BOUNTY_PLATFORM,
        target="example.com",
        scope=ScanScope.SINGLE_DOMAIN,
        authorized_by="owner@example.com",
        issued_at=datetime.utcnow() - timedelta(hours=1),
        expires_at=datetime.utcnow() + timedelta(days=1),
        allowed_methods=["dns_enum"],
        metadata={"user_id": "user-1"},
    )

    assert engine.register_authorization(cert)
    assert ledger.exists()

    restored = GuardRailEngine()
    assert "cert-123" in restored.authorized_certificates


def test_authorization_ledger_persists_decisions(monkeypatch, tmp_path: Path):
    ledger = tmp_path / "auth_ledger.json"
    monkeypatch.setenv("K1_AUTH_LEDGER_PATH", str(ledger))

    engine = GuardRailEngine()
    engine._log_blocked_operation(
        user_id="user-2",
        target="out-of-scope.example",
        scan_type="osint",
        scan_method="dns_enum",
        reason="No valid authorization",
    )

    restored = GuardRailEngine()
    assert len(restored.blocked_operations) >= 1
    assert restored.blocked_operations[0]["user_id"] == "user-2"
