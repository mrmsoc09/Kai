from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Coroutine

logger = logging.getLogger(__name__)


class ExecutionSafetyError(RuntimeError):
    """Raised when execution safety constraints are violated."""


class RateLimitExceeded(ExecutionSafetyError):
    """Raised when a tool exceeds its rate limit."""


@dataclass
class ExecutionSafetyConfig:
    rate_limit_rps: float = 2.0
    max_concurrency: int = 5
    timeout_seconds: int = 300
    max_retries: int = 3
    retry_backoff_base: float = 2.0


TOOL_SAFETY_DEFAULTS: dict[str, ExecutionSafetyConfig] = {
    "httpx": ExecutionSafetyConfig(rate_limit_rps=10, max_concurrency=20, timeout_seconds=30),
    "nuclei": ExecutionSafetyConfig(rate_limit_rps=2, max_concurrency=5, timeout_seconds=300),
    "ffuf": ExecutionSafetyConfig(rate_limit_rps=5, max_concurrency=10, timeout_seconds=600),
    "sqlmap": ExecutionSafetyConfig(rate_limit_rps=1, max_concurrency=2, timeout_seconds=900),
    "default": ExecutionSafetyConfig(rate_limit_rps=2, max_concurrency=5, timeout_seconds=300),
}


@dataclass
class _ToolState:
    last_execution: float = 0.0
    active_count: int = 0


class ExecutionSafetyLayer:
    """Wraps tool execution with rate limiting, timeouts, and retry logic."""

    def __init__(self, config: ExecutionSafetyConfig | None = None) -> None:
        self.config = config or ExecutionSafetyConfig()
        self._tool_states: dict[str, _ToolState] = {}
        self._lock = asyncio.Lock()

    def _get_state(self, tool_name: str) -> _ToolState:
        if tool_name not in self._tool_states:
            self._tool_states[tool_name] = _ToolState()
        return self._tool_states[tool_name]

    def _get_config(self, tool_name: str) -> ExecutionSafetyConfig:
        return TOOL_SAFETY_DEFAULTS.get(tool_name, self.config)

    async def check_rate_limit(self, tool_name: str) -> None:
        """Check and enforce rate limit for a tool. Raises RateLimitExceeded if over limit."""
        cfg = self._get_config(tool_name)
        min_interval = 1.0 / cfg.rate_limit_rps if cfg.rate_limit_rps > 0 else 0.0

        async with self._lock:
            state = self._get_state(tool_name)
            now = time.monotonic()
            elapsed = now - state.last_execution

            if elapsed < min_interval:
                raise RateLimitExceeded(
                    f"Tool '{tool_name}' rate limited: {elapsed:.3f}s since last call, "
                    f"minimum interval {min_interval:.3f}s"
                )

            if state.active_count >= cfg.max_concurrency:
                raise RateLimitExceeded(
                    f"Tool '{tool_name}' concurrency limit reached: "
                    f"{state.active_count}/{cfg.max_concurrency}"
                )

            state.last_execution = now
            state.active_count += 1

    async def _release(self, tool_name: str) -> None:
        async with self._lock:
            state = self._get_state(tool_name)
            state.active_count = max(0, state.active_count - 1)

    async def execute_with_safety(
        self,
        coro_factory: Any,
        tool_name: str,
        timeout: int | None = None,
    ) -> Any:
        """Execute a coroutine with timeout and retry logic.

        coro_factory must be a callable that returns a new coroutine each call,
        since coroutines can only be awaited once.
        """
        cfg = self._get_config(tool_name)
        effective_timeout = timeout or cfg.timeout_seconds
        last_error: Exception | None = None

        for attempt in range(1, cfg.max_retries + 1):
            await self.check_rate_limit(tool_name)
            try:
                result = await asyncio.wait_for(coro_factory(), timeout=effective_timeout)
                await self._release(tool_name)
                return result
            except asyncio.TimeoutError:
                await self._release(tool_name)
                last_error = ExecutionSafetyError(
                    f"Tool '{tool_name}' timed out after {effective_timeout}s (attempt {attempt})"
                )
            except RateLimitExceeded:
                await self._release(tool_name)
                raise
            except Exception as exc:
                await self._release(tool_name)
                last_error = exc

            if attempt < cfg.max_retries:
                backoff = cfg.retry_backoff_base ** (attempt - 1)
                logger.info(
                    "Retrying tool '%s' in %.1fs (attempt %d/%d)",
                    tool_name,
                    backoff,
                    attempt + 1,
                    cfg.max_retries,
                )
                await asyncio.sleep(backoff)

        raise ExecutionSafetyError(
            f"Tool '{tool_name}' exhausted {cfg.max_retries} retries: {last_error}"
        )
