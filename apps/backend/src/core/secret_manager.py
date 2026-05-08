from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


class SecretManagerError(RuntimeError):
    """Raised for secret retrieval or configuration failures."""


@dataclass(frozen=True)
class SecretRef:
    name: str
    required: bool = True


class BaseSecretProvider:
    def get_secret(self, name: str) -> Optional[str]:
        raise NotImplementedError


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

    def get_secret(self, name: str) -> Optional[str]:
        path = f"{self.prefix}/{name}" if self.prefix else name
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=self.mount,
            )
        except Exception:
            return None
        data = (response or {}).get("data", {}).get("data", {})
        value = data.get("value")
        if isinstance(value, str) and value.strip():
            return value.strip()
        raw = data.get(name)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
        return None

    def get_secret_hierarchical(
        self, category: str, service: str
    ) -> Optional[str]:
        """Retrieve secret from hierarchical path: k1/{category}/{service}"""
        path = f"k1/{category}/{service}"
        try:
            response = self.client.secrets.kv.v2.read_secret_version(
                path=path,
                mount_point=self.mount,
            )
        except Exception:
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

    def get_optional(self, name: str) -> Optional[str]:
        # Check scan cache before hitting Vault
        try:
            from .scan_cache import get_scan_cache
            cached = get_scan_cache().get("vault", name)
            if cached is not None:
                return cached
        except Exception:
            pass

        if self._vault_provider:
            value = self._vault_provider.get_secret(name)
            if value:
                try:
                    from .scan_cache import get_scan_cache
                    get_scan_cache().set("vault", name, value)
                except Exception:
                    pass
                return value
        if self._allow_env_fallback():
            return self._env_provider.get_secret(name)
        return None

    def get_required(self, name: str) -> str:
        value = self.get_optional(name)
        if not value:
            raise SecretManagerError(f"required secret missing: {name}")
        return value

    def validate_required(self, names: list[str]) -> None:
        missing = [name for name in names if not self.get_optional(name)]
        if missing:
            raise SecretManagerError("required secrets missing: " + ", ".join(missing))

    def get_hierarchical(
        self, category: str, service: str
    ) -> Optional[str]:
        """Retrieve secret from hierarchical path: k1/{category}/{service}

        Example:
            get_hierarchical("ai", "openai") → secret/k1/ai/openai
            get_hierarchical("osint", "shodan") → secret/k1/osint/shodan
        """
        cache_key = f"hier:{category}/{service}"
        try:
            from .scan_cache import get_scan_cache
            cached = get_scan_cache().get("vault", cache_key)
            if cached is not None:
                return cached
        except Exception:
            pass

        value: Optional[str] = None
        if self._vault_provider:
            value = self._vault_provider.get_secret_hierarchical(category, service)
        if not value and self._allow_env_fallback():
            value = self._env_provider.get_secret(f"{service.upper()}_API_KEY")

        if value:
            try:
                from .scan_cache import get_scan_cache
                get_scan_cache().set("vault", cache_key, value)
            except Exception:
                pass
        return value

    def get_hierarchical_required(
        self, category: str, service: str
    ) -> str:
        """Retrieve required secret from hierarchical path."""
        value = self.get_hierarchical(category, service)
        if not value:
            raise SecretManagerError(
                f"required secret missing: k1/{category}/{service}"
            )
        return value


_SECRET_MANAGER: Optional[SecretManager] = None


def get_secret_manager() -> SecretManager:
    global _SECRET_MANAGER
    if _SECRET_MANAGER is None:
        _SECRET_MANAGER = SecretManager()
    return _SECRET_MANAGER
