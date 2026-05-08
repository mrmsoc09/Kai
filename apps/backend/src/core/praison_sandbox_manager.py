"""
DeepAgents Sandbox Manager
===========================
Enterprise-safe sandbox lifecycle management for DeepAgent code execution.

Sandboxes provide isolated execution environments for specialists that
need to run code (e.g., exploit verification, data analysis, script execution).

Design principles:
  - Sandbox-as-tool architecture: sandboxes are tools, not ambient capabilities
  - Secrets never enter sandbox: credentials stay in Vault, not sandbox env
  - TTL-bounded lifecycle: sandboxes auto-destroy after max_ttl_seconds
  - Auditable: every create/execute/destroy emits telemetry
  - Host shell BLOCKED in production: no os.system/subprocess bypass
  - Execution mode aware: graph_only returns fixtures, tool_mock returns mocks
  - Future-ready: seams for Docker/gVisor/Firecracker backends

Current implementation:
  - InProcessSandbox: restricted exec() in isolated namespace (dev/test only)
  - MockSandbox: deterministic fixtures for simulation modes
  - Future: DockerSandbox, RemoteSandbox

Production safety:
  K1_SANDBOX_ALLOW_INPROCESS=false (default) -> blocks in-process exec
  K1_SANDBOX_MAX_TTL=3600 (default) -> hard TTL cap
  K1_SANDBOX_MAX_CONCURRENT=5 (default) -> concurrency limit
"""

from __future__ import annotations

import io
import logging
import os
import threading
import time
import uuid
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from apps.backend.src.core.praison_execution_events import (
    MissionEvent,
    emit as _emit_event,
    get_event_bus,
)

logger = logging.getLogger(__name__)


# -- Constants ----------------------------------------------------------------

_DEFAULT_MAX_TTL: int = 3600
_DEFAULT_MAX_CONCURRENT: int = 5
_DEFAULT_MAX_MEMORY_MB: int = 256
_DEFAULT_MAX_OUTPUT_BYTES: int = 1_048_576  # 1 MB
_DEFAULT_EXECUTION_TTL: int = 300  # per-sandbox default TTL
_DEFAULT_MAX_CODE_CHARS: int = 100_000
_CONTENT_PREVIEW_MAX: int = 500


# -- SandboxState enum --------------------------------------------------------


class SandboxState(str, Enum):
    """Lifecycle states for a sandbox instance."""

    CREATED = "created"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    DESTROYED = "destroyed"
    EXPIRED = "expired"


_TERMINAL_STATES = frozenset({
    SandboxState.COMPLETED,
    SandboxState.FAILED,
    SandboxState.DESTROYED,
    SandboxState.EXPIRED,
})


# -- SandboxResult dataclass --------------------------------------------------


@dataclass
class SandboxResult:
    """Result of code execution in a sandbox."""

    sandbox_id: str
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time_ms: float
    truncated: bool  # True if output was truncated
    error: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sandbox_id": self.sandbox_id,
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "execution_time_ms": self.execution_time_ms,
            "truncated": self.truncated,
            "error": self.error,
        }


# -- SandboxConfig dataclass --------------------------------------------------


@dataclass(frozen=True)
class SandboxConfig:
    """Immutable sandbox configuration."""

    sandbox_id: str
    agent_id: str
    mission_id: str
    workflow_id: str
    thread_id: str
    max_ttl_seconds: int  # hard TTL (default 300)
    max_memory_mb: int  # memory limit (default 256)
    max_output_bytes: int  # stdout/stderr cap (default 1 MB)
    allowed_modules: frozenset[str]  # Python modules allowed in sandbox
    blocked_modules: frozenset[str]  # Python modules blocked (os, subprocess, etc.)
    allow_network: bool  # False in production
    allow_filesystem: bool  # False in production
    execution_mode: str  # "live" | "graph_only" | "tool_mock"

    _DEFAULT_BLOCKED: frozenset[str] = frozenset({
        "os", "subprocess", "shutil", "pathlib", "socket", "http",
        "urllib", "requests", "sys", "importlib", "ctypes", "signal",
    })

    @classmethod
    def safe_default(
        cls,
        agent_id: str,
        mission_id: str = "",
        workflow_id: str = "",
        thread_id: str = "",
        execution_mode: str = "live",
    ) -> SandboxConfig:
        """
        Create a safe default sandbox configuration.

        Blocks dangerous modules, disables network and filesystem access,
        uses conservative TTL and memory limits.
        """
        return cls(
            sandbox_id=str(uuid.uuid4()),
            agent_id=agent_id,
            mission_id=mission_id,
            workflow_id=workflow_id,
            thread_id=thread_id or str(uuid.uuid4()),
            max_ttl_seconds=_DEFAULT_EXECUTION_TTL,
            max_memory_mb=_DEFAULT_MAX_MEMORY_MB,
            max_output_bytes=_DEFAULT_MAX_OUTPUT_BYTES,
            allowed_modules=frozenset(),
            blocked_modules=cls._DEFAULT_BLOCKED,
            allow_network=False,
            allow_filesystem=False,
            execution_mode=execution_mode,
        )


