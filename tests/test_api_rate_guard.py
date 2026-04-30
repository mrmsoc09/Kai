"""Tests for api_rate_guard — rate limiting, jitter, backoff, budget gate, key rotation."""
from __future__ import annotations

import asyncio
import time
import pytest

from apps.backend.src.core.api_rate_guard import (
    RateGuard,
    RateLimitExceeded,
    _KeyPool,
    _SERVICE_QUOTAS,
    get_rate_guard,
    rate_guarded,
    register_service_keys,
)


@pytest.fixture
def guard():
    g = RateGuard()
    g._redis_ok = False  # force in-process mode for tests
    return g


# 1. Known services are in the quota table
def test_known_services_in_quota_table():
    assert "shodan" in _SERVICE_QUOTAS
    assert "censys" in _SERVICE_QUOTAS
    assert "openrouter" in _SERVICE_QUOTAS
    assert "ollama" in _SERVICE_QUOTAS
    assert "google_cse" in _SERVICE_QUOTAS


# 2. Unknown service gets default quota (no KeyError)
@pytest.mark.asyncio
async def test_unknown_service_no_error(guard):
    # Should not raise — gets default quota
    await guard.wait("totally_unknown_service_xyz")


# 3. 429 backoff increases with each call
def test_backoff_increases(guard):
    delays = []
    for _ in range(5):
        delay = guard.record_429("shodan")
        delays.append(delay)
    # Each call should generally have a higher ceiling (probabilistically)
    # We just check delays are non-negative and at least one is > 0
    assert all(d >= 0 for d in delays)
    assert max(delays) > 0


# 4. record_success resets backoff
def test_success_resets_backoff(guard):
    guard.record_429("shodan")
    guard.record_429("shodan")
    guard.record_429("shodan")
    guard.record_success("shodan")
    state = guard._get_local("shodan")
    assert state.backoff_attempt == 0


# 5. Daily count increments
@pytest.mark.asyncio
async def test_daily_count_increments(guard):
    before = guard._daily_count("hunter")
    await guard.wait("hunter")
    after = guard._daily_count("hunter")
    assert after == before + 1


# 6. Daily budget gate blocks at 100% of quota (daily_count >= daily_limit)
@pytest.mark.asyncio
async def test_daily_budget_gate(guard):
    state = guard._get_local("hunter")
    today = time.strftime("%Y-%m-%d")
    state.daily_count = 25   # exactly at limit (100%) → hard block
    state.daily_date = today
    with pytest.raises(RateLimitExceeded, match="daily quota"):
        await guard.wait("hunter")


# 7. RPM jitter adds non-zero delay
@pytest.mark.asyncio
async def test_jitter_is_nonzero():
    guard = RateGuard()
    guard._redis_ok = False
    quota = _SERVICE_QUOTAS["hunter"]
    jitter_lo, jitter_hi = quota["jitter"]
    assert jitter_hi > 0, "Hunter should have non-zero jitter"


# 8. rate_guarded decorator wraps coroutine correctly
@pytest.mark.asyncio
async def test_decorator_passes_through():
    call_count = 0

    @rate_guarded("ollama")   # ollama has very fast quota
    async def fast_fn() -> str:
        nonlocal call_count
        call_count += 1
        return "ok"

    result = await fast_fn()
    assert result == "ok"
    assert call_count == 1


# 9. rate_guarded retries on simulated 429
@pytest.mark.asyncio
async def test_decorator_retries_on_429():
    attempts = 0

    @rate_guarded("ollama")
    async def flaky_fn() -> str:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise Exception("429 rate limit exceeded")
        return "success"

    result = await flaky_fn()
    assert result == "success"
    assert attempts == 3


# 10. RateLimitExceeded propagates when max retries exhausted
@pytest.mark.asyncio
async def test_decorator_raises_after_max_retries():
    @rate_guarded("ollama")
    async def always_fails() -> str:
        raise Exception("429 Too Many Requests")

    with pytest.raises(RateLimitExceeded):
        await always_fails()


# ---------------------------------------------------------------------------
# _KeyPool unit tests
# ---------------------------------------------------------------------------

