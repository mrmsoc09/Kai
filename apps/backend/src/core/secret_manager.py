from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Optional

from .secrets_cache import SecretType, SecretsCacheManager, get_secrets_cache

logger = logging.getLogger(__name__)


class SecretManagerError(RuntimeError):
    """Raised for secret retrieval or configuration failures."""


@dataclass(frozen=True)
class SecretRef:
    name: str
    required: bool = True


class BaseSecretProvider:
    def get_secret(self, name: str) -> Optional[str]:
        raise NotImplementedError

    def get_secret_with_lease(self, name: str) -> tuple[Optional[str], Optional[int]]:
        """Return (value, lease_duration_seconds). Default delegates to get_secret."""
        return self.get_secret(name), None


class EnvSecretProvider(BaseSecretProvider):
    def get_secret(self, name: str) -> Optional[str]:
        value = os.getenv(name)
        if value is None:
            return None
        value = value.strip()
        return value or None


class VaultSecretProvider(BaseSecretProvider):
    def __init__(self) -> None:
        self.addr = (os.getenv("VAULT_ADDR") or "").strip()
        self.token = (os.getenv("VAULT_TOKEN") or "").strip()
        self.namespace = (os.getenv("VAULT_NAMESPACE") or "").strip() or None
        self.mount = (os.getenv("VAULT_MOUNT_POINT") or "secret").strip()
        self.prefix = (os.getenv("VAULT_SECRET_PREFIX") or "kai").strip().strip("/")

        if not self.addr:
            raise SecretManagerError("VAULT_ADDR missing")
        if not self.token:
            raise SecretManagerError("VAULT_TOKEN missing")

        try:
            import hvac  # type: ignore
        except Exception as exc:  # pragma: no cover - dependency issue
            raise SecretManagerError("hvac not installed") from exc

        kwargs = {"url": self.addr, "token": self.token}
        if self.namespace:
            kwargs["namespace"] = self.namespace
        self.client = hvac.Client(**kwargs)
        try:
            if not self.client.is_authenticated():
                raise SecretManagerError("Vault authentication failed")
        except SecretManagerError:
            raise
        except Exception as exc:
            raise SecretManagerError("Vault authentication check failed") from exc

    def _get_with_retry(self, path: str) -> Optional[dict]:
        """Fetch a KV-v2 secret with exponential backoff (3 attempts: 1s, 2s delays)."""
        import time as _time
        for attempt in range(3):
            try:
                return self.client.secrets.kv.v2.read_secret_version(
                    path=path,
                    mount_point=self.mount,
                )
            except Exception:
                if attempt < 2:
                    _time.sleep(2 ** attempt)
        return None

    def get_secret(self, name: str) -> Optional[str]:
        path = f"{self.prefix}/{name}" if self.prefix else name
        response = self._get_with_retry(path)
        if response is None:
            return None
        data = (response or {}).get("data", {}).get("data", {})
        value = data.get("value")
        if isinstance(value, str) and value.strip():
            return value.strip()
        raw = data.get(name)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        return None

    def get_secret_with_lease(self, name: str) -> tuple[Optional[str], Optional[int]]:
        """Return (value, lease_duration) for dynamic-secret TTL capping."""
        path = f"{self.prefix}/{name}" if self.prefix else name
        response = self._get_with_retry(path)
        if response is None:
            return None, None
        lease_duration: Optional[int] = response.get("lease_duration")
        data = (response or {}).get("data", {}).get("data", {})
        value = data.get("value")
        if isinstance(value, str) and value.strip():
            return value.strip(), lease_duration
        raw = data.get(name)
        if isinstance(raw, str) and raw.strip():
            return raw.strip(), lease_duration
        return None, None

    def get_secret_hierarchical(
        self, category: str, service: str
    ) -> Optional[str]:
        """Retrieve secret from hierarchical path: k1/{category}/{service}"""
        path = f"k1/{category}/{service}"
        response = self._get_with_retry(path)
        if response is None:
            return None
        data = (response or {}).get("data", {}).get("data", {})
        value = data.get("value")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class SecretManager:
    """
    Vault-primary secret manager with environment fallback for development only.
    """

    def __init__(self) -> None:
        self.env_name = (os.getenv("ENVIRONMENT") or "").strip().lower()
        default_backend = "env" if self.env_name in {"dev", "development", "test"} else "vault"
        self.backend = (os.getenv("K1_SECRET_BACKEND") or default_backend).strip().lower()
        self._env_provider = EnvSecretProvider()
        self._vault_provider: Optional[VaultSecretProvider] = None

        if self.backend == "vault":
            try:
                self._vault_provider = VaultSecretProvider()
            except Exception as exc:
                if self._allow_env_fallback():
                    self._vault_provider = None
                else:
                    raise SecretManagerError(
                        f"vault backend initialization failed: {exc}"
                    ) from exc
        elif self.backend != "env":
            raise SecretManagerError(f"unsupported secret backend: {self.backend}")

    def _allow_env_fallback(self) -> bool:
        if self.backend == "env":
            return True
        if _env_bool("K1_ALLOW_ENV_SECRETS", False):
            return True
        return self.env_name in {"dev", "development", "test"}

    def _cache(self) -> SecretsCacheManager:
        return get_secrets_cache()

    def get_optional(
        self, name: str, tenant_id: Optional[str] = None
    ) -> Optional[str]:
        """Return secret value or None.

        Checks the encrypted in-memory cache first; on miss fetches from Vault
        (or env fallback) and stores the result with the API_KEY TTL.

        Args:
            name: Secret name / path.
            tenant_id: Optional tenant scope for cache isolation.
        """
        cached = self._cache().get(name, tenant_id=tenant_id)
        if cached is not None:
            logger.debug("secrets_cache hit: %s (tenant=%s)", name, tenant_id)
            return cached

        if self._vault_provider:
            value, lease_duration = self._vault_provider.get_secret_with_lease(name)
            if value:
                self._cache().set(
                    name, value, SecretType.API_KEY,
                    tenant_id=tenant_id, lease_duration=lease_duration,
                )
                return value
        if self._allow_env_fallback():
            return self._env_provider.get_secret(name)
        return None

    def get_required(
        self, name: str, tenant_id: Optional[str] = None
    ) -> str:
        """Return secret value; raise SecretManagerError if missing."""
        value = self.get_optional(name, tenant_id=tenant_id)
        if not value:
            raise SecretManagerError(f"required secret missing: {name}")
        return value

    def validate_required(
        self, names: list[str], tenant_id: Optional[str] = None
    ) -> None:
        missing = [n for n in names if not self.get_optional(n, tenant_id=tenant_id)]
        if missing:
            raise SecretManagerError("required secrets missing: " + ", ".join(missing))

    def get_hierarchical(
        self,
        category: str,
        service: str,
        tenant_id: Optional[str] = None,
    ) -> Optional[str]:
        """Retrieve secret from hierarchical Vault path: k1/{category}/{service}.

        Example:
            get_hierarchical("ai", "openai") → secret/k1/ai/openai
            get_hierarchical("osint", "shodan") → secret/k1/osint/shodan
        """
        cache_key = f"hier:{category}/{service}"
        cached = self._cache().get(cache_key, tenant_id=tenant_id)
        if cached is not None:
            logger.debug(
                "secrets_cache hit: %s/%s (tenant=%s)", category, service, tenant_id
            )
            return cached

        value: Optional[str] = None
        if self._vault_provider:
            value = self._vault_provider.get_secret_hierarchical(category, service)
        if not value and self._allow_env_fallback():
            value = self._env_provider.get_secret(f"{service.upper()}_API_KEY")

        if value:
            self._cache().set(
                cache_key, value, SecretType.API_KEY, tenant_id=tenant_id
            )
        return value

    def get_hierarchical_required(
        self,
        category: str,
        service: str,
        tenant_id: Optional[str] = None,
    ) -> str:
        """Retrieve required secret from hierarchical Vault path."""
        value = self.get_hierarchical(category, service, tenant_id=tenant_id)
        if not value:
            raise SecretManagerError(
                f"required secret missing: k1/{category}/{service}"
            )
        return value

    def invalidate(
        self, name: str, tenant_id: Optional[str] = None
    ) -> None:
        """Evict a single secret from the cache (forces re-fetch on next access)."""
        self._cache().invalidate(name, tenant_id=tenant_id)

    def invalidate_tenant(self, tenant_id: str) -> None:
        """Evict all cached secrets for a tenant (e.g. on tenant offboarding)."""
        self._cache().invalidate_tenant(tenant_id)

    def cache_stats(self) -> dict:
        """Return cache observability metrics (hits, misses, hit_rate, etc.)."""
        return self._cache().stats


_SECRET_MANAGER: Optional[SecretManager] = None


def get_secret_manager() -> SecretManager:
    global _SECRET_MANAGER
    if _SECRET_MANAGER is None:
        _SECRET_MANAGER = SecretManager()
    return _SECRET_MANAGER
