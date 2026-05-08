from __future__ import annotations

import logging
import os
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

# Env-controlled defaults so deployments can override without code changes.
_DEFAULT_NETWORK = os.environ.get("KAI_DOCKER_NETWORK", "kai_kai_internal")
_DEFAULT_MEMORY = os.environ.get("KAI_DOCKER_MEMORY", "768m")
_IMAGE_PREFIX = "kai-"

# Per-tool capability requirements (NET_RAW/NET_ADMIN needed for raw-socket tools).
_TOOL_CAPS: dict[str, list[str]] = {
    "nmap": ["NET_RAW", "NET_ADMIN"],
    "masscan": ["NET_RAW", "NET_ADMIN"],
    "naabu": ["NET_RAW", "NET_ADMIN"],
    "ncrack": ["NET_RAW"],
    "responder": ["NET_RAW", "NET_ADMIN"],
    "ipv6toolkit": ["NET_RAW", "NET_ADMIN"],
    "hping3": ["NET_RAW"],
}


@dataclass(slots=True)
class DockerExecutionResult:
    stdout: str
    stderr: str
    exit_code: int
    runtime_ms: int
    image: str
    cmd_args: list[str]


class DockerToolExecutor:
    """
    Runs security tool containers via `docker run` and captures their output.

    Usage::

        executor = DockerToolExecutor()
        if executor.is_available() and executor.image_exists("kai-nmap"):
            result = executor.execute_in_container(
                "kai-nmap",
                ["-sV", "-p", "80,443", "example.com"],
                timeout=120,
            )
    """

    # Class-level availability cache (checked once per process lifetime).
    _checked: bool = False
    _available: bool = False

    def __init__(
        self,
        *,
        network: str | None = None,
        memory_limit: str | None = None,
    ) -> None:
        self.network = network or _DEFAULT_NETWORK
        self.memory_limit = memory_limit or _DEFAULT_MEMORY

    # ------------------------------------------------------------------
    # Availability / image probes
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        """Return True if the Docker daemon is reachable."""
        if not DockerToolExecutor._checked:
            try:
                r = subprocess.run(
                    ["docker", "info"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                )
                DockerToolExecutor._available = r.returncode == 0
            except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
                DockerToolExecutor._available = False
            DockerToolExecutor._checked = True
        return DockerToolExecutor._available

    def image_exists(self, image: str) -> bool:
        """Return True if the named image is present in the local registry."""
        if not self.is_available():
            return False
        try:
            r = subprocess.run(
                ["docker", "image", "inspect", "--format", "{{.Id}}", image],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
            return r.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return False

    @staticmethod
    def tool_image(tool_name: str) -> str:
        """Derive the canonical image name for a tool: ``kai-<tool_name>``."""
        return f"{_IMAGE_PREFIX}{tool_name}"

    # ------------------------------------------------------------------
    # Core execution
    # ------------------------------------------------------------------

    def execute_in_container(
        self,
        image: str,
        cmd_args: list[str],
        *,
        timeout: int = 300,
        tmp_host_dir: str | Path | None = None,
        extra_env: dict[str, str] | None = None,
        max_output_chars: int = 200_000,
        tool_name: str = "",
    ) -> DockerExecutionResult:
        """
        Run ``docker run --rm <image> <cmd_args>`` and return captured output.

        Args:
            image:          Full Docker image name (e.g. ``kai-nmap``).
            cmd_args:       Arguments forwarded to the container's entrypoint.
                            These are the tool arguments *without* the binary
                            name, because the Dockerfile ENTRYPOINT is the binary.
            timeout:        Seconds before the container is killed (exit code 124).
            tmp_host_dir:   Host path mounted at ``/tmp`` inside the container.
                            Required for tools that write output files to ``/tmp``.
            extra_env:      Additional ``--env KEY=VALUE`` pairs.
            max_output_chars: Truncate stdout/stderr at this many characters.
            tool_name:      Used to look up capability requirements (NET_RAW etc.).
        """
        docker_cmd: list[str] = ["docker", "run", "--rm"]

        docker_cmd += ["--network", self.network]
        docker_cmd += ["--memory", self.memory_limit]
        docker_cmd += ["--security-opt", "no-new-privileges:true"]

        # Per-tool Linux capabilities (raw sockets for network scanners).
        for cap in _TOOL_CAPS.get(tool_name, []):
            docker_cmd += ["--cap-add", cap]

        # Mount host /tmp so file-writing tools (e.g. nmap -oX) are accessible.
        if tmp_host_dir is not None:
            tmp_host_dir = Path(tmp_host_dir).resolve()
            tmp_host_dir.mkdir(parents=True, exist_ok=True)
            docker_cmd += ["--volume", f"{tmp_host_dir}:/tmp:rw"]

        for key, val in (extra_env or {}).items():
            docker_cmd += ["--env", f"{key}={val}"]

        docker_cmd.append(image)
        docker_cmd.extend(cmd_args)

        started = time.monotonic()
        stdout = ""
        stderr = ""
        exit_code = -1
        process: subprocess.Popen[bytes] | None = None

        try:
            process = subprocess.Popen(
                docker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=False,
                shell=False,
                start_new_session=True,
            )
            out_bytes, err_bytes = process.communicate(timeout=timeout)
            stdout = _decode(out_bytes)[:max_output_chars]
            stderr = _decode(err_bytes)[:max_output_chars]
            exit_code = int(process.returncode or 0)

        except subprocess.TimeoutExpired as exc:
            stdout = _decode(exc.stdout)[:max_output_chars]
            stderr = (
                _decode(exc.stderr) + f"\ntimeout_exceeded:{timeout}s"
            )[:max_output_chars]
            exit_code = 124
            _terminate(process)

        except OSError as exc:
            stderr = f"docker_oserror:{exc}"
            exit_code = 127

        finally:
            if process is not None and process.poll() is None:
                _terminate(process)

        runtime_ms = max(0, int((time.monotonic() - started) * 1000))
        _log.debug(
            "docker_exec image=%s exit=%d runtime_ms=%d", image, exit_code, runtime_ms
        )
        return DockerExecutionResult(
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            runtime_ms=runtime_ms,
            image=image,
            cmd_args=cmd_args,
        )


# ------------------------------------------------------------------
# Module-level singleton (lazy, shared across all BaseToolAgent instances)
# ------------------------------------------------------------------

_EXECUTOR: DockerToolExecutor | None = None


def get_executor() -> DockerToolExecutor:
    """Return the process-wide DockerToolExecutor singleton."""
    global _EXECUTOR
    if _EXECUTOR is None:
        _EXECUTOR = DockerToolExecutor()
    return _EXECUTOR


def reset_executor() -> None:
    """Reset the singleton and availability cache (test isolation only)."""
    global _EXECUTOR
    _EXECUTOR = None
    DockerToolExecutor._checked = False
    DockerToolExecutor._available = False


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def _decode(value: bytes | str | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _terminate(process: subprocess.Popen[bytes] | None) -> None:
    if process is None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except Exception:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except Exception:
            pass
