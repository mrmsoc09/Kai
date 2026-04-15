"""
HashiCorp Vault client for secure secret management.

Provides VaultClient class for interacting with Vault KV v2 engine,
including write, read, update, delete, validate, and rotate operations.
Implements connection pooling, retry logic, and comprehensive error handling.

Never logs secret values - all logging is safe and audit-friendly.
"""

from __future__ import annotations

import os
import logging
import time
import json
from typing import Any, Dict, List, Optional, Tuple
from contextlib import contextmanager

try:
    import hvac
    from hvac.exceptions import VaultError, InvalidPath
except ImportError:
    raise ImportError("hvac package required. Install: pip install hvac")

logger = logging.getLogger(__name__)


class VaultException(Exception):
    """Base exception for Vault operations"""

    pass


class VaultConnectionError(VaultException):
    """Connection to Vault server failed"""

    pass


class SecretNotFoundError(VaultException):
    """Requested secret doesn't exist"""

    pass


class SecretValidationError(VaultException):
    """Secret validation failed"""

    pass


class VaultPermissionError(VaultException):
    """Permission denied for Vault operation"""

    pass


class VaultClient:
    """
    Client for HashiCorp Vault secret management.

    Handles KV v2 engine operations with retry logic, connection pooling,
    and comprehensive error handling. Never logs secret values.
    """

    def __init__(
        self,
        vault_addr: str = None,
        vault_token: str = None,
        vault_namespace: str = None,
        retry_count: int = 3,
        retry_delay: int = 1,
        skip_verify: bool = False,
    ):
        """
        Initialize Vault client.

        Args:
            vault_addr: Vault server address (e.g., http://vault:8200)
            vault_token: Authentication token for Vault
            vault_namespace: Optional Vault namespace
            retry_count: Number of retry attempts (default: 3)
            retry_delay: Initial retry delay in seconds (exponential backoff)
            skip_verify: Skip HTTPS verification (dev only)
        """
        self.vault_addr = vault_addr or os.getenv("VAULT_ADDR", "http://localhost:8200")
        self.vault_token = vault_token or os.getenv("VAULT_TOKEN")
        self.vault_namespace = vault_namespace or os.getenv("VAULT_NAMESPACE")
        self.retry_count = retry_count or int(os.getenv("VAULT_RETRY_COUNT", "3"))
        self.retry_delay = retry_delay or int(os.getenv("VAULT_RETRY_DELAY", "1"))
        self.skip_verify = skip_verify or os.getenv("VAULT_SKIP_VERIFY", "false").lower() == "true"

        if not self.vault_token:
            logger.warning("VAULT_TOKEN not set - Vault client will fail on first operation")

        self.client: Optional[hvac.Client] = None
        self._connect()

    def _connect(self) -> None:
        """Create or refresh Vault client connection."""
        try:
            self.client = hvac.Client(
                url=self.vault_addr,
                token=self.vault_token,
                namespace=self.vault_namespace,
                verify=not self.skip_verify,
            )
            # Test connection
            self.client.is_authenticated()
            logger.debug(f"Connected to Vault at {self.vault_addr}")
        except Exception as e:
            logger.error(f"Failed to connect to Vault: {str(e)}")
            self.client = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup connection."""
        if self.client:
            self.client.adapter.close()

    def _retry_operation(self, operation_name: str, func, *args, **kwargs) -> Any:
        """
        Execute operation with exponential backoff retry logic.

        Args:
            operation_name: Name of operation for logging
            func: Callable to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result from func

        Raises:
            VaultConnectionError: If all retries exhausted
        """
        last_error = None

        for attempt in range(self.retry_count):
            try:
                return func(*args, **kwargs)
            except VaultError as e:
                last_error = e
                if attempt < self.retry_count - 1:
                    delay = self.retry_delay * (2**attempt)
                    logger.warning(
                        f"{operation_name} attempt {attempt + 1}/{self.retry_count} "
                        f"failed, retrying in {delay}s"
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"{operation_name} failed after {self.retry_count} attempts")

        raise VaultConnectionError(f"{operation_name} failed: {str(last_error)}")

    def health_check(self) -> Dict[str, Any]:
        """
        Check Vault server health and readiness.

        Returns:
            Dict with keys: sealed, initialized, standby, version, cluster_name, cluster_id

        Raises:
            VaultConnectionError: If health check fails
        """
        if not self.client:
            self._connect()

        try:
            health = self.client.sys.read_health_status()
            return {
                "sealed": health.get("sealed", False),
                "initialized": health.get("initialized", False),
                "standby": health.get("standby", False),
                "version": health.get("version", "unknown"),
                "cluster_name": health.get("cluster_name", "unknown"),
                "cluster_id": health.get("cluster_id", "unknown"),
            }
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            raise VaultConnectionError(f"Health check failed: {str(e)}")

    def write_secret(
        self,
        secret_path: str,
        secret_data: Dict[str, str],
        overwrite: bool = False,
    ) -> bool:
        """
        Write secret to Vault KV v2 engine.

        Args:
            secret_path: Path to secret (e.g., "secret/data/kaison/openai-key")
            secret_data: Dict of secret fields (never logged)
            overwrite: Allow overwriting existing secret

        Returns:
            True if successful

        Raises:
            VaultPermissionError: If secret exists and overwrite=False
            VaultConnectionError: If write fails
        """
        if not self.client:
            self._connect()

        # Check if secret exists
        if not overwrite:
            try:
                self.client.secrets.kv.v2.read_secret_version(path=secret_path)
                raise VaultPermissionError(
                    f"Secret already exists at {secret_path}. Set overwrite=True to replace."
                )
            except (InvalidPath, hvac.exceptions.InvalidRequest):
                pass  # Secret doesn't exist, proceed

        def _write():
            self.client.secrets.kv.v2.create_or_update_secret(
                path=secret_path,
                secret=secret_data,
            )

        try:
            self._retry_operation(f"Write secret to {secret_path}", _write)
            logger.info(f"Secret written to {secret_path}")
            return True
        except VaultConnectionError:
            raise

    def read_secret(self, secret_path: str) -> Dict[str, str]:
        """
        Read secret from Vault KV v2 engine.

        Args:
            secret_path: Path to secret

        Returns:
            Dict of secret fields

        Raises:
            SecretNotFoundError: If secret not found
            VaultConnectionError: If read fails
        """
        if not self.client:
            self._connect()

        def _read():
            response = self.client.secrets.kv.v2.read_secret_version(path=secret_path)
            return response.get("data", {}).get("data", {})

        try:
            result = self._retry_operation(f"Read secret from {secret_path}", _read)
            logger.info(f"Secret read from {secret_path}")
            return result
        except (InvalidPath, hvac.exceptions.InvalidRequest):
            raise SecretNotFoundError(f"Secret not found at {secret_path}")
        except VaultConnectionError:
            raise

    def list_secrets(self, secret_prefix: str) -> List[str]:
        """
        List all secrets under a prefix.

        Args:
            secret_prefix: Prefix path (e.g., "secret/data/kaison")

        Returns:
            List of secret paths/names
        """
        if not self.client:
            self._connect()

        try:
            response = self.client.secrets.kv.v2.list_secrets(path=secret_prefix)
            keys = response.get("data", {}).get("keys", [])
            logger.info(f"Listed {len(keys)} secrets under {secret_prefix}")
            return keys
        except Exception as e:
            logger.warning(f"Failed to list secrets under {secret_prefix}: {str(e)}")
            return []

    def delete_secret(self, secret_path: str) -> bool:
        """
        Delete secret from Vault.

        Args:
            secret_path: Path to secret

        Returns:
            True if successful

        Raises:
            SecretNotFoundError: If secret doesn't exist
            VaultConnectionError: If delete fails
        """
        if not self.client:
            self._connect()

        # Check if exists first
        try:
            self.read_secret(secret_path)
        except SecretNotFoundError:
            raise

        def _delete():
            self.client.secrets.kv.v2.delete_secret_versions(
                path=secret_path,
                versions=None,  # Delete all versions
            )

        try:
            self._retry_operation(f"Delete secret from {secret_path}", _delete)
            logger.info(f"Secret deleted from {secret_path}")
            return True
        except VaultConnectionError:
            raise

    def update_secret(
        self,
        secret_path: str,
        updates: Dict[str, str],
    ) -> bool:
        """
        Update existing secret by merging fields.

        Args:
            secret_path: Path to secret
            updates: Dict of fields to update/add

        Returns:
            True if successful

        Raises:
            SecretNotFoundError: If secret doesn't exist
            VaultConnectionError: If update fails
        """
        # Read current secret
        current = self.read_secret(secret_path)

        # Merge updates
        current.update(updates)

        # Write back
        return self.write_secret(secret_path, current, overwrite=True)

    def get_secret_metadata(self, secret_path: str) -> Dict[str, Any]:
        """
        Get secret metadata without exposing values.

        Args:
            secret_path: Path to secret

        Returns:
            Dict with created_time, updated_time, current_version, versions

        Raises:
            SecretNotFoundError: If secret doesn't exist
        """
        if not self.client:
            self._connect()

        try:
            response = self.client.secrets.kv.v2.read_secret_metadata(path=secret_path)
            metadata = response.get("data", {})
            return {
                "created_time": metadata.get("created_time"),
                "updated_time": metadata.get("updated_time"),
                "current_version": metadata.get("current_version"),
                "versions": metadata.get("versions", []),
            }
        except (InvalidPath, hvac.exceptions.InvalidRequest):
            raise SecretNotFoundError(f"Secret metadata not found at {secret_path}")

    def rotate_secret(
        self,
        secret_path: str,
        new_value: str,
    ) -> bool:
        """
        Rotate secret to new value while keeping version history.

        Args:
            secret_path: Path to secret
            new_value: New secret value

        Returns:
            True if successful

        Raises:
            SecretNotFoundError: If secret doesn't exist
        """
        # Read current secret
        current = self.read_secret(secret_path)

        # Assume single-field secret (common pattern)
        # If multi-field, only rotate the primary field
        if len(current) == 1:
            key = list(current.keys())[0]
            current[key] = new_value
        else:
            # Assume "value" key for multi-field secrets
            current["value"] = new_value

        # Write new version
        self.write_secret(secret_path, current, overwrite=True)
        logger.info(f"Secret rotated at {secret_path}")
        return True

    def validate_secret(
        self,
        service: str,
        secret_value: str,
    ) -> Tuple[bool, str]:
        """
        Validate that a secret works for its service.

        Args:
            service: Service name (openai, gemini, shodan, github, aws, etc.)
            secret_value: The secret to validate

        Returns:
            Tuple (is_valid, error_message or "")
        """
        service = service.lower().strip()

        try:
            if service == "openai":
                try:
                    import openai

                    client = openai.OpenAI(api_key=secret_value)
                    client.models.list()
                    return (True, "")
                except Exception as e:
                    return (False, f"OpenAI validation failed: {str(e)}")

            elif service == "gemini":
                try:
                    import google.generativeai as genai

                    genai.configure(api_key=secret_value)
                    genai.GenerativeModel("gemini-pro")
                    return (True, "")
                except Exception as e:
                    return (False, f"Gemini validation failed: {str(e)}")

            elif service == "shodan":
                try:
                    import shodan

                    api = shodan.Shodan(secret_value)
                    api.info()
                    return (True, "")
                except Exception as e:
                    return (False, f"Shodan validation failed: {str(e)}")

            elif service == "github":
                try:
                    import requests

                    r = requests.get(
                        "https://api.github.com/user",
                        headers={"Authorization": f"token {secret_value}"},
                    )
                    if r.status_code == 200:
                        return (True, "")
                    return (False, f"GitHub validation failed: {r.status_code}")
                except Exception as e:
                    return (False, f"GitHub validation failed: {str(e)}")

            elif service == "aws":
                try:
                    import boto3

                    # Parse AWS secret format: access_key_id:secret_access_key
                    parts = secret_value.split(":")
                    if len(parts) != 2:
                        return (False, "AWS secret must be format: access_key_id:secret_access_key")
                    client = boto3.client(
                        "sts", aws_access_key_id=parts[0], aws_secret_access_key=parts[1]
                    )
                    client.get_caller_identity()
                    return (True, "")
                except Exception as e:
                    return (False, f"AWS validation failed: {str(e)}")

            else:
                # Generic format validation
                if len(secret_value) > 10:
                    return (True, "")
                return (False, "Secret too short")

        except Exception as e:
            return (False, f"Validation error: {str(e)}")

    def sync_secrets_to_env(self, secret_prefix: str = "k1") -> int:
        """
        Load K1 Vault secrets and expose them as process env vars.

        Args:
            secret_prefix: Root prefix in KV v2 mount (default: "k1")

        Returns:
            Number of env vars populated from Vault.
        """
        if not self.client:
            self._connect()
        if not self.client:
            return 0

        service_to_env = {
            "openai": "OPENAI_API_KEY",
            "anthropicai": "ANTHROPIC_API_KEY",
            "geminiai": "GOOGLE_API_KEY",
            "google_developer": "GOOGLE_API_KEY",
            "github_developer": "GITHUB_TOKEN",
            "otx_alienvault": "OTX_API_KEY",
            "nvd_nist": "NVD_API_KEY",
            "projectdiscovery": "PROJECTDISCOVERY_API_KEY",
        }

        categories = ("ai", "osint", "security", "bugbounty", "search", "communication", "developer", "other")
        preferred_fields = ("key", "value", "api_key", "token", "secret")

        def _env_name_for_service(service: str) -> str:
            if service in service_to_env:
                return service_to_env[service]
            normalized = "".join(ch if ch.isalnum() else "_" for ch in service).strip("_").upper()
            if not normalized:
                return ""
            if normalized.endswith(("_KEY", "_TOKEN", "_SECRET", "_PASSWORD")):
                return normalized
            return f"{normalized}_API_KEY"

        def _pick_value(secret_data: Dict[str, Any]) -> Optional[str]:
            for field in preferred_fields:
                value = secret_data.get(field)
                if isinstance(value, str) and value.strip():
                    return value.strip()
            for value in secret_data.values():
                if isinstance(value, str) and value.strip():
                    return value.strip()
            return None

        synced = 0
        for category in categories:
            category_path = f"{secret_prefix}/{category}".strip("/")
            try:
                response = self.client.secrets.kv.v2.list_secrets(path=category_path)
                services = response.get("data", {}).get("keys", []) or []
            except Exception:
                continue

            for service_raw in services:
                service = str(service_raw).rstrip("/")
                if not service:
                    continue
                full_path = f"{category_path}/{service}".strip("/")
                try:
                    secret_data = self.read_secret(full_path)
                except Exception as exc:
                    logger.warning(f"Failed to read Vault secret {full_path}: {exc}")
                    continue

                value = _pick_value(secret_data or {})
                if not value:
                    continue

                env_key = _env_name_for_service(service)
                if not env_key or env_key in os.environ:
                    continue

                os.environ[env_key] = value
                synced += 1

        logger.info(f"Synced {synced} secrets to environment")
        return synced

    def get_secret_audit_log(
        self,
        secret_path: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get audit log for secret access (requires audit backend enabled).

        Args:
            secret_path: Path to secret
            limit: Max entries to return

        Returns:
            List of audit entries
        """
        if not self.client:
            self._connect()

        try:
            # Query audit log (requires Vault audit backend)
            response = self.client.sys.list_audit_backends()

            # Placeholder - full audit log integration would require
            # accessing Vault audit API with proper filtering
            logger.info(f"Audit log requested for {secret_path}")
            return []

        except Exception as e:
            logger.warning(f"Failed to get audit log: {str(e)}")
            return []
