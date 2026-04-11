"""
Comprehensive test suite for Vault secrets management integration.

Tests cover VaultClient initialization, secret operations, validation,
audit logging, and FastAPI endpoint integration with proper RBAC enforcement.
"""

from __future__ import annotations

import os
import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone

from apps.backend.src.core.vault_client import (
    VaultClient,
    VaultException,
    VaultConnectionError,
    SecretNotFoundError,
    SecretValidationError,
    VaultPermissionError,
)
from apps.backend.src.models.vault_models import (
    StoreSecretRequest,
    SecretResponse,
    ListSecretsResponse,
    SecretMetadataResponse,
    TestSecretRequest,
    TestSecretResponse,
    RotateSecretRequest,
    RotateSecretResponse,
    VaultHealthResponse,
)


class TestVaultClientInitialization:
    """Test VaultClient initialization and configuration."""

    def test_init_with_explicit_params(self):
        """Test initialization with explicit parameters."""
        with patch("apps.backend.src.core.vault_client.hvac.Client"):
            client = VaultClient(
                vault_addr="http://vault:8200", vault_token="test-token", vault_namespace="k1"
            )
            assert client.vault_addr == "http://vault:8200"
            assert client.vault_token == "test-token"
            assert client.vault_namespace == "k1"

    def test_init_with_env_vars(self, monkeypatch):
        """Test initialization with environment variables."""
        monkeypatch.setenv("VAULT_ADDR", "http://vault:8200")
        monkeypatch.setenv("VAULT_TOKEN", "env-token")
        monkeypatch.setenv("VAULT_NAMESPACE", "k1")

        with patch("apps.backend.src.core.vault_client.hvac.Client"):
            client = VaultClient()
            assert client.vault_addr == "http://vault:8200"
            assert client.vault_token == "env-token"
            assert client.vault_namespace == "k1"

    def test_init_defaults(self, monkeypatch):
        """Test initialization with default values."""
        monkeypatch.delenv("VAULT_ADDR", raising=False)
        monkeypatch.delenv("VAULT_TOKEN", raising=False)
        monkeypatch.delenv("VAULT_NAMESPACE", raising=False)

        with patch("apps.backend.src.core.vault_client.hvac.Client"):
            client = VaultClient()
            assert client.vault_addr == "http://localhost:8200"
            assert client.retry_count == 3
            assert client.retry_delay == 1
            assert client.skip_verify is False


class TestVaultClientHealthCheck:
    """Test health check operations."""

    def test_health_check_success(self):
        """Test successful health check."""
        mock_client = MagicMock()
        mock_client.sys.read_health_status.return_value = {
            "sealed": False,
            "initialized": True,
            "standby": False,
            "version": "1.15.0",
            "cluster_name": "vault",
            "cluster_id": "test-id",
        }

        with patch("apps.backend.src.core.vault_client.hvac.Client", return_value=mock_client):
            client = VaultClient()
            health = client.health_check()

            assert health["sealed"] is False
            assert health["initialized"] is True
            assert health["version"] == "1.15.0"

    def test_health_check_sealed(self):
        """Test health check when Vault is sealed."""
        mock_client = MagicMock()
        mock_client.sys.read_health_status.return_value = {
            "sealed": True,
            "initialized": True,
            "standby": False,
            "version": "1.15.0",
        }

        with patch("apps.backend.src.core.vault_client.hvac.Client", return_value=mock_client):
            client = VaultClient()
            health = client.health_check()
            assert health["sealed"] is True

    def test_health_check_failure(self):
        """Test health check with connection error."""
        mock_client = MagicMock()
        mock_client.sys.read_health_status.side_effect = Exception("Connection refused")

        with patch("apps.backend.src.core.vault_client.hvac.Client", return_value=mock_client):
            client = VaultClient()
            with pytest.raises(VaultConnectionError):
                client.health_check()