# -- SandboxHandle ------------------------------------------------------------


class SandboxHandle:
    """
    Active sandbox instance handle.
    Tracks lifecycle and enforces TTL.
    """

    def __init__(self, config: SandboxConfig) -> None:
        self._config = config
        self._state = SandboxState.CREATED
        self._created_at = time.monotonic()
        self._created_timestamp = datetime.now(timezone.utc)
        self._execution_count: int = 0
        self._lock = threading.Lock()

    @property
    def sandbox_id(self) -> str:
        return self._config.sandbox_id

    @property
    def state(self) -> SandboxState:
        with self._lock:
            # Auto-transition to expired if TTL exceeded
            if (
                self._state not in _TERMINAL_STATES
                and self.is_expired
            ):
                self._state = SandboxState.EXPIRED
            return self._state

    @property
    def is_expired(self) -> bool:
        """True if the sandbox has exceeded its max TTL."""
        return self.elapsed_seconds > self._config.max_ttl_seconds

    @property
    def elapsed_seconds(self) -> float:
        """Seconds since sandbox creation."""
        return time.monotonic() - self._created_at

    async def execute(self, code: str, *, timeout_seconds: int = 30) -> SandboxResult:
        """
        Execute code in the sandbox.

        In graph_only mode: returns deterministic fixture.
        In tool_mock mode: returns mock result.
        In live mode: executes in restricted namespace (dev) or container (future).

        Args:
            code: Python code string to execute.
            timeout_seconds: Maximum execution time in seconds.

        Returns:
            SandboxResult with stdout, stderr, exit_code, etc.
        """
        with self._lock:
            # Check terminal state
            if self._state in _TERMINAL_STATES:
                return SandboxResult(
                    sandbox_id=self._config.sandbox_id,
                    success=False,
                    stdout="",
                    stderr="",
                    exit_code=1,
                    execution_time_ms=0.0,
                    truncated=False,
                    error=f"Sandbox is in terminal state: {self._state.value}",
                )
            # Check expiry
            if self.is_expired:
                self._state = SandboxState.EXPIRED
                return SandboxResult(
                    sandbox_id=self._config.sandbox_id,
                    success=False,
                    stdout="",
                    stderr="",
                    exit_code=1,
                    execution_time_ms=0.0,
                    truncated=False,
                    error="Sandbox has expired (TTL exceeded)",
                )
            self._state = SandboxState.RUNNING

        mode = self._config.execution_mode
        start_ms = time.monotonic()

        try:
            if mode == "graph_only":
                result = SandboxResult(
                    sandbox_id=self._config.sandbox_id,
                    success=True,
                    stdout="[SIMULATION] Code execution skipped in graph_only mode",
                    stderr="",
                    exit_code=0,
                    execution_time_ms=0.0,
                    truncated=False,
                    error="",
                )
            elif mode == "tool_mock":
                result = SandboxResult(
                    sandbox_id=self._config.sandbox_id,
                    success=True,
                    stdout=f"[MOCK] Executed {len(code)} chars of code",
                    stderr="",
                    exit_code=0,
                    execution_time_ms=1.0,
                    truncated=False,
                    error="",
                )
            else:
                # Live mode
                result = self._execute_live(code, timeout_seconds=timeout_seconds)

            elapsed_ms = (time.monotonic() - start_ms) * 1000.0
            result.execution_time_ms = elapsed_ms

            with self._lock:
                self._execution_count += 1
                if result.success:
                    self._state = SandboxState.COMPLETED
                else:
                    self._state = SandboxState.FAILED

            # Emit telemetry
            _emit_sandbox_event(
                "sandbox_executed",
                config=self._config,
                detail={
                    "execution_time_ms": result.execution_time_ms,
                    "exit_code": result.exit_code,
                    "success": result.success,
                    "truncated": result.truncated,
                    "execution_count": self._execution_count,
                    "mode": mode,
                },
            )

            return result

        except Exception as exc:
            elapsed_ms = (time.monotonic() - start_ms) * 1000.0
            with self._lock:
                self._state = SandboxState.FAILED
            logger.error(
                "Sandbox %s execution error: %s",
                self._config.sandbox_id,
                exc,
                exc_info=True,
            )
            return SandboxResult(
                sandbox_id=self._config.sandbox_id,
                success=False,
                stdout="",
                stderr="",
                exit_code=1,
                execution_time_ms=elapsed_ms,
                truncated=False,
                error=f"Sandbox execution error: {exc}",
            )

    def _execute_live(self, code: str, *, timeout_seconds: int = 30) -> SandboxResult:
        """
        Execute code in live mode using restricted in-process exec or blocking.

        Checks K1_SANDBOX_ALLOW_INPROCESS env (default False).
        If allowed: uses _execute_restricted() with isolated namespace.
        If not allowed: returns error result.
        """
        allow_inprocess = (
            os.getenv("K1_SANDBOX_ALLOW_INPROCESS", "false").lower() == "true"
        )

        if not allow_inprocess:
            return SandboxResult(
                sandbox_id=self._config.sandbox_id,
                success=False,
                stdout="",
                stderr="",
                exit_code=1,
                execution_time_ms=0.0,
                truncated=False,
                error="In-process execution blocked in production. "
                      "Set K1_SANDBOX_ALLOW_INPROCESS=true for dev/test.",
            )

        return self._execute_restricted(code, timeout_seconds=timeout_seconds)

    def _execute_restricted(self, code: str, *, timeout_seconds: int = 30) -> SandboxResult:
        """
        Execute code in a restricted namespace with timeout enforcement.

        Steps:
        1. Create clean namespace dict (only safe builtins)
        2. Filter blocked_modules from builtins
        3. Use exec(code, namespace) with timeout via threading.Timer
        4. Capture stdout via io.StringIO redirect
        5. Truncate output to max_output_bytes
        6. Return SandboxResult
        """
        if len(code) > _DEFAULT_MAX_CODE_CHARS:
            return SandboxResult(
                sandbox_id=self._config.sandbox_id,
                success=False,
                stdout="",
                stderr="",
                exit_code=1,
                execution_time_ms=0.0,
                truncated=False,
                error=f"Code exceeds maximum length ({len(code)} > {_DEFAULT_MAX_CODE_CHARS})",
            )

        # Build restricted builtins from an explicit allowlist.
        # This removes powerful primitives such as open/eval/exec/compile/input.
        import builtins as _builtins

        # object and __build_class__ are excluded: access to object.__subclasses__()
        # enables full MRO traversal and sandbox escape regardless of import restrictions.
        allowed_builtin_names = {
            "abs", "all", "any", "bool", "bytes", "dict", "enumerate", "filter",
            "float", "frozenset", "int", "isinstance", "issubclass", "len", "list",
            "map", "max", "min", "pow", "print", "range", "repr", "reversed",
            "round", "set", "sorted", "str", "sum", "tuple", "type", "zip",
            "Exception", "RuntimeError", "ValueError", "TypeError", "KeyError",
            "IndexError", "AssertionError", "ZeroDivisionError",
        }
        safe_builtins: dict[str, Any] = {}
        for name in allowed_builtin_names:
            value = getattr(_builtins, name, None)
            if value is not None:
                safe_builtins[name] = value

        # Create a restricted __import__ that blocks dangerous modules
        blocked = self._config.blocked_modules
        allowed_modules = set(self._config.allowed_modules)
        if isinstance(__builtins__, dict):
            original_import = __builtins__.get("__import__", __import__)
        else:
            original_import = getattr(__builtins__, "__import__", __import__)

        def restricted_import(name: str, *args: Any, **kwargs: Any) -> Any:
            # Check if the top-level module name is blocked
            top_module = name.split(".")[0]
            if top_module in blocked:
                raise ImportError(
                    f"Module '{name}' is blocked in sandbox (blocked: {top_module})"
                )
            if allowed_modules and top_module not in allowed_modules:
                raise ImportError(
                    f"Module '{name}' is not allowlisted in sandbox"
                )
            return original_import(name, *args, **kwargs)

        safe_builtins["__import__"] = restricted_import
        safe_builtins["__builtins__"] = safe_builtins

        namespace: dict[str, Any] = {"__builtins__": safe_builtins, "__name__": "__sandbox__"}

        # Capture stdout and stderr
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()

        # Execution with timeout
        exec_error: list[str] = []  # mutable container for thread communication
        exec_completed = threading.Event()

        def _run_exec() -> None:
            try:
                with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                    exec(code, namespace)  # noqa: S102  -- intentional restricted exec
            except Exception as exc:
                exec_error.append(str(exc))
            finally:
                exec_completed.set()

        exec_thread = threading.Thread(target=_run_exec, daemon=True)
        exec_thread.start()
        exec_thread.join(timeout=timeout_seconds)

        timed_out = not exec_completed.is_set()

        # Retrieve captured output
        raw_stdout = stdout_capture.getvalue()
        raw_stderr = stderr_capture.getvalue()

        # Truncate output to max_output_bytes
        max_bytes = self._config.max_output_bytes
        truncated = False

        if len(raw_stdout.encode("utf-8", errors="replace")) > max_bytes:
            # Truncate by character count (approximate)
            raw_stdout = raw_stdout[:max_bytes] + "\n... [TRUNCATED]"
            truncated = True
        if len(raw_stderr.encode("utf-8", errors="replace")) > max_bytes:
            raw_stderr = raw_stderr[:max_bytes] + "\n... [TRUNCATED]"
            truncated = True

        if timed_out:
            return SandboxResult(
                sandbox_id=self._config.sandbox_id,
                success=False,
                stdout=raw_stdout,
                stderr=raw_stderr,
                exit_code=124,  # conventional timeout exit code
                execution_time_ms=timeout_seconds * 1000.0,
                truncated=truncated,
                error=f"Execution timed out after {timeout_seconds}s",
            )

        if exec_error:
            return SandboxResult(
                sandbox_id=self._config.sandbox_id,
                success=False,
                stdout=raw_stdout,
                stderr=raw_stderr,
                exit_code=1,
                execution_time_ms=0.0,
                truncated=truncated,
                error=exec_error[0],
            )

        return SandboxResult(
            sandbox_id=self._config.sandbox_id,
            success=True,
            stdout=raw_stdout,
            stderr=raw_stderr,
            exit_code=0,
            execution_time_ms=0.0,
            truncated=truncated,
            error="",
        )

    def destroy(self) -> None:
        """Explicitly destroy the sandbox."""
        with self._lock:
            if self._state not in _TERMINAL_STATES:
                self._state = SandboxState.DESTROYED

    def to_dict(self) -> dict[str, Any]:
        """Serialize sandbox handle state for audit and API responses."""
        return {
            "sandbox_id": self._config.sandbox_id,
            "agent_id": self._config.agent_id,
            "mission_id": self._config.mission_id,
            "workflow_id": self._config.workflow_id,
            "thread_id": self._config.thread_id,
            "state": self.state.value,
            "execution_mode": self._config.execution_mode,
            "max_ttl_seconds": self._config.max_ttl_seconds,
            "elapsed_seconds": round(self.elapsed_seconds, 2),
            "is_expired": self.is_expired,
            "execution_count": self._execution_count,
            "created_at": self._created_timestamp.isoformat(),
        }


