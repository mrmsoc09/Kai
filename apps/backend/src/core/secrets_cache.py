"""
SecretsCacheManager — encrypted in-memory secrets cache.

Architecture decisions:
- In-process only (not Redis): avoids distributing the encryption key across
  workers; bytearray ciphertext can be overwritten on eviction.
- NaCl SecretBox (XSalsa20-Poly1305): authenticated encryption, no padding
  oracle, well-audited.  Key is 32 bytes from env, never in code.
- bytearray ciphertext: allows os.urandom() wipe on eviction/shutdown.
  Post-decrypt plaintext is a Python str (immutable, interned by the runtime);
  we cannot guarantee its wipe — this is documented below and in the config YAML.
  Defence: minimise time between decrypt() and use; never store the returned str.
- Per-tenant isolation: cache key is prefixed with tenant_id when supplied.
- LRU eviction at max_size=1000 (configurable) prevents memory exhaustion.
- Thread-safe: single threading.Lock guards all store mutations.

Key setup:
    python3 -c "import secrets; print(secrets.token_hex(32))"
    export SECRETS_CACHE_KEY_HEX=<64-char hex>
    # Never commit or log this value.

Missing key: a deterministic dev-only key is derived from a fixed seed.
A warning is emitted — production deployments must set the env var.
"""
from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from collections import OrderedDict
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SecretType enum + per-type TTL configuration
# ---------------------------------------------------------------------------

class SecretType(Enum):
    API_KEY     = "api_key"
    PASSWORD    = "password"
    TOKEN       = "token"
    CERTIFICATE = "certificate"
    DYNAMIC     = "dynamic"   # Vault-leased; TTL capped by lease_duration


# Default TTL per secret type (seconds). Override via SecretsCacheManager(ttl_overrides=...).
_DEFAULT_TYPE_TTLS: dict[SecretType, int] = {
    SecretType.API_KEY:     300,   # 5 min
    SecretType.PASSWORD:    180,   # 3 min — higher risk, shorter window
    SecretType.TOKEN:       300,   # 5 min
    SecretType.CERTIFICATE: 3600,  # 1 hr  — long-lived, expensive to re-fetch
    SecretType.DYNAMIC:      60,   # 1 min — always capped by Vault lease_duration
}

# Safety margin subtracted from Vault lease_duration before using it as TTL.
_LEASE_SAFETY_MARGIN = 30  # seconds


# ---------------------------------------------------------------------------
# EncryptedSecretValue
# ---------------------------------------------------------------------------

class EncryptedSecretValue:
    """
    NaCl-encrypted wrapper for a single secret value stored in the cache.

    The ciphertext is held in a bytearray so wipe() can overwrite it with
    random bytes before deletion, preventing the plaintext from lingering in
    freed heap pages.

    Limitation: decrypt() returns a Python str, which is immutable and may
    be interned.  Callers must use the returned value immediately and not
    assign it to long-lived variables.
    """

    __slots__ = ("_box", "_ciphertext_buf", "_expires_at", "secret_type", "tenant_id")

    def __init__(
        self,
        plaintext: str,
        box: "nacl.secret.SecretBox",
        secret_type: SecretType,
        expires_at: float,
        tenant_id: Optional[str],
    ) -> None:
        self._box = box
        cipher = box.encrypt(plaintext.encode("utf-8"))
        self._ciphertext_buf: bytearray = bytearray(cipher)
        self._expires_at = expires_at
        self.secret_type = secret_type
        self.tenant_id = tenant_id

    def decrypt(self) -> str:
        """Return plaintext.  Use immediately; do not store the result."""
        return self._box.decrypt(bytes(self._ciphertext_buf)).decode("utf-8")

    def is_expired(self) -> bool:
        return time.monotonic() > self._expires_at

    def wipe(self) -> None:
        """Overwrite ciphertext buffer with random bytes, then clear it."""
        n = len(self._ciphertext_buf)
        if n:
            self._ciphertext_buf[:] = os.urandom(n)
        self._ciphertext_buf = bytearray()