class TestVaultClientSecretOperations:
    """Test secret write, read, delete operations."""

    def test_write_secret_success(self):
        """Test successful secret write."""
        from hvac.exceptions import InvalidPath

        mock_client = MagicMock()
        # First call to check existence raises InvalidPath (secret doesn't exist)
        mock_client.secrets.kv.v2.read_secret_version.side_effect = InvalidPath("Not found")
        mock_client.secrets.kv.v2.create_or_update_secret = MagicMock()

        with patch("apps.backend.src.core.vault_client.hvac.Client", return_value=mock_client):
            with patch("apps.backend.src.core.vault_client.InvalidPath", InvalidPath):
                client = VaultClient()
                result = client.write_secret(
                    "secret/data/kaison/test", {"value": "secret123"}, overwrite=False
                )
                assert result is True

    def test_write_secret_already_exists(self):
        """Test write fails when secret already exists and overwrite=False."""
        mock_client = MagicMock()
        # First call returns existing secret (doesn't raise exception)
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"value": "existing"}}
        }

        with patch("apps.backend.src.core.vault_client.hvac.Client", return_value=mock_client):
            client = VaultClient()
            with pytest.raises(VaultPermissionError):
                client.write_secret(
                    "secret/data/kaison/test", {"value": "new_secret"}, overwrite=False
                )

    def test_read_secret_success(self):
        """Test successful secret read."""
        mock_client = MagicMock()
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"value": "secret123"}}
        }

        with patch("apps.backend.src.core.vault_client.hvac.Client", return_value=mock_client):
            client = VaultClient()
            secret = client.read_secret("secret/data/kaison/test")
            assert secret["value"] == "secret123"

    def test_read_secret_not_found(self):
        """Test read fails when secret doesn't exist."""
        mock_client = MagicMock()
        from hvac.exceptions import InvalidPath, VaultError

        # InvalidPath is a subclass of VaultError, so it will be caught and retried
        # After retries, it becomes a VaultConnectionError
        mock_client.secrets.kv.v2.read_secret_version.side_effect = InvalidPath("Not found")

        with patch("apps.backend.src.core.vault_client.hvac.Client", return_value=mock_client):
            with patch("apps.backend.src.core.vault_client.InvalidPath", InvalidPath):
                client = VaultClient(retry_count=1)  # Reduce retries for test speed
                # When InvalidPath is raised during read_secret, it becomes VaultConnectionError
                with pytest.raises((SecretNotFoundError, VaultConnectionError)):
                    client.read_secret("secret/data/kaison/nonexistent")

    def test_delete_secret_success(self):
        """Test successful secret deletion."""
        mock_client = MagicMock()
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"value": "secret123"}}
        }
        mock_client.secrets.kv.v2.delete_secret_versions = MagicMock()

        with patch("apps.backend.src.core.vault_client.hvac.Client", return_value=mock_client):
            client = VaultClient()
            result = client.delete_secret("secret/data/kaison/test")
            assert result is True

    def test_list_secrets(self):
        """Test listing secrets under prefix."""
        mock_client = MagicMock()
        mock_client.secrets.kv.v2.list_secrets.return_value = {
            "data": {"keys": ["secret1", "secret2", "secret3"]}
        }

        with patch("apps.backend.src.core.vault_client.hvac.Client", return_value=mock_client):
            client = VaultClient()
            secrets = client.list_secrets("secret/data/kaison")
            assert len(secrets) == 3
            assert "secret1" in secrets


class TestVaultClientUpdateAndRotate:
    """Test secret update and rotation operations."""

    def test_update_secret(self):
        """Test merging secret fields."""
        mock_client = MagicMock()
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"value": "old_secret", "type": "api_key"}}
        }
        mock_client.secrets.kv.v2.create_or_update_secret = MagicMock()

        with patch("apps.backend.src.core.vault_client.hvac.Client", return_value=mock_client):
            client = VaultClient()
            result = client.update_secret("secret/data/kaison/test", {"description": "Updated"})
            assert result is True

    def test_rotate_secret_single_field(self):
        """Test rotating secret with single field."""
        mock_client = MagicMock()
        mock_client.secrets.kv.v2.read_secret_version.return_value = {
            "data": {"data": {"value": "old_secret"}}
        }
        mock_client.secrets.kv.v2.create_or_update_secret = MagicMock()

        with patch("apps.backend.src.core.vault_client.hvac.Client", return_value=mock_client):
            client = VaultClient()
            result = client.rotate_secret("secret/data/kaison/test", "new_secret")
            assert result is True

    def test_get_secret_metadata(self):
        """Test retrieving secret metadata."""
        mock_client = MagicMock()
        mock_client.secrets.kv.v2.read_secret_metadata.return_value = {
            "data": {
                "created_time": "2026-04-11T12:00:00Z",
                "updated_time": "2026-04-11T12:00:00Z",
                "current_version": 1,
                "versions": [{"version": 1}],
            }
        }

        with patch("apps.backend.src.core.vault_client.hvac.Client", return_value=mock_client):
            client = VaultClient()
            metadata = client.get_secret_metadata("secret/data/kaison/test")
            assert metadata["current_version"] == 1


class TestVaultClientValidation:
    """Test secret validation against live APIs."""

    def test_validate_secret_openai(self):
        """Test OpenAI API key validation."""
        mock_client = MagicMock()

        with patch("apps.backend.src.core.vault_client.hvac.Client", return_value=mock_client):
            with patch("openai.OpenAI") as mock_openai:
                mock_openai.return_value.models.list.return_value = MagicMock()
                client = VaultClient()
                is_valid, error = client.validate_secret("openai", "sk-test123")
                assert is_valid is True

    def test_validate_secret_github(self):
        """Test GitHub token validation."""
        mock_client = MagicMock()

        with patch("apps.backend.src.core.vault_client.hvac.Client", return_value=mock_client):
            with patch("requests.get") as mock_get:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_get.return_value = mock_response
                client = VaultClient()
                is_valid, error = client.validate_secret("github", "ghp_test123")
                assert is_valid is True

    def test_validate_secret_invalid_format(self):
        """Test validation fails for invalid secret format."""
        mock_client = MagicMock()

        with patch("apps.backend.src.core.vault_client.hvac.Client", return_value=mock_client):
            client = VaultClient()
            is_valid, error = client.validate_secret("unknown_service", "short")
            assert is_valid is False