# -- SandboxLimitExceeded exception -------------------------------------------


class SandboxLimitExceeded(RuntimeError):
    """Raised when sandbox concurrency limit is reached."""


# -- SandboxManager -----------------------------------------------------------


class SandboxManager:
    """
    Manages sandbox lifecycle across all DeepAgent specialists.

    Thread-safe. Enforces:
    - Max concurrent sandboxes (K1_SANDBOX_MAX_CONCURRENT)
    - TTL expiry with auto-cleanup
    - No host shell in production
    - Audit trail for every operation
    """

    def __init__(
        self,
        event_bus: Any | None = None,
        max_concurrent: int | None = None,
    ) -> None:
        self._event_bus = event_bus
        self._max_concurrent = (
            max_concurrent
            if max_concurrent is not None
            else int(os.getenv("K1_SANDBOX_MAX_CONCURRENT", str(_DEFAULT_MAX_CONCURRENT)))
        )
        self._sandboxes: dict[str, SandboxHandle] = {}
        self._lock = threading.Lock()
        logger.debug(
            "SandboxManager initialized: max_concurrent=%d",
            self._max_concurrent,
        )

    def create(
        self,
        agent_id: str,
        *,
        mission_id: str = "",
        workflow_id: str = "",
        thread_id: str = "",
        execution_mode: str = "live",
        max_ttl_seconds: int | None = None,
    ) -> SandboxHandle:
        """
        Create a new sandbox. Enforces concurrency limits.
        Emits sandbox_created event.

        Args:
            agent_id: The agent requesting the sandbox.
            mission_id: Correlation ID for the active mission.
            workflow_id: Correlation ID for the active workflow.
            thread_id: Unique thread identifier (auto-generated if empty).
            execution_mode: "live" | "graph_only" | "tool_mock".
            max_ttl_seconds: Override default TTL.

        Returns:
            SandboxHandle for the newly created sandbox.

        Raises:
            SandboxLimitExceeded: If max concurrent sandboxes are already active.
        """
        # Resolve TTL: explicit arg > env > default
        resolved_ttl = max_ttl_seconds
        if resolved_ttl is None:
            resolved_ttl = int(
                os.getenv("K1_SANDBOX_MAX_TTL", str(_DEFAULT_MAX_TTL))
            )
        # Clamp TTL to the hard maximum from env
        hard_max = int(os.getenv("K1_SANDBOX_MAX_TTL", str(_DEFAULT_MAX_TTL)))
        resolved_ttl = min(resolved_ttl, hard_max)

        config = SandboxConfig.safe_default(
            agent_id=agent_id,
            mission_id=mission_id,
            workflow_id=workflow_id,
            thread_id=thread_id,
            execution_mode=execution_mode,
        )
        # Override TTL on the config via object.__setattr__ since it is frozen
        object.__setattr__(config, "max_ttl_seconds", resolved_ttl)

        with self._lock:
            # Clean expired before checking limits
            self._cleanup_expired_locked()

            active_count = sum(
                1 for h in self._sandboxes.values()
                if h.state not in _TERMINAL_STATES
            )
            if active_count >= self._max_concurrent:
                raise SandboxLimitExceeded(
                    f"Sandbox concurrency limit reached: {active_count}/{self._max_concurrent}. "
                    f"Destroy existing sandboxes or wait for TTL expiry."
                )

            handle = SandboxHandle(config)
            self._sandboxes[config.sandbox_id] = handle

        # Emit telemetry
        _emit_sandbox_event(
            "sandbox_created",
            config=config,
            detail={
                "max_ttl_seconds": resolved_ttl,
                "execution_mode": execution_mode,
            },
            event_bus=self._event_bus,
        )

        logger.debug(
            "Sandbox created: id=%s agent=%s mode=%s ttl=%ds",
            config.sandbox_id,
            agent_id,
            execution_mode,
            resolved_ttl,
        )

        return handle

    def get(self, sandbox_id: str) -> SandboxHandle | None:
        """Retrieve a sandbox handle by ID. Returns None if not found."""
        with self._lock:
            return self._sandboxes.get(sandbox_id)

    def destroy(self, sandbox_id: str) -> bool:
        """
        Destroy a specific sandbox by ID.

        Returns:
            True if the sandbox was found and destroyed, False if not found.
        """
        with self._lock:
            handle = self._sandboxes.get(sandbox_id)
            if handle is None:
                return False
            handle.destroy()

        # Emit telemetry
        _emit_sandbox_event(
            "sandbox_destroyed",
            config=handle._config,
            detail={"elapsed_seconds": round(handle.elapsed_seconds, 2)},
            event_bus=self._event_bus,
        )

        logger.debug("Sandbox destroyed: id=%s", sandbox_id)
        return True

    def destroy_for_mission(self, mission_id: str) -> int:
        """
        Destroy all sandboxes for a mission.

        Returns:
            Count of sandboxes destroyed.
        """
        destroyed = 0
        with self._lock:
            for handle in self._sandboxes.values():
                if (
                    handle._config.mission_id == mission_id
                    and handle.state not in _TERMINAL_STATES
                ):
                    handle.destroy()
                    _emit_sandbox_event(
                        "sandbox_destroyed",
                        config=handle._config,
                        detail={
                            "reason": "mission_cleanup",
                            "elapsed_seconds": round(handle.elapsed_seconds, 2),
                        },
                        event_bus=self._event_bus,
                    )
                    destroyed += 1

        if destroyed:
            logger.debug(
                "Destroyed %d sandboxes for mission %s",
                destroyed,
                mission_id,
            )
        return destroyed

    def cleanup_expired(self) -> int:
        """
        Destroy all expired sandboxes.

        Returns:
            Count of sandboxes expired and cleaned up.
        """
        with self._lock:
            return self._cleanup_expired_locked()

    def _cleanup_expired_locked(self) -> int:
        """
        Internal: clean up expired sandboxes while holding self._lock.

        Returns count of sandboxes transitioned to EXPIRED.
        """
        expired_count = 0
        for handle in self._sandboxes.values():
            if handle.state not in _TERMINAL_STATES and handle.is_expired:
                handle.destroy()
                # Set state to EXPIRED specifically (destroy sets DESTROYED)
                with handle._lock:
                    handle._state = SandboxState.EXPIRED
                _emit_sandbox_event(
                    "sandbox_expired",
                    config=handle._config,
                    detail={
                        "elapsed_seconds": round(handle.elapsed_seconds, 2),
                        "max_ttl_seconds": handle._config.max_ttl_seconds,
                    },
                    event_bus=self._event_bus,
                )
                expired_count += 1

        if expired_count:
            logger.debug("Cleaned up %d expired sandboxes", expired_count)
        return expired_count

    def active_count(self) -> int:
        """Return count of non-terminal sandboxes."""
        with self._lock:
            return sum(
                1 for h in self._sandboxes.values()
                if h.state not in _TERMINAL_STATES
            )

    def list_active(self) -> list[dict[str, Any]]:
        """Return serialized list of all non-terminal sandboxes."""
        with self._lock:
            return [
                h.to_dict()
                for h in self._sandboxes.values()
                if h.state not in _TERMINAL_STATES
            ]


