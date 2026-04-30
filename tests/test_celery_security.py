"""Tests for Celery signed-task and encrypted-result helpers (A.8).

These tests are fully self-contained — no Redis, PostgreSQL, or Vault required.
"""
from __future__ import annotations

import importlib
import json
import logging
import os
import sys
from types import ModuleType
from unittest.mock import patch

import pytest


# ---------------------------------------------------------------------------
# Helpers to reload the module under test with a clean env
# ---------------------------------------------------------------------------

_MODULE = "apps.backend.src.worker.celery_app"


def _reload_celery_app(env_overrides: dict[str, str] | None = None) -> ModuleType:
    """Re-import celery_app with specific env vars applied."""
    env = {k: v for k, v in os.environ.items()}
    for key in (
        "K1_CELERY_RESULT_KEY",
        "K1_CELERY_SECURITY_KEY",
        "K1_CELERY_SECURITY_CERT",
        "K1_CELERY_SECURITY_CERT_DIR",
        "K1_CELERY_SECRET_KEY",
    ):
        env.pop(key, None)
    if env_overrides:
        env.update(env_overrides)

    if _MODULE in sys.modules:
        del sys.modules[_MODULE]

    with patch.dict(os.environ, env, clear=True):
        mod = importlib.import_module(_MODULE)
    return mod


# ---------------------------------------------------------------------------
# Fernet helpers
# ---------------------------------------------------------------------------


class TestGetFernet:
    def test_returns_fernet_instance_with_explicit_key(self) -> None:
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        mod = _reload_celery_app({"K1_CELERY_RESULT_KEY": key})
        f = mod._get_fernet()
        assert isinstance(f, Fernet)

    def test_fallback_dev_key_when_env_absent(self, caplog: pytest.LogCaptureFixture) -> None:
        from cryptography.fernet import Fernet

        with caplog.at_level(logging.WARNING, logger="apps.backend.src.worker.celery_app"):
            mod = _reload_celery_app()
            f = mod._get_fernet()
        assert isinstance(f, Fernet)
        assert any("insecure dev key" in r.message for r in caplog.records)

    def test_dev_key_is_deterministic(self) -> None:
        mod1 = _reload_celery_app()
        mod2 = _reload_celery_app()
        # Both modules should produce the same dev key (SHA-256 of fixed seed).
        key1 = mod1._get_fernet()._signing_key
        key2 = mod2._get_fernet()._signing_key
        assert key1 == key2


# ---------------------------------------------------------------------------
# _encrypt_result / _decrypt_result round-trips
# ---------------------------------------------------------------------------


class TestEncryptDecryptResult:
    def _make_mod(self) -> ModuleType:
        from cryptography.fernet import Fernet

        key = Fernet.generate_key().decode()
        return _reload_celery_app({"K1_CELERY_RESULT_KEY": key})

    def test_round_trip_dict(self) -> None:
        mod = self._make_mod()
        data = {"status": "completed", "findings": [{"id": 1, "severity": "high"}]}
        token = mod._encrypt_result(data)
        assert isinstance(token, str)
        recovered = mod._decrypt_result(token)
        assert recovered == data

    def test_round_trip_list(self) -> None:
        mod = self._make_mod()
        data = [1, "two", {"three": 3}]
        assert mod._decrypt_result(mod._encrypt_result(data)) == data

    def test_round_trip_string(self) -> None:
        mod = self._make_mod()
        data = "hello world"
        assert mod._decrypt_result(mod._encrypt_result(data)) == data

    def test_round_trip_none(self) -> None:
        mod = self._make_mod()
        assert mod._decrypt_result(mod._encrypt_result(None)) is None

    def test_encrypted_token_differs_from_plaintext(self) -> None:
        mod = self._make_mod()
        data = {"secret": "value"}
        token = mod._encrypt_result(data)
        # Token must not contain the raw JSON in plaintext.
        assert json.dumps(data) not in token

    def test_wrong_key_raises(self) -> None:
        """Decryption with a different key must raise InvalidToken.

        _get_fernet() reads K1_CELERY_RESULT_KEY at call time, so we must keep
        the patched env active during both encrypt and decrypt calls.
        """
        from cryptography.fernet import Fernet, InvalidToken

        key_a = Fernet.generate_key().decode()
        key_b = Fernet.generate_key().decode()

        # Encrypt with key_a.
        with patch.dict(os.environ, {"K1_CELERY_RESULT_KEY": key_a}, clear=False):
            mod = _reload_celery_app({"K1_CELERY_RESULT_KEY": key_a})
            token = mod._encrypt_result({"x": 1})

        # Attempt to decrypt with key_b — must fail.
        with patch.dict(os.environ, {"K1_CELERY_RESULT_KEY": key_b}, clear=False):
            with pytest.raises(InvalidToken):
                mod._decrypt_result(token)

    def test_bytes_token_accepted_by_decrypt(self) -> None:
        mod = self._make_mod()
        data = {"k": "v"}
        token_str = mod._encrypt_result(data)
        # _decrypt_result must accept bytes as well as str.
        assert mod._decrypt_result(token_str.encode()) == data


# ---------------------------------------------------------------------------
# Serializer configuration
# ---------------------------------------------------------------------------


class TestCeleryConf:
    def test_default_serializer_is_json_when_no_pki(self) -> None:
        mod = _reload_celery_app()
        assert mod.celery_app.conf.task_serializer == "json"
        assert "json" in mod.celery_app.conf.accept_content

    def test_result_serializer_is_json(self) -> None:
        mod = _reload_celery_app()
        assert mod.celery_app.conf.result_serializer == "json"

    def test_task_create_missing_queues_enabled(self) -> None:
        mod = _reload_celery_app()
        assert mod.celery_app.conf.task_create_missing_queues is True

    def test_signing_disabled_warning_when_no_env(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="apps.backend.src.worker.celery_app"):
            _reload_celery_app()
        assert any("task signing DISABLED" in r.message for r in caplog.records)

    def test_legacy_secret_key_triggers_pki_guidance(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level(logging.WARNING, logger="apps.backend.src.worker.celery_app"):
            _reload_celery_app({"K1_CELERY_SECRET_KEY": "some-hmac-secret"})
        messages = " ".join(r.message for r in caplog.records)
        assert "K1_CELERY_SECRET_KEY is set but Celery task signing requires PKI" in messages

    def test_partial_pki_env_still_disabled(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        # Only key provided, no cert or cert_dir.
        with caplog.at_level(logging.WARNING, logger="apps.backend.src.worker.celery_app"):
            mod = _reload_celery_app({"K1_CELERY_SECURITY_KEY": "/tmp/key.pem"})
        assert mod.celery_app.conf.task_serializer == "json"
        assert any("task signing DISABLED" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Import smoke test
# ---------------------------------------------------------------------------


class TestImportClean:
    def test_module_importable_without_external_services(self) -> None:
        """Importing celery_app must not connect to Redis or raise."""
        mod = _reload_celery_app()
        assert hasattr(mod, "celery_app")
        assert hasattr(mod, "_encrypt_result")
        assert hasattr(mod, "_decrypt_result")
        assert hasattr(mod, "_get_fernet")

    def test_celery_app_main_name(self) -> None:
        mod = _reload_celery_app()
        assert mod.celery_app.main == "k1_worker"
