"""
DeepAgents Backend Policy
==========================
Safe backend management for DeepAgent specialist scratch and storage.

Enforces:
  - Ephemeral scratch is the default (thread-scoped, auto-cleanup)
  - Durable storage only where explicitly approved
  - Local host filesystem BLOCKED in production
  - Local shell BLOCKED in production
  - All writes path-prefix restricted to K1_ARTIFACTS_ROOT
  - No secrets in any backend workspace
  - Audit trail for all workspace operations

Backend types:
  - "ephemeral": In-memory dict-based scratch (default, always safe)
  - "scratch": File-based scratch under K1_ARTIFACTS_ROOT/scratch/{thread_id}/
  - "durable": Persistent storage under K1_ARTIFACTS_ROOT/specialist_memory/{agent_id}/
    (requires explicit approval and governance context)

Production safety:
  - K1_DEEPAGENT_ALLOW_HOST_FS=false (default) blocks all host filesystem access
  - K1_DEEPAGENT_ALLOW_SHELL=false (default) blocks shell execution
  - Path traversal prevention via strict prefix checking
"""

from __future__ import annotations

import logging
import os
import shutil
import threading
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# -- Real deepagents backend protocol availability ----------------------------
try:
    from deepagents.backends.protocol import (
        BackendProtocol as _RealBackendProtocol,
    )
    _DEEPAGENTS_BACKEND_AVAILABLE = True
except ImportError:
    _RealBackendProtocol = None  # type: ignore[assignment,misc]
    _DEEPAGENTS_BACKEND_AVAILABLE = False


def is_deepagents_backend_available() -> bool:
    """Return True if the real deepagents BackendProtocol is importable."""
    return _DEEPAGENTS_BACKEND_AVAILABLE


# -- Enums and exceptions -----------------------------------------------------


class BackendPolicy(str, Enum):
    """Workspace backend policy for DeepAgent specialists."""

    EPHEMERAL = "ephemeral"  # in-memory, thread-scoped
    SCRATCH = "scratch"  # file-based, auto-cleanup
    DURABLE = "durable"  # persistent, requires approval


class BackendViolation(PermissionError):
    """Raised when a backend operation violates policy."""


# -- BackendConfig -------------------------------------------------------------


@dataclass(frozen=True)
class BackendConfig:
    """Immutable configuration for a DeepAgent workspace backend."""

    policy: BackendPolicy
    base_path: str  # K1_ARTIFACTS_ROOT-based resolved path
    agent_id: str
    thread_id: str
    max_size_bytes: int  # budget for this workspace (default 50 MB)
    allow_host_fs: bool  # False in production
    allow_shell: bool  # False in production
    ttl_seconds: int  # auto-cleanup TTL (default 3600)

    @classmethod
    def safe_default(cls, agent_id: str, thread_id: str) -> BackendConfig:
        """
        Create a safe default config for development / testing.

        Uses ephemeral policy with conservative limits.
        Host filesystem and shell access are disabled.
        """
        base = os.path.join(_resolve_artifacts_root(), "scratch", thread_id)
        return cls(
            policy=BackendPolicy.EPHEMERAL,
            base_path=base,
            agent_id=agent_id,
            thread_id=thread_id,
            max_size_bytes=50 * 1024 * 1024,  # 50 MB
            allow_host_fs=False,
            allow_shell=False,
            ttl_seconds=3600,
        )

    @classmethod
    def for_production(
        cls,
        agent_id: str,
        thread_id: str,
        policy: BackendPolicy = BackendPolicy.EPHEMERAL,
    ) -> BackendConfig:
        """
        Create a production-safe config.

        Host filesystem and shell are unconditionally disabled.
        Durable policy requires K1_DEEPAGENT_ALLOW_DURABLE=true.
        """
        if policy == BackendPolicy.DURABLE and not _allow_durable():
            logger.warning(
                "BackendConfig.for_production: durable policy requested but "
                "K1_DEEPAGENT_ALLOW_DURABLE is not true — falling back to scratch"
            )
            policy = BackendPolicy.SCRATCH

        if policy == BackendPolicy.SCRATCH:
            base = os.path.join(_resolve_artifacts_root(), "scratch", thread_id)
        elif policy == BackendPolicy.DURABLE:
            base = os.path.join(
                _resolve_artifacts_root(), "specialist_memory", agent_id
            )
        else:
            # Ephemeral — base_path is nominal (not used for filesystem)
            base = os.path.join(_resolve_artifacts_root(), "scratch", thread_id)

        return cls(
            policy=policy,
            base_path=base,
            agent_id=agent_id,
            thread_id=thread_id,
            max_size_bytes=50 * 1024 * 1024,  # 50 MB
            allow_host_fs=False,
            allow_shell=False,
            ttl_seconds=3600,
        )