# -- Telemetry helper ---------------------------------------------------------


def _emit_sandbox_event(
    event_type: str,
    *,
    config: SandboxConfig,
    detail: dict[str, Any] | None = None,
    event_bus: Any | None = None,
) -> None:
    """
    Emit a sandbox telemetry event to the Kai EventBus.

    Uses emit() from praison_execution_events with MissionEvent.
    Falls back to the module-level singleton EventBus if no event_bus provided.
    """
    event = MissionEvent(
        event_type=event_type,
        mission_id=config.mission_id,
        workflow_id=config.workflow_id,
        agent_id=config.agent_id,
        node_id=config.sandbox_id,
        detail={
            "sandbox_id": config.sandbox_id,
            "agent_id": config.agent_id,
            "thread_id": config.thread_id,
            "execution_mode": config.execution_mode,
            **(detail or {}),
        },
    )

    try:
        if event_bus is not None and hasattr(event_bus, "emit"):
            event_bus.emit(event)
        else:
            _emit_event(event)
    except Exception as exc:
        logger.warning(
            "Failed to emit sandbox event %s for %s: %s",
            event_type,
            config.sandbox_id,
            exc,
        )


# -- Module singleton ---------------------------------------------------------

_manager: SandboxManager | None = None
_manager_lock = threading.Lock()


def get_sandbox_manager() -> SandboxManager:
    """
    Return the module-level SandboxManager singleton.

    Creates a default instance on first access. Use initialize_sandbox_manager()
    for explicit configuration (e.g., injecting a custom EventBus or concurrency limit).
    """
    global _manager
    if _manager is None:
        with _manager_lock:
            if _manager is None:
                _manager = SandboxManager()
    return _manager


def initialize_sandbox_manager(
    event_bus: Any | None = None,
    max_concurrent: int | None = None,
) -> SandboxManager:
    """
    Initialize (or reinitialize) the module-level SandboxManager singleton.

    Args:
        event_bus: Optional EventBus instance for telemetry emission.
        max_concurrent: Override max concurrent sandbox limit.

    Returns:
        The newly created SandboxManager singleton.
    """
    global _manager
    with _manager_lock:
        _manager = SandboxManager(event_bus=event_bus, max_concurrent=max_concurrent)
    logger.info(
        "SandboxManager initialized: max_concurrent=%d",
        _manager._max_concurrent,
    )
    return _manager
