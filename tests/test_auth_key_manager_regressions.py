from __future__ import annotations

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
import pytest

from apps.backend.src.core import auth as auth_mod
from apps.backend.src.core import key_manager as key_manager_mod


class _SecretManagerStub:
    def __init__(self, value: str | None) -> None:
        self.value = value

    def get_optional(self, name: str) -> str | None:
        assert name == "VAULT_TOKEN"
        return self.value


class _DummyVaultClient:
    def __init__(self, *, url: str, token: str) -> None:
        self.url = url
        self.token = token

    def is_authenticated(self) -> bool:
        return bool(self.token)


def test_decode_access_token_missing_jose_returns_controlled_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_mod, "jwt", None)

    with pytest.raises(HTTPException) as exc_info:
        auth_mod.decode_access_token("any-token")

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "auth_not_configured"


def test_get_current_user_dev_token_fallback_survives_missing_jose(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_mod, "jwt", None)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("K1_DEV_TOKEN", "dev-token")

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials="dev-token")
    user = auth_mod.get_current_user(creds)

    assert user.id == "dev"
    assert auth_mod.ROLE_ADMIN in user.roles


def test_key_manager_uses_explicit_token_before_any_other_source(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("VAULT_TOKEN", raising=False)
    monkeypatch.delenv("K1_TEST_MODE", raising=False)
    monkeypatch.delenv("K1_ALLOW_DEV_VAULT_ROOT", raising=False)
    monkeypatch.setattr(key_manager_mod, "get_secret_manager", lambda: _SecretManagerStub("secret-token"))
    monkeypatch.setattr(key_manager_mod.hvac, "Client", _DummyVaultClient)

    manager = key_manager_mod.KeyManager(vault_token="explicit-token")

    assert manager.vault_token == "explicit-token"
    assert isinstance(manager.client, _DummyVaultClient)
    assert manager.client.token == "explicit-token"


def test_key_manager_prefers_environment_token_over_secret_manager(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("VAULT_TOKEN", "env-token")
    monkeypatch.delenv("K1_TEST_MODE", raising=False)
    monkeypatch.delenv("K1_ALLOW_DEV_VAULT_ROOT", raising=False)
    monkeypatch.setattr(key_manager_mod, "get_secret_manager", lambda: _SecretManagerStub("secret-token"))
    monkeypatch.setattr(key_manager_mod.hvac, "Client", _DummyVaultClient)

    manager = key_manager_mod.KeyManager()

    assert manager.vault_token == "env-token"
    assert manager.client.token == "env-token"


def test_key_manager_raises_when_no_token_in_production(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("VAULT_TOKEN", raising=False)
    monkeypatch.delenv("K1_TEST_MODE", raising=False)
    monkeypatch.delenv("K1_ALLOW_DEV_VAULT_ROOT", raising=False)
    monkeypatch.setattr(key_manager_mod, "get_secret_manager", lambda: _SecretManagerStub(None))

    with pytest.raises(RuntimeError, match="VAULT_TOKEN is not configured"):
        key_manager_mod.KeyManager()


def test_key_manager_allows_explicit_non_production_root_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("K1_TEST_MODE", "true")
    monkeypatch.delenv("VAULT_TOKEN", raising=False)
    monkeypatch.delenv("K1_ALLOW_DEV_VAULT_ROOT", raising=False)
    monkeypatch.setattr(key_manager_mod, "get_secret_manager", lambda: _SecretManagerStub(None))
    monkeypatch.setattr(key_manager_mod.hvac, "Client", _DummyVaultClient)

    manager = key_manager_mod.KeyManager()

    assert manager.vault_token == "root"
    assert manager.client.token == "root"