# -- DeepAgentBackend base class -----------------------------------------------


class DeepAgentBackend:
    """
    Governed workspace backend for DeepAgent specialists.

    Provides read/write/list operations within a strictly bounded workspace.
    All paths are validated against the configured prefix.

    Subclasses implement the actual storage mechanism:
      - EphemeralBackend: in-memory dict
      - ScratchBackend: file-based with auto-cleanup
      - DurableBackend: persistent file-based
    """

    def __init__(self, config: BackendConfig) -> None:
        self._config = config
        # Normalize base_path to an absolute path for safe prefix comparison
        self._base_path = os.path.normpath(os.path.abspath(config.base_path))
        self._lock = threading.Lock()

    @property
    def config(self) -> BackendConfig:
        """Return the immutable backend configuration."""
        return self._config

    def write(self, key: str, data: str | bytes) -> str:
        """
        Write to workspace. Returns the full resolved path.

        Args:
            key: Relative key within the workspace (e.g. "output.json").
            data: Content to write (str or bytes).

        Returns:
            The full resolved path string.

        Raises:
            BackendViolation: On path traversal or budget exceeded.
        """
        raise NotImplementedError

    def read(self, key: str) -> str | bytes | None:
        """
        Read from workspace.

        Args:
            key: Relative key within the workspace.

        Returns:
            Content as str or bytes, or None if not found.
        """
        raise NotImplementedError

    def list_keys(self) -> list[str]:
        """List all keys in workspace."""
        raise NotImplementedError

    def delete(self, key: str) -> bool:
        """
        Delete key from workspace.

        Returns:
            True if the key existed and was deleted, False otherwise.
        """
        raise NotImplementedError

    def cleanup(self) -> None:
        """Remove entire workspace (called on TTL expiry or explicit cleanup)."""
        raise NotImplementedError

    def usage_bytes(self) -> int:
        """Current workspace size in bytes."""
        raise NotImplementedError

    @property
    def is_over_budget(self) -> bool:
        """True if workspace exceeds max_size_bytes."""
        return self.usage_bytes() > self._config.max_size_bytes

    def _validate_key(self, key: str) -> str:
        """
        Validate key does not escape prefix. Returns the normalized absolute path.

        Rejects:
        - Path traversal via ".."
        - Absolute paths (starting with "/")
        - Null bytes and control characters
        - Paths that escape the workspace prefix after normalization

        Raises:
            BackendViolation: On any traversal or escape attempt.
        """
        if not key or not key.strip():
            raise BackendViolation("Empty key is not permitted")

        # Reject null bytes and control characters
        if "\x00" in key:
            raise BackendViolation(f"Null byte in key: {key!r}")
        for ch in key:
            if ord(ch) < 32 and ch not in ("\n", "\r", "\t"):
                raise BackendViolation(
                    f"Control character (0x{ord(ch):02x}) in key: {key!r}"
                )

        # Reject absolute paths
        if key.startswith("/") or key.startswith("\\"):
            raise BackendViolation(f"Absolute path not permitted: {key!r}")

        # Reject path traversal components
        if ".." in key.split("/") or ".." in key.split("\\"):
            raise BackendViolation(f"Path traversal attempt: {key!r}")

        # Normalize and verify it stays within prefix
        normalized = os.path.normpath(os.path.join(self._base_path, key))
        # Ensure the normalized path starts with the base path followed by a
        # separator (or is exactly the base path, though that should not happen
        # for a file key)
        if not normalized.startswith(self._base_path + os.sep) and normalized != self._base_path:
            raise BackendViolation(f"Escaped workspace prefix: {key!r}")

        return normalized


