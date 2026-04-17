"""Task 2 validation: Execution Safety Layer."""
from __future__ import annotations

import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "backend", "src"))

from core.execution_safety import (
    ExecutionSafetyConfig,
    ExecutionSafetyLayer,
    ExecutionSafetyError,
    RateLimitExceeded,
)


async def run_tests() -> list[str]:
    errors: list[str] = []

    # Test 1: Rate limiting - 1 RPS means second rapid call should be rejected
    cfg = ExecutionSafetyConfig(rate_limit_rps=1.0, max_concurrency=100, max_retries=1)
    layer = ExecutionSafetyLayer(config=cfg)

    # First call should succeed
    await layer.check_rate_limit("test_tool")

    # Second immediate call should raise RateLimitExceeded
    try:
        await layer.check_rate_limit("test_tool")
        errors.append("Second rapid call should have been rate-limited")
    except RateLimitExceeded:
        pass  # expected

    # Test 2: Retry logic - coroutine fails twice then succeeds
    call_count = 0

    async def flaky_coroutine():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ValueError(f"Simulated failure #{call_count}")
        return "success"

    retry_cfg = ExecutionSafetyConfig(
        rate_limit_rps=1000,  # high limit so rate limiting doesn't interfere
        max_concurrency=100,
        max_retries=3,
        retry_backoff_base=0.01,  # fast backoff for test
        timeout_seconds=5,
    )
    retry_layer = ExecutionSafetyLayer(config=retry_cfg)

    call_count = 0
    result = await retry_layer.execute_with_safety(
        flaky_coroutine, "test_retry"
    )
    if result != "success":
        errors.append(f"Expected 'success', got '{result}'")
    if call_count != 3:
        errors.append(f"Expected 3 calls (2 failures + 1 success), got {call_count}")

    # Test 3: Retry exhaustion - always fails
    exhaust_cfg = ExecutionSafetyConfig(
        rate_limit_rps=1000,
        max_concurrency=100,
        max_retries=2,
        retry_backoff_base=0.01,
        timeout_seconds=5,
    )
    exhaust_layer = ExecutionSafetyLayer(config=exhaust_cfg)

    async def always_fails():
        raise ValueError("always fails")

    try:
        await exhaust_layer.execute_with_safety(always_fails, "test_exhaust")
        errors.append("Should have raised ExecutionSafetyError after exhausting retries")
    except ExecutionSafetyError:
        pass  # expected

    return errors


def main() -> None:
    errors = asyncio.run(run_tests())
    if errors:
        print("TASK 2 FAILED:")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("TASK 2 PASSED")


if __name__ == "__main__":
    main()