# ---------------------------------------------------------------------------
# SecretsCacheManager
# ---------------------------------------------------------------------------

class SecretsCacheManager:
    """
    Encrypted in-memory LRU cache for secrets retrieved from Vault.

    Usage::

        cache = get_secrets_cache()

        # Store
        cache.set("shodan_key", secret_value, SecretType.API_KEY, tenant_id="org-42")

        # Retrieve (returns None on miss or expiry)
        value = cache.get("shodan_key", tenant_id="org-42")
        if value is None:
            value = vault.read(...)
            cache.set("shodan_key", value, SecretType.API_KEY, tenant_id="org-42")

        # Observe
        print(cache.stats)

        # Shutdown (wipe all)
        cache.shutdown()
    """

    def __init__(
        self,
        max_size: int = 1000,
        ttl_overrides: Optional[dict[SecretType, int]] = None,
    ) -> None:
        self._box = self._load_box()
        self._store: OrderedDict[str, EncryptedSecretValue] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.Lock()
        self._ttls = dict(_DEFAULT_TYPE_TTLS)
        if ttl_overrides:
            self._ttls.update(ttl_overrides)

        # Observability counters
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._wipes = 0

    # ------------------------------------------------------------------
    # Key derivation
    # ------------------------------------------------------------------

    @staticmethod
    def _load_box() -> "nacl.secret.SecretBox":
        import nacl.secret  # type: ignore

        key_hex = os.environ.get("SECRETS_CACHE_KEY_HEX", "").strip()
        if key_hex:
            try:
                key = bytes.fromhex(key_hex)
            except ValueError as exc:
                raise ValueError("SECRETS_CACHE_KEY_HEX is not valid hex") from exc
            if len(key) != nacl.secret.SecretBox.KEY_SIZE:
                raise ValueError(
                    f"SECRETS_CACHE_KEY_HEX must encode exactly "
                    f"{nacl.secret.SecretBox.KEY_SIZE} bytes "
                    f"({nacl.secret.SecretBox.KEY_SIZE * 2} hex chars)"
                )
        else:
            logger.warning(
                "SECRETS_CACHE_KEY_HEX not set — using dev-only derivation. "
                "Set this env var in production."
            )
            key = hashlib.sha256(b"kai-dev-secrets-cache-not-for-production").digest()

        return nacl.secret.SecretBox(key)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(name: str, tenant_id: Optional[str]) -> str:
        if tenant_id:
            return f"{tenant_id}:{name}"
        return name

    def _evict_lru(self) -> None:
        """Evict the least-recently-used entry (must be called under lock)."""
        if not self._store:
            return
        key, entry = next(iter(self._store.items()))
        entry.wipe()
        del self._store[key]
        self._evictions += 1
        self._wipes += 1
        logger.debug("secrets_cache: LRU eviction key=%s", key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get(self, name: str, tenant_id: Optional[str] = None) -> Optional[str]:
        """
        Return decrypted secret or None on cache miss / expiry.

        On expiry the entry is wiped and removed; the caller should re-fetch
        from Vault and call set().
        """
        key = self._make_key(name, tenant_id)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry.is_expired():
                entry.wipe()
                del self._store[key]
                self._misses += 1
                self._wipes += 1
                logger.debug("secrets_cache: TTL expired key=%s", key)
                return None
            # LRU: move to end (most-recently used)
            self._store.move_to_end(key)
            self._hits += 1
            return entry.decrypt()

    def set(
        self,
        name: str,
        value: str,
        secret_type: SecretType = SecretType.API_KEY,
        tenant_id: Optional[str] = None,
        ttl: Optional[int] = None,
        lease_duration: Optional[int] = None,
    ) -> None:
        """
        Encrypt and store *value*.

        TTL precedence:
        1. Explicit *ttl* argument (caller override).
        2. *lease_duration* from Vault (minus safety margin), capped by type TTL.
        3. Per-type default from _DEFAULT_TYPE_TTLS.

        For DYNAMIC secrets, lease_duration should always be provided.
        """
        effective_ttl = ttl if ttl is not None else self._ttls[secret_type]
        if lease_duration is not None:
            lease_ttl = max(lease_duration - _LEASE_SAFETY_MARGIN, 1)
            effective_ttl = min(effective_ttl, lease_ttl)

        key = self._make_key(name, tenant_id)
        expires_at = time.monotonic() + effective_ttl

        with self._lock:
            # Wipe any existing entry before replacing
            existing = self._store.pop(key, None)
            if existing is not None:
                existing.wipe()
                self._wipes += 1

            # Enforce size limit before inserting
            while len(self._store) >= self._max_size:
                self._evict_lru()

            self._store[key] = EncryptedSecretValue(
                value, self._box, secret_type, expires_at, tenant_id
            )
            self._store.move_to_end(key)

    def invalidate(self, name: str, tenant_id: Optional[str] = None) -> None:
        """Remove and wipe a single cache entry."""
        key = self._make_key(name, tenant_id)
        with self._lock:
            entry = self._store.pop(key, None)
            if entry is not None:
                entry.wipe()
                self._wipes += 1

    def invalidate_tenant(self, tenant_id: str) -> None:
        """Remove and wipe all entries belonging to *tenant_id*."""
        prefix = f"{tenant_id}:"
        with self._lock:
            keys = [k for k in self._store if k.startswith(prefix)]
            for k in keys:
                self._store[k].wipe()
                self._wipes += 1
                del self._store[k]
        logger.info("secrets_cache: invalidated %d entries for tenant %s", len(keys), tenant_id)

    def invalidate_all(self) -> None:
        """Wipe every cached entry (e.g. after Vault token refresh)."""
        with self._lock:
            for entry in self._store.values():
                entry.wipe()
                self._wipes += 1
            self._store.clear()
        logger.info("secrets_cache: full invalidation complete")

    def shutdown(self) -> None:
        """Overwrite and discard all cached secrets (call at process exit)."""
        with self._lock:
            n = len(self._store)
            for entry in self._store.values():
                entry.wipe()
                self._wipes += 1
            self._store.clear()
        logger.info("secrets_cache: shutdown wiped %d entries", n)

    # ------------------------------------------------------------------
    # Observability
    # ------------------------------------------------------------------

    @property
    def stats(self) -> dict:
        """Return a snapshot of cache observability metrics."""
        with self._lock:
            size = len(self._store)
            total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(self._hits / total, 4) if total else 0.0,
            "evictions": self._evictions,
            "wipes": self._wipes,
            "size": size,
            "max_size": self._max_size,
        }

    def log_stats(self) -> None:
        """Emit cache statistics at INFO level for observability pipelines."""
        s = self.stats
        logger.info(
            "secrets_cache stats: size=%d/%d hits=%d misses=%d hit_rate=%.2f%% "
            "evictions=%d wipes=%d",
            s["size"], s["max_size"],
            s["hits"], s["misses"], s["hit_rate"] * 100,
            s["evictions"], s["wipes"],
        )


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_CACHE: Optional[SecretsCacheManager] = None
_CACHE_LOCK = threading.Lock()


def get_secrets_cache() -> SecretsCacheManager:
    """Return the process-level SecretsCacheManager singleton."""
    global _CACHE
    if _CACHE is None:
        with _CACHE_LOCK:
            if _CACHE is None:
                _CACHE = SecretsCacheManager()
    return _CACHE


def reset_secrets_cache() -> None:
    """Shutdown and discard the singleton (for tests and hot-reload)."""
    global _CACHE
    with _CACHE_LOCK:
        if _CACHE is not None:
            _CACHE.shutdown()
            _CACHE = None