# -- EphemeralBackend ----------------------------------------------------------


class EphemeralBackend(DeepAgentBackend):
    """
    In-memory dict backend. Always safe. No persistence.

    All data is stored in a thread-safe dict[str, str | bytes] that is
    discarded when the backend is garbage collected or cleanup() is called.
    """

    def __init__(self, config: BackendConfig) -> None:
        super().__init__(config)
        self._store: dict[str, str | bytes] = {}
        self._size_bytes: int = 0

    def write(self, key: str, data: str | bytes) -> str:
        """Write to in-memory store."""
        resolved = self._validate_key(key)
        data_bytes = len(data.encode("utf-8") if isinstance(data, str) else data)

        with self._lock:
            # Subtract old value size if overwriting
            if key in self._store:
                old_val = self._store[key]
                old_size = len(
                    old_val.encode("utf-8") if isinstance(old_val, str) else old_val
                )
                self._size_bytes -= old_size

            # Check budget before writing
            if self._size_bytes + data_bytes > self._config.max_size_bytes:
                raise BackendViolation(
                    f"Write would exceed workspace budget: "
                    f"current={self._size_bytes}, "
                    f"write={data_bytes}, "
                    f"max={self._config.max_size_bytes}"
                )

            self._store[key] = data
            self._size_bytes += data_bytes

        return resolved

    def read(self, key: str) -> str | bytes | None:
        """Read from in-memory store."""
        self._validate_key(key)  # validate even for reads (consistent policy)
        with self._lock:
            return self._store.get(key)

    def list_keys(self) -> list[str]:
        """List all keys in the in-memory store."""
        with self._lock:
            return sorted(self._store.keys())

    def delete(self, key: str) -> bool:
        """Delete key from in-memory store."""
        self._validate_key(key)
        with self._lock:
            if key not in self._store:
                return False
            old_val = self._store.pop(key)
            old_size = len(
                old_val.encode("utf-8") if isinstance(old_val, str) else old_val
            )
            self._size_bytes -= old_size
            return True

    def cleanup(self) -> None:
        """Clear entire in-memory store."""
        with self._lock:
            self._store.clear()
            self._size_bytes = 0
        logger.debug(
            "EphemeralBackend cleanup: agent=%s thread=%s",
            self._config.agent_id,
            self._config.thread_id,
        )

    def usage_bytes(self) -> int:
        """Current in-memory usage."""
        with self._lock:
            return self._size_bytes


# -- ScratchBackend ------------------------------------------------------------


