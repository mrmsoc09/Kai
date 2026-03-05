from __future__ import annotations

import pytest

from apps.backend.src.core.secret_manager import (
    SecretManager,
    SecretManagerError,
)


def test_secret_manager_env_backend_reads_required(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("K1_SECRET_BACKEND", "env")
    monkeypatch.setenv("SHODAN_API_KEY", "abc123")

    manager = SecretManager()
    assert manager.get_required("SHODAN_API_KEY") == "abc123"


def test_secret_manager_required_missing_raises(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("K1_SECRET_BACKEND", "env")
    monkeypatch.delenv("SHODAN_API_KEY", raising=False)

    manager = SecretManager()
    with pytest.raises(SecretManagerError, match="required secret missing"):
        manager.get_required("SHODAN_API_KEY")


def test_secret_manager_vault_backend_falls_back_to_env_in_test(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("K1_SECRET_BACKEND", "vault")
    monkeypatch.delenv("VAULT_ADDR", raising=False)
    monkeypatch.delenv("VAULT_TOKEN", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "env-openai-key")

    manager = SecretManager()
    assert manager.get_required("OPENAI_API_KEY") == "env-openai-key"