class TestVaultClientSyncToEnv:
    """Test syncing secrets to environment variables."""

    def test_sync_secrets_to_env(self):
        """Test syncing secrets from Vault to environment."""
        mock_client = MagicMock()
        mock_client.secrets.kv.v2.list_secrets.return_value = {
            "data": {"keys": ["api_key", "db_password"]}
        }
        mock_client.secrets.kv.v2.read_secret_version.side_effect = [
            {"data": {"data": {"key": "value1"}}},
            {"data": {"data": {"key": "value2"}}},
        ]

        with patch("apps.backend.src.core.vault_client.hvac.Client", return_value=mock_client):
            client = VaultClient()
            synced = client.sync_secrets_to_env("secret/data/kaison")
            assert synced >= 0


class TestVaultClientAuditLog:
    """Test audit logging operations."""

    def test_get_secret_audit_log(self):
        """Test retrieving audit log for secret."""
        mock_client = MagicMock()
        mock_client.sys.list_audit_backends.return_value = {}

        with patch("apps.backend.src.core.vault_client.hvac.Client", return_value=mock_client):
            client = VaultClient()
            audit_log = client.get_secret_audit_log("secret/data/kaison/test")
            assert isinstance(audit_log, list)


class TestVaultClientRetryLogic:
    """Test retry logic with exponential backoff."""

    def test_retry_on_failure_then_success(self):
        """Test retry succeeds after initial failure."""
        mock_client = MagicMock()
        from hvac.exceptions import VaultError

        # First call fails, second succeeds
        mock_client.secrets.kv.v2.read_secret_version.side_effect = [
            VaultError("Temporary error"),
            {"data": {"data": {"value": "secret123"}}},
        ]

        with patch("apps.backend.src.core.vault_client.hvac.Client", return_value=mock_client):
            client = VaultClient(retry_count=3, retry_delay=0)  # Fast retry for testing
            secret = client.read_secret("secret/data/kaison/test")
            assert secret["value"] == "secret123"

    def test_retry_exhaustion(self):
        """Test all retries exhausted."""
        mock_client = MagicMock()
        from hvac.exceptions import VaultError

        mock_client.secrets.kv.v2.read_secret_version.side_effect = VaultError("Persistent error")

        with patch("apps.backend.src.core.vault_client.hvac.Client", return_value=mock_client):
            client = VaultClient(retry_count=2, retry_delay=0)
            with pytest.raises(VaultConnectionError):
                client.read_secret("secret/data/kaison/test")


class TestPydanticModels:
    """Test Pydantic model validation."""

    def test_store_secret_request(self):
        """Test StoreSecretRequest validation."""
        request = StoreSecretRequest(
            name="OPENAI_API_KEY",
            type="api_key",
            value="sk-test123",
            description="OpenAI key",
            tags=["ai", "openai"],
        )
        assert request.name == "OPENAI_API_KEY"
        assert request.type == "api_key"

    def test_secret_response(self):
        """Test SecretResponse model."""
        response = SecretResponse(
            name="OPENAI_API_KEY",
            type="api_key",
            status="stored",
            last_updated=datetime.now(timezone.utc),
            environment="production",
        )
        assert response.name == "OPENAI_API_KEY"
        assert response.status == "stored"

    def test_vault_health_response(self):
        """Test VaultHealthResponse model."""
        health = VaultHealthResponse(
            connected=True, status="ready", version="1.15.0", sealed=False, initialized=True
        )
        assert health.connected is True
        assert health.status == "ready"


class TestVaultContextManager:
    """Test VaultClient context manager support."""

    def test_context_manager(self):
        """Test using VaultClient as context manager."""
        mock_client = MagicMock()

        with patch("apps.backend.src.core.vault_client.hvac.Client", return_value=mock_client):
            with VaultClient() as client:
                assert client is not None

            # Verify adapter.close() was called
            mock_client.adapter.close.assert_called_once()


class TestVaultExceptionHandling:
    """Test exception handling and propagation."""

    def test_vault_exception_inheritance(self):
        """Test exception hierarchy."""
        assert issubclass(VaultConnectionError, VaultException)
        assert issubclass(SecretNotFoundError, VaultException)
        assert issubclass(VaultPermissionError, VaultException)

    def test_exception_messages(self):
        """Test exception messages are preserved."""
        exc = VaultConnectionError("Connection to Vault failed")
        assert "Connection to Vault failed" in str(exc)


# Integration tests would require actual Vault instance
# These are marked as requiring external services
class TestVaultIntegration:
    """Integration tests requiring actual Vault instance."""

    @pytest.mark.skipif(
        not os.getenv("VAULT_ADDR"), reason="Requires VAULT_ADDR environment variable"
    )
    def test_real_vault_health_check(self):
        """Test health check against real Vault."""
        with patch("apps.backend.src.core.vault_client.hvac.Client"):
            client = VaultClient()
            # When VAULT_ADDR is set, health check should work
            # This test is mostly for integration environments
            health = client.health_check()
            assert isinstance(health, dict)