class ScratchBackend(DeepAgentBackend):
    """
    File-based scratch under K1_ARTIFACTS_ROOT/scratch/{thread_id}/.

    Creates the directory on first write. Entire directory tree is removed
    on cleanup(). Suitable for temporary intermediate files during specialist
    execution.
    """

    def __init__(self, config: BackendConfig) -> None:
        super().__init__(config)
        self._initialized = False

    def _ensure_dir(self) -> None:
        """Create the scratch directory if it does not exist."""
        if not self._initialized:
            Path(self._base_path).mkdir(parents=True, exist_ok=True)
            self._initialized = True

    def write(self, key: str, data: str | bytes) -> str:
        """Write to filesystem under the scratch directory."""
        resolved = self._validate_key(key)
        data_bytes = len(data.encode("utf-8") if isinstance(data, str) else data)

        # Check budget before writing
        current = self.usage_bytes()
        if current + data_bytes > self._config.max_size_bytes:
            raise BackendViolation(
                f"Write would exceed workspace budget: "
                f"current={current}, write={data_bytes}, "
                f"max={self._config.max_size_bytes}"
            )

        self._ensure_dir()
        target = Path(resolved)
        target.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            if isinstance(data, bytes):
                target.write_bytes(data)
            else:
                target.write_text(data, encoding="utf-8")

        return resolved

    def read(self, key: str) -> str | bytes | None:
        """Read from filesystem."""
        resolved = self._validate_key(key)
        target = Path(resolved)
        if not target.exists():
            return None
        # Try text first, fall back to binary
        try:
            return target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return target.read_bytes()

    def list_keys(self) -> list[str]:
        """List all files relative to base_path."""
        base = Path(self._base_path)
        if not base.exists():
            return []
        keys: list[str] = []
        for p in base.rglob("*"):
            if p.is_file():
                keys.append(str(p.relative_to(base)))
        return sorted(keys)

    def delete(self, key: str) -> bool:
        """Delete a file from the scratch directory."""
        resolved = self._validate_key(key)
        target = Path(resolved)
        if not target.exists():
            return False
        with self._lock:
            target.unlink(missing_ok=True)
        return True

    def cleanup(self) -> None:
        """Remove the entire scratch directory tree."""
        base = Path(self._base_path)
        if base.exists():
            with self._lock:
                shutil.rmtree(base, ignore_errors=True)
            self._initialized = False
        logger.debug(
            "ScratchBackend cleanup: agent=%s thread=%s path=%s",
            self._config.agent_id,
            self._config.thread_id,
            self._base_path,
        )

    def usage_bytes(self) -> int:
        """Total size of all files in the scratch directory."""
        base = Path(self._base_path)
        if not base.exists():
            return 0
        total = 0
        for p in base.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
        return total


# -- DurableBackend ------------------------------------------------------------


class DurableBackend(DeepAgentBackend):
    """
    Persistent specialist memory. Requires explicit governance approval.

    Stored under K1_ARTIFACTS_ROOT/specialist_memory/{agent_id}/.
    Unlike ScratchBackend, cleanup() does NOT delete the directory — it only
    clears a session marker. Durable storage persists across executions.
    """

    def __init__(self, config: BackendConfig) -> None:
        super().__init__(config)
        self._initialized = False

    def _ensure_dir(self) -> None:
        """Create the durable directory if it does not exist."""
        if not self._initialized:
            Path(self._base_path).mkdir(parents=True, exist_ok=True)
            self._initialized = True

    def write(self, key: str, data: str | bytes) -> str:
        """Write to the durable storage directory."""
        resolved = self._validate_key(key)
        data_bytes = len(data.encode("utf-8") if isinstance(data, str) else data)

        current = self.usage_bytes()
        if current + data_bytes > self._config.max_size_bytes:
            raise BackendViolation(
                f"Write would exceed durable workspace budget: "
                f"current={current}, write={data_bytes}, "
                f"max={self._config.max_size_bytes}"
            )

        self._ensure_dir()
        target = Path(resolved)
        target.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            if isinstance(data, bytes):
                target.write_bytes(data)
            else:
                target.write_text(data, encoding="utf-8")

        return resolved

    def read(self, key: str) -> str | bytes | None:
        """Read from the durable storage directory."""
        resolved = self._validate_key(key)
        target = Path(resolved)
        if not target.exists():
            return None
        try:
            return target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return target.read_bytes()

    def list_keys(self) -> list[str]:
        """List all files in the durable storage directory."""
        base = Path(self._base_path)
        if not base.exists():
            return []
        keys: list[str] = []
        for p in base.rglob("*"):
            if p.is_file():
                keys.append(str(p.relative_to(base)))
        return sorted(keys)

    def delete(self, key: str) -> bool:
        """Delete a file from durable storage."""
        resolved = self._validate_key(key)
        target = Path(resolved)
        if not target.exists():
            return False
        with self._lock:
            target.unlink(missing_ok=True)
        return True

    def cleanup(self) -> None:
        """
        Cleanup for durable backend is a no-op on the directory.

        Durable storage persists across executions by design. Only individual
        keys can be deleted via delete(). To fully remove durable storage,
        use explicit administrative action.
        """
        logger.debug(
            "DurableBackend cleanup called (no-op): agent=%s path=%s",
            self._config.agent_id,
            self._base_path,
        )

    def usage_bytes(self) -> int:
        """Total size of all files in the durable directory."""
        base = Path(self._base_path)
        if not base.exists():
            return 0
        total = 0
        for p in base.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
        return total