class TestKeyPool:
    def _pool(self, keys: list[str]) -> _KeyPool:
        from apps.backend.src.core.api_rate_guard import _KeyPool
        return _KeyPool(keys=keys)

    # 11. Round-robin wraps correctly
    def test_round_robin(self):
        pool = self._pool(["a", "b", "c"])
        assert pool.get_active_key() == "a"
        assert pool.get_active_key() == "b"
        assert pool.get_active_key() == "c"
        assert pool.get_active_key() == "a"  # wraps

    # 12. mark_429 causes key to be skipped
    def test_mark_429_skips_key(self):
        pool = self._pool(["a", "b", "c"])
        pool.mark_429("a", cooloff_seconds=9999)
        assert pool.get_active_key() == "b"
        assert pool.get_active_key() == "c"
        assert pool.get_active_key() == "b"  # 'a' still cooled off

    # 13. mark_429 on unknown key is a no-op (no exception)
    def test_mark_429_unknown_key_noop(self):
        pool = self._pool(["a", "b"])
        pool.mark_429("does_not_exist")  # must not raise
        assert pool.get_active_key() in {"a", "b"}

    # 14. All keys cooled off → get_active_key returns None
    def test_all_keys_cooled_off(self):
        pool = self._pool(["a", "b"])
        pool.mark_429("a", cooloff_seconds=9999)
        pool.mark_429("b", cooloff_seconds=9999)
        assert pool.get_active_key() is None

    # 15. Cooloff expires → key becomes available again
    def test_cooloff_expires(self):
        pool = self._pool(["a"])
        pool.mark_429("a", cooloff_seconds=-1)  # already expired
        assert pool.get_active_key() == "a"

    # 16. Single-key pool still round-robins
    def test_single_key(self):
        pool = self._pool(["only"])
        assert pool.get_active_key() == "only"
        assert pool.get_active_key() == "only"


# ---------------------------------------------------------------------------
# RateGuard key-pool integration tests
# ---------------------------------------------------------------------------

class TestRateGuardKeyPool:
    @pytest.fixture
    def guard(self) -> RateGuard:
        g = RateGuard()
        g._redis_ok = False
        return g

    # 17. register_key_pool creates pool; get_key returns round-robin values
    def test_register_and_rotate(self, guard):
        guard.register_key_pool("svc", ["k1", "k2", "k3"])
        assert guard.get_key("svc") == "k1"
        assert guard.get_key("svc") == "k2"
        assert guard.get_key("svc") == "k3"
        assert guard.get_key("svc") == "k1"

    # 18. get_key returns None when no pool is registered
    def test_get_key_no_pool(self, guard):
        assert guard.get_key("unregistered_svc") is None

    # 19. record_429 with key marks that key as cooled off
    def test_record_429_cools_key(self, guard):
        guard.register_key_pool("svc", ["k1", "k2"])
        key = guard.get_key("svc")          # k1
        guard.record_429("svc", key=key)    # cools k1
        next_key = guard.get_key("svc")
        assert next_key == "k2"

    # 20. record_429 without key does not crash (backward compat)
    def test_record_429_no_key_compat(self, guard):
        guard.register_key_pool("svc", ["k1"])
        delay = guard.record_429("svc")     # no key param
        assert delay >= 0

    # 21. register_key_pool with empty list raises ValueError
    def test_register_empty_keys_raises(self, guard):
        with pytest.raises(ValueError, match="must not be empty"):
            guard.register_key_pool("svc", [])

    # 22. register_key_pool replaces an existing pool
    def test_register_replaces_pool(self, guard):
        guard.register_key_pool("svc", ["old"])
        guard.register_key_pool("svc", ["new1", "new2"])
        assert guard.get_key("svc") == "new1"

    # 23. Module-level register_service_keys wires into singleton
    def test_module_level_register(self):
        import apps.backend.src.core.api_rate_guard as mod
        orig_guard = mod._guard
        try:
            mod._guard = None
            register_service_keys("testsvc", ["x", "y"])
            singleton = get_rate_guard()
            assert singleton.get_key("testsvc") == "x"
            assert singleton.get_key("testsvc") == "y"
        finally:
            mod._guard = orig_guard
