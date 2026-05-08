"""
Tests for SecretsCacheManager and EncryptedSecretValue.

Coverage:
    - Cache TTL expiration
    - Encryption / decryption round-trip
    - Per-tenant isolation
    - LRU eviction with bytearray wipe
    - Memory safety (wipe() verification)
    - Concurrent access (thread-safe)
    - Observability stats
    - Vault integration via mocked SecretManager
    - Key loading (good key, bad key, missing key → dev fallback)
    - SecretType per-type TTL
    - Dynamic secret lease_duration capping
    - shutdown() wipes all entries
"""
from __future__ import annotations

import os
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from apps.backend.src.core.secrets_cache import (
    EncryptedSecretValue,
    SecretType,
    SecretsCacheManager,
    get_secrets_cache,
    reset_secrets_cache,
    _DEFAULT_TYPE_TTLS,
    _LEASE_SAFETY_MARGIN,
)
from apps.backend.src.core.secret_manager import (
    SecretManager,
    SecretManagerError,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_cache():
    """Reset the singleton before and after each test."""
    reset_secrets_cache()
    yield
    reset_secrets_cache()


@pytest.fixture
def cache():
    return SecretsCacheManager()


@pytest.fixture
def box():
    import nacl.secret
    import nacl.utils
    return nacl.secret.SecretBox(nacl.utils.random(nacl.secret.SecretBox.KEY_SIZE))


# ---------------------------------------------------------------------------
# TestEncryptedSecretValue
# ---------------------------------------------------------------------------

class TestEncryptedSecretValue:
    def test_round_trip(self, box):
        ev = EncryptedSecretValue("s3cr3t!", box, SecretType.API_KEY, time.monotonic() + 60, None)
        assert ev.decrypt() == "s3cr3t!"

    def test_unicode_round_trip(self, box):
        ev = EncryptedSecretValue("pässwörd🔑", box, SecretType.PASSWORD, time.monotonic() + 60, None)
        assert ev.decrypt() == "pässwörd🔑"

    def test_ciphertext_differs_from_plaintext(self, box):
        ev = EncryptedSecretValue("plaintext", box, SecretType.TOKEN, time.monotonic() + 60, None)
        assert b"plaintext" not in bytes(ev._ciphertext_buf)

    def test_is_expired_false(self, box):
        ev = EncryptedSecretValue("v", box, SecretType.API_KEY, time.monotonic() + 60, None)
        assert not ev.is_expired()

    def test_is_expired_true(self, box):
        ev = EncryptedSecretValue("v", box, SecretType.API_KEY, time.monotonic() - 1, None)
        assert ev.is_expired()

    def test_wipe_clears_buffer(self, box):
        ev = EncryptedSecretValue("secret", box, SecretType.API_KEY, time.monotonic() + 60, None)
        original_len = len(ev._ciphertext_buf)
        ev.wipe()
        # Buffer should be empty after wipe
        assert len(ev._ciphertext_buf) == 0
        assert original_len > 0  # sanity: something was actually there

    def test_wipe_overwrites_with_random(self, box):
        ev = EncryptedSecretValue("secret", box, SecretType.API_KEY, time.monotonic() + 60, None)
        original = bytes(ev._ciphertext_buf)
        ev.wipe()
        # After wipe the original bytes should not be retrievable
        assert bytes(ev._ciphertext_buf) != original or len(original) == 0


# ---------------------------------------------------------------------------
# TestSecretsCacheManager — Basic Get/Set
# ---------------------------------------------------------------------------

class TestSecretsCacheGetSet:
    def test_set_then_get(self, cache):
        cache.set("api_key", "abc123", SecretType.API_KEY)
        assert cache.get("api_key") == "abc123"

    def test_miss_returns_none(self, cache):
        assert cache.get("nonexistent") is None

    def test_overwrite_existing(self, cache):
        cache.set("key", "old", SecretType.API_KEY)
        cache.set("key", "new", SecretType.API_KEY)
        assert cache.get("key") == "new"

    def test_empty_string_stores_and_retrieves(self, cache):
        cache.set("empty", "", SecretType.TOKEN)
        assert cache.get("empty") == ""

    def test_long_value(self, cache):
        value = "x" * 10_000
        cache.set("big", value, SecretType.CERTIFICATE)
        assert cache.get("big") == value


# ---------------------------------------------------------------------------
# TestTTLExpiration
# ---------------------------------------------------------------------------

class TestTTLExpiration:
    def test_entry_expires(self, cache):
        cache.set("k", "v", SecretType.API_KEY, ttl=1)
        assert cache.get("k") == "v"
        time.sleep(1.05)
        assert cache.get("k") is None

    def test_entry_not_yet_expired(self, cache):
        cache.set("k", "v", SecretType.API_KEY, ttl=5)
        time.sleep(0.1)
        assert cache.get("k") == "v"

    def test_expired_entry_is_wiped(self, cache):
        cache.set("k", "v", SecretType.API_KEY, ttl=1)
        time.sleep(1.05)
        cache.get("k")  # triggers wipe
        # Entry should be gone from store
        assert "k" not in cache._store

    def test_per_type_default_ttl_applied(self):
        cache = SecretsCacheManager()
        cache.set("pw", "secret", SecretType.PASSWORD)
        entry = cache._store.get("pw")
        expected_expiry = time.monotonic() + _DEFAULT_TYPE_TTLS[SecretType.PASSWORD]
        # Allow 1 second tolerance for test execution time
        assert abs(entry._expires_at - expected_expiry) < 1.0

    def test_explicit_ttl_overrides_type_default(self, cache):
        cache.set("k", "v", SecretType.API_KEY, ttl=999)
        entry = cache._store.get("k")
        expected = time.monotonic() + 999
        assert abs(entry._expires_at - expected) < 1.0

    def test_lease_duration_caps_ttl(self, cache):
        # API_KEY default TTL is 300s; lease_duration=50 → effective=50-30=20
        cache.set("dyn", "v", SecretType.DYNAMIC, lease_duration=50)
        entry = cache._store.get("dyn")
        expected_ttl = 50 - _LEASE_SAFETY_MARGIN
        expected_expiry = time.monotonic() + expected_ttl
        assert abs(entry._expires_at - expected_expiry) < 1.0

    def test_lease_duration_minimum_one_second(self, cache):
        # lease_duration smaller than safety margin → capped to 1s, not 0 or negative
        cache.set("dyn", "v", SecretType.DYNAMIC, lease_duration=10)
        entry = cache._store.get("dyn")
        # max(10-30, 1) = 1
        expected_ttl = 1
        expected_expiry = time.monotonic() + expected_ttl
        assert abs(entry._expires_at - expected_expiry) < 1.0

    def test_lease_longer_than_type_ttl_uses_type_ttl(self, cache):
        # API_KEY TTL=300, lease=10000 → min(300, 10000-30)=300
        cache.set("k", "v", SecretType.API_KEY, lease_duration=10000)
        entry = cache._store.get("k")
        expected_expiry = time.monotonic() + _DEFAULT_TYPE_TTLS[SecretType.API_KEY]
        assert abs(entry._expires_at - expected_expiry) < 1.0


# ---------------------------------------------------------------------------
# TestPerTenantIsolation
# ---------------------------------------------------------------------------

class TestPerTenantIsolation:
    def test_different_tenants_isolated(self, cache):
        cache.set("key", "tenant-a-val", SecretType.API_KEY, tenant_id="tenant-a")
        cache.set("key", "tenant-b-val", SecretType.API_KEY, tenant_id="tenant-b")
        assert cache.get("key", tenant_id="tenant-a") == "tenant-a-val"
        assert cache.get("key", tenant_id="tenant-b") == "tenant-b-val"

    def test_no_tenant_does_not_see_tenant_entry(self, cache):
        cache.set("key", "tenant-val", SecretType.API_KEY, tenant_id="org-1")
        assert cache.get("key") is None

    def test_invalidate_tenant_removes_only_that_tenant(self, cache):
        cache.set("key", "a", SecretType.API_KEY, tenant_id="a")
        cache.set("key", "b", SecretType.API_KEY, tenant_id="b")
        cache.invalidate_tenant("a")
        assert cache.get("key", tenant_id="a") is None
        assert cache.get("key", tenant_id="b") == "b"

    def test_invalidate_tenant_wipes_all_keys_for_tenant(self, cache):
        for i in range(5):
            cache.set(f"key{i}", f"val{i}", SecretType.API_KEY, tenant_id="victim")
        cache.set("safe", "stays", SecretType.API_KEY, tenant_id="safe")
        cache.invalidate_tenant("victim")
        for i in range(5):
            assert cache.get(f"key{i}", tenant_id="victim") is None
        assert cache.get("safe", tenant_id="safe") == "stays"


# ---------------------------------------------------------------------------
# TestLRUEviction
# ---------------------------------------------------------------------------

class TestLRUEviction:
    def test_evicts_when_full(self):
        cache = SecretsCacheManager(max_size=3)
        cache.set("a", "1", SecretType.API_KEY)
        cache.set("b", "2", SecretType.API_KEY)
        cache.set("c", "3", SecretType.API_KEY)
        cache.set("d", "4", SecretType.API_KEY)  # triggers eviction of "a"
        assert cache.get("a") is None
        assert cache.get("b") == "2"
        assert cache.get("c") == "3"
        assert cache.get("d") == "4"

    def test_access_prevents_eviction(self):
        cache = SecretsCacheManager(max_size=3)
        cache.set("a", "1", SecretType.API_KEY)
        cache.set("b", "2", SecretType.API_KEY)
        cache.set("c", "3", SecretType.API_KEY)
        cache.get("a")  # promotes "a" to MRU
        cache.set("d", "4", SecretType.API_KEY)  # should evict "b" (LRU now)
        assert cache.get("a") == "1"
        assert cache.get("b") is None
        assert cache.get("c") == "3"
        assert cache.get("d") == "4"

    def test_eviction_count_increments(self):
        cache = SecretsCacheManager(max_size=2)
        cache.set("a", "1", SecretType.API_KEY)
        cache.set("b", "2", SecretType.API_KEY)
        assert cache.stats["evictions"] == 0
        cache.set("c", "3", SecretType.API_KEY)
        assert cache.stats["evictions"] == 1

    def test_evicted_entry_buffer_wiped(self):
        cache = SecretsCacheManager(max_size=1)
        cache.set("a", "first", SecretType.API_KEY)
        evicted_entry = cache._store.get("a")
        cache.set("b", "second", SecretType.API_KEY)
        # After eviction, "a"'s buffer should be cleared
        assert len(evicted_entry._ciphertext_buf) == 0


# ---------------------------------------------------------------------------
# TestMemorySafety
# ---------------------------------------------------------------------------

class TestMemorySafety:
    def test_invalidate_wipes_buffer(self, cache):
        cache.set("k", "sensitive", SecretType.PASSWORD)
        entry = cache._store.get("k")
        cache.invalidate("k")
        assert len(entry._ciphertext_buf) == 0

    def test_overwrite_wipes_old_entry(self, cache):
        cache.set("k", "old-value", SecretType.API_KEY)
        old_entry = cache._store.get("k")
        cache.set("k", "new-value", SecretType.API_KEY)
        assert len(old_entry._ciphertext_buf) == 0

    def test_shutdown_wipes_all(self, cache):
        cache.set("a", "1", SecretType.API_KEY)
        cache.set("b", "2", SecretType.API_KEY)
        entries = list(cache._store.values())
        cache.shutdown()
        for entry in entries:
            assert len(entry._ciphertext_buf) == 0
        assert len(cache._store) == 0

    def test_wipe_count_tracks_all_wipes(self):
        cache = SecretsCacheManager(max_size=2)
        cache.set("a", "1", SecretType.API_KEY)
        cache.set("b", "2", SecretType.API_KEY)
        cache.set("c", "3", SecretType.API_KEY)  # evicts "a" → wipe
        cache.invalidate("b")                     # explicit → wipe
        cache.set("d", "4", SecretType.API_KEY)
        cache.set("d", "5", SecretType.API_KEY)  # overwrite → wipe
        assert cache.stats["wipes"] >= 3

    def test_expired_entry_wiped_on_access(self, cache):
        cache.set("k", "v", SecretType.API_KEY, ttl=1)
        entry = cache._store.get("k")
        time.sleep(1.05)
        cache.get("k")  # triggers expired wipe
        assert len(entry._ciphertext_buf) == 0

    def test_invalidate_all_wipes_everything(self, cache):
        for i in range(5):
            cache.set(f"k{i}", f"v{i}", SecretType.API_KEY)
        entries = list(cache._store.values())
        cache.invalidate_all()
        for entry in entries:
            assert len(entry._ciphertext_buf) == 0
        assert len(cache._store) == 0


# ---------------------------------------------------------------------------
# TestConcurrentAccess
# ---------------------------------------------------------------------------

class TestConcurrentAccess:
    def test_concurrent_reads_are_safe(self, cache):
        cache.set("shared", "value", SecretType.API_KEY)
        errors = []

        def reader():
            try:
                for _ in range(100):
                    result = cache.get("shared")
                    assert result == "value"
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=reader) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == [], f"Concurrent read errors: {errors}"

    def test_concurrent_writes_are_safe(self, cache):
        errors = []

        def writer(i: int):
            try:
                for j in range(50):
                    cache.set(f"key-{i}-{j}", f"val-{i}-{j}", SecretType.API_KEY)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == [], f"Concurrent write errors: {errors}"

    def test_concurrent_mixed_ops(self, cache):
        """Simultaneous gets, sets, and invalidations do not corrupt state."""
        errors = []

        def mixed(i: int):
            try:
                for j in range(30):
                    cache.set(f"k{i}", f"v{j}", SecretType.API_KEY)
                    cache.get(f"k{i}")
                    if j % 5 == 0:
                        cache.invalidate(f"k{i}")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=mixed, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == [], f"Mixed concurrent op errors: {errors}"

    def test_concurrent_lru_eviction_safe(self):
        cache = SecretsCacheManager(max_size=10)
        errors = []

        def filler(offset: int):
            try:
                for i in range(20):
                    cache.set(f"key-{offset}-{i}", f"val-{i}", SecretType.API_KEY)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=filler, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == [], f"Concurrent eviction errors: {errors}"
        assert len(cache._store) <= 10