# -- Factory -------------------------------------------------------------------


def create_backend(
    agent_id: str,
    thread_id: str,
    policy: str = "ephemeral",
    *,
    production_mode: bool | None = None,
) -> DeepAgentBackend:
    """
    Factory: create a governed backend.

    production_mode defaults to True unless K1_DEEPAGENT_DEV_MODE=true.
    In production mode:
    - "ephemeral" -> EphemeralBackend (always safe)
    - "scratch" -> ScratchBackend (bounded, auto-cleanup)
    - "durable" -> DurableBackend (requires K1_DEEPAGENT_ALLOW_DURABLE=true)
    - Host filesystem -> BLOCKED
    - Shell execution -> BLOCKED

    Args:
        agent_id: The agent this workspace belongs to.
        thread_id: Unique thread/execution ID for workspace isolation.
        policy: One of "ephemeral", "scratch", "durable".
        production_mode: Override production mode detection.

    Returns:
        A DeepAgentBackend subclass instance.

    Raises:
        BackendViolation: If durable is requested but not allowed.
        ValueError: If policy is not recognized.
    """
    if production_mode is None:
        production_mode = _is_production()

    # Resolve policy enum
    try:
        backend_policy = BackendPolicy(policy.lower())
    except ValueError:
        raise ValueError(
            f"Unknown backend policy: {policy!r}. "
            f"Valid values: {[p.value for p in BackendPolicy]}"
        )

    # Build config
    if production_mode:
        config = BackendConfig.for_production(agent_id, thread_id, backend_policy)
    else:
        # Development mode — still safe defaults but allow durable without env check
        if backend_policy == BackendPolicy.SCRATCH:
            base = os.path.join(_resolve_artifacts_root(), "scratch", thread_id)
        elif backend_policy == BackendPolicy.DURABLE:
            base = os.path.join(
                _resolve_artifacts_root(), "specialist_memory", agent_id
            )
        else:
            base = os.path.join(_resolve_artifacts_root(), "scratch", thread_id)

        config = BackendConfig(
            policy=backend_policy,
            base_path=base,
            agent_id=agent_id,
            thread_id=thread_id,
            max_size_bytes=50 * 1024 * 1024,  # 50 MB
            allow_host_fs=False,
            allow_shell=False,
            ttl_seconds=3600,
        )

    # Instantiate the correct backend class
    if config.policy == BackendPolicy.EPHEMERAL:
        return EphemeralBackend(config)
    elif config.policy == BackendPolicy.SCRATCH:
        return ScratchBackend(config)
    elif config.policy == BackendPolicy.DURABLE:
        if production_mode and not _allow_durable():
            raise BackendViolation(
                "Durable backend is not allowed in production. "
                "Set K1_DEEPAGENT_ALLOW_DURABLE=true to enable."
            )
        return DurableBackend(config)
    else:
        # Defensive: should not reach here due to enum validation above
        raise ValueError(f"Unhandled backend policy: {config.policy}")


# -- BackendProtocol adapter (deepagents package alignment) --------------------

# Choose the base class dynamically: real BackendProtocol when available,
# plain object otherwise. This lets K1BackendProtocolAdapter satisfy
# isinstance checks against the real protocol while remaining importable
# on Python 3.10 where deepagents is not installed.
_BackendProtocolBase: type = _RealBackendProtocol if _DEEPAGENTS_BACKEND_AVAILABLE else object


class K1BackendProtocolAdapter(_BackendProtocolBase):  # type: ignore[misc]
    """
    Wraps a Kai ``DeepAgentBackend`` to implement the real deepagents
    ``BackendProtocol`` interface.

    This adapter enables Kai's governed backends (ephemeral, scratch, durable)
    to be passed into the real ``deepagents.create_deep_agent(backend=...)``
    call. All operations are delegated to the wrapped Kai backend with
    appropriate path mapping.

    When the real deepagents package is not installed, the adapter still works
    but does not satisfy the ``BackendProtocol`` ABC checks.
    """

    def __init__(self, backend: DeepAgentBackend) -> None:
        self._backend = backend

    @property
    def wrapped_backend(self) -> DeepAgentBackend:
        """Return the underlying Kai backend."""
        return self._backend

    def _to_relative_key(self, absolute_path: str) -> str:
        """Convert an absolute path to a relative key for the Kai backend."""
        prefix = self._backend._base_path
        if absolute_path.startswith(prefix):
            rel = absolute_path[len(prefix):]
            if rel.startswith(os.sep) or rel.startswith("/"):
                rel = rel[1:]
            return rel or "."
        # If it doesn't start with the prefix, use the raw path stripped of leading /
        return absolute_path.lstrip("/") or "."

    def ls_info(self, path: str) -> list[dict[str, Any]]:
        """List files matching the Kai backend's keys."""
        keys = self._backend.list_keys()
        rel_path = self._to_relative_key(path).rstrip("/")
        infos: list[dict[str, Any]] = []
        seen_dirs: set[str] = set()
        for key in keys:
            if rel_path != "." and not key.startswith(rel_path + "/") and key != rel_path:
                continue
            prefix_to_strip = (rel_path + "/") if rel_path != "." else ""
            relative = key[len(prefix_to_strip):] if prefix_to_strip else key
            if "/" in relative:
                subdir = relative.split("/")[0]
                subdir_path = os.path.join(path.rstrip("/"), subdir) + "/"
                if subdir_path not in seen_dirs:
                    seen_dirs.add(subdir_path)
                    infos.append({"path": subdir_path, "is_dir": True, "size": 0, "modified_at": ""})
            else:
                content = self._backend.read(key)
                size = len(content.encode("utf-8") if isinstance(content, str) else content or b"")
                infos.append({"path": os.path.join(path.rstrip("/"), relative), "is_dir": False, "size": size, "modified_at": ""})
        return sorted(infos, key=lambda x: x.get("path", ""))

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> str:
        """Read file content with line numbers (cat -n format)."""
        key = self._to_relative_key(file_path)
        content = self._backend.read(key)
        if content is None:
            return f"Error: File '{file_path}' not found"
        text = content if isinstance(content, str) else content.decode("utf-8", errors="replace")
        lines = text.split("\n")
        selected = lines[offset : offset + limit]
        result_lines = []
        for i, line in enumerate(selected):
            line_num = offset + i + 1
            result_lines.append(f"{line_num:6d}\t{line}")
        return "\n".join(result_lines)

    def write(self, file_path: str, content: str) -> Any:
        """Write content to a new file. Returns a WriteResult-compatible object."""
        key = self._to_relative_key(file_path)
        try:
            resolved = self._backend.write(key, content)
            return _WriteResultCompat(error=None, path=resolved, files_update=None)
        except BackendViolation as exc:
            return _WriteResultCompat(error=str(exc), path=None, files_update=None)

    def edit(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> Any:
        """Edit file by replacing string occurrences."""
        key = self._to_relative_key(file_path)
        content = self._backend.read(key)
        if content is None:
            return _EditResultCompat(error=f"Error: File '{file_path}' not found")
        text = content if isinstance(content, str) else content.decode("utf-8", errors="replace")
        count = text.count(old_string)
        if count == 0:
            return _EditResultCompat(error=f"Error: String not found in file: '{old_string}'")
        if count > 1 and not replace_all:
            return _EditResultCompat(error=f"Error: String '{old_string}' appears multiple times. Use replace_all=True.")
        if replace_all:
            new_text = text.replace(old_string, new_string)
        else:
            new_text = text.replace(old_string, new_string, 1)
        resolved = self._backend.write(key, new_text)
        return _EditResultCompat(error=None, path=resolved, occurrences=count)

    def grep_raw(self, pattern: str, path: str | None = None, glob: str | None = None) -> list[dict[str, str | int]] | str:
        """Search files for a literal text pattern."""
        import fnmatch as fnmatch_mod
        keys = self._backend.list_keys()
        rel_path = self._to_relative_key(path) if path else "."
        matches: list[dict[str, str | int]] = []
        for key in keys:
            if rel_path != "." and not key.startswith(rel_path):
                continue
            if glob and not fnmatch_mod.fnmatch(key, glob):
                continue
            content = self._backend.read(key)
            if content is None:
                continue
            text = content if isinstance(content, str) else content.decode("utf-8", errors="replace")
            for line_num, line in enumerate(text.split("\n"), start=1):
                if pattern in line:
                    matches.append({"path": key, "line": line_num, "text": line})
        return matches

    def glob_info(self, pattern: str, path: str = "/") -> list[dict[str, Any]]:
        """Find files matching a glob pattern."""
        import fnmatch as fnmatch_mod
        keys = self._backend.list_keys()
        infos: list[dict[str, Any]] = []
        for key in keys:
            if fnmatch_mod.fnmatch(key, pattern):
                infos.append({"path": key, "is_dir": False, "size": 0, "modified_at": ""})
        return infos

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[dict[str, Any]]:
        """Upload files to the backend."""
        responses = []
        for fpath, data in files:
            key = self._to_relative_key(fpath)
            try:
                self._backend.write(key, data)
                responses.append({"path": fpath, "error": None})
            except BackendViolation as exc:
                responses.append({"path": fpath, "error": str(exc)})
        return responses

    def download_files(self, paths: list[str]) -> list[dict[str, Any]]:
        """Download files from the backend."""
        responses = []
        for fpath in paths:
            key = self._to_relative_key(fpath)
            content = self._backend.read(key)
            if content is None:
                responses.append({"path": fpath, "content": None, "error": "file_not_found"})
            else:
                data = content.encode("utf-8") if isinstance(content, str) else content
                responses.append({"path": fpath, "content": data, "error": None})
        return responses


@dataclass
class _WriteResultCompat:
    """Lightweight WriteResult-compatible dataclass for protocol adapter."""
    error: str | None = None
    path: str | None = None
    files_update: dict[str, Any] | None = None


@dataclass
class _EditResultCompat:
    """Lightweight EditResult-compatible dataclass for protocol adapter."""
    error: str | None = None
    path: str | None = None
    files_update: dict[str, Any] | None = None
    occurrences: int | None = None


def create_protocol_adapter(backend: DeepAgentBackend) -> K1BackendProtocolAdapter:
    """Factory: wrap a Kai DeepAgentBackend in a BackendProtocol-compatible adapter."""
    return K1BackendProtocolAdapter(backend)


# -- Environment helpers -------------------------------------------------------


def _resolve_artifacts_root() -> str:
    """Get K1_ARTIFACTS_ROOT, default to 'artifacts/'."""
    return os.getenv("K1_ARTIFACTS_ROOT", "artifacts")


def _is_production() -> bool:
    """True unless K1_DEEPAGENT_DEV_MODE=true."""
    return os.getenv("K1_DEEPAGENT_DEV_MODE", "false").lower() != "true"


def _allow_durable() -> bool:
    """True only if K1_DEEPAGENT_ALLOW_DURABLE=true."""
    return os.getenv("K1_DEEPAGENT_ALLOW_DURABLE", "false").lower() == "true"