# ---------------------------------------------------------------------------
# TestObservability
# ---------------------------------------------------------------------------

class TestObservability:
    def test_hit_increments(self, cache):
        cache.set("k", "v", SecretType.API_KEY)
        cache.get("k")
        cache.get("k")
        assert cache.stats["hits"] == 2

    def test_miss_increments(self, cache):
        cache.get("nope")
        cache.get("also-nope")
        assert cache.stats["misses"] == 2

    def test_hit_rate_correct(self, cache):
        cache.set("k", "v", SecretType.API_KEY)
        cache.get("k")        # hit
        cache.get("missing")  # miss
        assert cache.stats["hit_rate"] == 0.5

    def test_hit_rate_zero_on_no_calls(self, cache):
        assert cache.stats["hit_rate"] == 0.0

    def test_size_reflects_store(self, cache):
        assert cache.stats["size"] == 0
        cache.set("a", "1", SecretType.API_KEY)
        cache.set("b", "2", SecretType.API_KEY)
        assert cache.stats["size"] == 2
        cache.invalidate("a")
        assert cache.stats["size"] == 1

    def test_log_stats_does_not_raise(self, cache, caplog):
        import logging
        cache.set("k", "v", SecretType.API_KEY)
        cache.get("k")
        with caplog.at_level(logging.INFO, logger="apps.backend.src.core.secrets_cache"):
            cache.log_stats()
        assert any("hit_rate" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# TestKeyLoading
# ---------------------------------------------------------------------------

class TestKeyLoading:
    def test_valid_32_byte_key(self, monkeypatch):
        key_hex = "a" * 64  # 32 bytes
        monkeypatch.setenv("SECRETS_CACHE_KEY_HEX", key_hex)
        cache = SecretsCacheManager()
        cache.set("k", "v", SecretType.API_KEY)
        assert cache.get("k") == "v"

    def test_invalid_key_length_raises(self, monkeypatch):
        monkeypatch.setenv("SECRETS_CACHE_KEY_HEX", "abcd1234")  # only 4 bytes
        with pytest.raises(ValueError, match="32 bytes"):
            SecretsCacheManager()

    def test_non_hex_key_raises(self, monkeypatch):
        monkeypatch.setenv("SECRETS_CACHE_KEY_HEX", "g" * 64)  # invalid hex
        with pytest.raises(ValueError, match="not valid hex"):
            SecretsCacheManager()

    def test_missing_key_uses_dev_fallback(self, monkeypatch, caplog):
        import logging
        monkeypatch.delenv("SECRETS_CACHE_KEY_HEX", raising=False)
        with caplog.at_level(logging.WARNING, logger="apps.backend.src.core.secrets_cache"):
            cache = SecretsCacheManager()
        assert any("dev-only" in r.message for r in caplog.records)
        # Dev key still works for encrypt/decrypt
        cache.set("k", "v", SecretType.API_KEY)
        assert cache.get("k") == "v"


# ---------------------------------------------------------------------------
# TestSingleton
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_get_secrets_cache_returns_same_instance(self):
        c1 = get_secrets_cache()
        c2 = get_secrets_cache()
        assert c1 is c2

    def test_reset_clears_singleton(self):
        c1 = get_secrets_cache()
        reset_secrets_cache()
        c2 = get_secrets_cache()
        assert c1 is not c2

    def test_reset_wipes_existing_data(self):
        c1 = get_secrets_cache()
        c1.set("k", "v", SecretType.API_KEY)
        entry = c1._store.get("k")
        reset_secrets_cache()
        # entry should be wiped by shutdown() called in reset
        assert len(entry._ciphertext_buf) == 0


# ---------------------------------------------------------------------------
# TestSecretManagerIntegration
# ---------------------------------------------------------------------------

class TestSecretManagerIntegration:
    """Mock-Vault tests exercising the SecretManager → SecretsCacheManager path."""

    def _make_manager(self, monkeypatch) -> SecretManager:
        monkeypatch.setenv("K1_SECRET_BACKEND", "env")
        monkeypatch.setenv("ENVIRONMENT", "test")
        return SecretManager()

    def test_get_optional_caches_vault_fetch(self, monkeypatch):
        """Vault results are cached; a second call does not re-hit Vault."""
        monkeypatch.setenv("K1_SECRET_BACKEND", "env")
        monkeypatch.setenv("ENVIRONMENT", "test")
        mgr = SecretManager()

        # Inject a mock Vault provider (get_secret_with_lease returns (value, lease_duration))
        mock_vault = MagicMock()
        mock_vault.get_secret_with_lease.return_value = ("vault-value", None)
        mgr._vault_provider = mock_vault

        v1 = mgr.get_optional("MY_KEY")
        v2 = mgr.get_optional("MY_KEY")  # should hit cache, not Vault
        assert v1 == "vault-value"
        assert v2 == "vault-value"
        assert mock_vault.get_secret_with_lease.call_count == 1  # only fetched once

    def test_get_required_raises_on_missing(self, monkeypatch):
        monkeypatch.setenv("K1_SECRET_BACKEND", "env")
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.delenv("ABSENT_KEY", raising=False)
        mgr = SecretManager()
        with pytest.raises(SecretManagerError, match="required secret missing"):
            mgr.get_required("ABSENT_KEY")

    def test_cache_stats_accessible(self, monkeypatch):
        monkeypatch.setenv("K1_SECRET_BACKEND", "env")
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.setenv("STAT_KEY", "val")
        mgr = SecretManager()
        mgr.get_optional("STAT_KEY")
        stats = mgr.cache_stats()
        assert "hit_rate" in stats
        assert "hits" in stats

    def test_invalidate_forces_re_fetch_from_vault(self, monkeypatch):
        """After invalidation, the next get re-fetches from Vault."""
        monkeypatch.setenv("K1_SECRET_BACKEND", "env")
        monkeypatch.setenv("ENVIRONMENT", "test")
        mgr = SecretManager()

        mock_vault = MagicMock()
        mock_vault.get_secret_with_lease.side_effect = [("original", None), ("rotated", None)]
        mgr._vault_provider = mock_vault

        assert mgr.get_optional("ROT_KEY") == "original"
        # Cache serves stale value without invalidation
        assert mgr.get_optional("ROT_KEY") == "original"
        assert mock_vault.get_secret_with_lease.call_count == 1

        mgr.invalidate("ROT_KEY")
        assert mgr.get_optional("ROT_KEY") == "rotated"
        assert mock_vault.get_secret_with_lease.call_count == 2

    def test_tenant_isolation_via_secret_manager(self, monkeypatch):
        monkeypatch.setenv("K1_SECRET_BACKEND", "env")
        monkeypatch.setenv("ENVIRONMENT", "test")
        monkeypatch.setenv("SHARED_KEY", "global")
        mgr = SecretManager()
        mgr._cache().set("SHARED_KEY", "tenant-a", SecretType.API_KEY, tenant_id="a")
        assert mgr.get_optional("SHARED_KEY", tenant_id="a") == "tenant-a"
        assert mgr.get_optional("SHARED_KEY") == "global"  # no tenant → miss → env

    def test_invalidate_tenant(self, monkeypatch):
        monkeypatch.setenv("K1_SECRET_BACKEND", "env")
        monkeypatch.setenv("ENVIRONMENT", "test")
        mgr = SecretManager()
        mgr._cache().set("k1", "v1", SecretType.API_KEY, tenant_id="evict-me")
        mgr._cache().set("k2", "v2", SecretType.API_KEY, tenant_id="evict-me")
        mgr._cache().set("safe", "ok", SecretType.API_KEY, tenant_id="keep")
        mgr.invalidate_tenant("evict-me")
        assert mgr._cache().get("k1", tenant_id="evict-me") is None
        assert mgr._cache().get("k2", tenant_id="evict-me") is None
        assert mgr._cache().get("safe", tenant_id="keep") == "ok"
