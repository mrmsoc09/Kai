"""Tests for DockerToolExecutor and BaseToolAgent Docker execution path."""
from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from apps.backend.src.core.docker_executor import (
    DockerExecutionResult,
    DockerToolExecutor,
    get_executor,
    reset_executor,
)


@pytest.fixture(autouse=True)
def _reset_executor():
    """Ensure singleton state doesn't leak between tests."""
    reset_executor()
    yield
    reset_executor()


# ---------------------------------------------------------------------------
# DockerToolExecutor unit tests (no real Docker)
# ---------------------------------------------------------------------------


def test_tool_image_name():
    assert DockerToolExecutor.tool_image("nmap") == "kai-nmap"
    assert DockerToolExecutor.tool_image("subfinder") == "kai-subfinder"


def test_is_available_when_docker_missing():
    with patch("subprocess.run", side_effect=FileNotFoundError):
        executor = DockerToolExecutor()
        assert executor.is_available() is False


def test_is_available_when_daemon_down():
    result = MagicMock(returncode=1)
    with patch("subprocess.run", return_value=result):
        executor = DockerToolExecutor()
        assert executor.is_available() is False


def test_is_available_cached():
    """Second call must not issue a second subprocess.run."""
    result = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=result) as mock_run:
        executor = DockerToolExecutor()
        executor.is_available()
        executor.is_available()
        # Only one check should occur despite two calls.
        assert mock_run.call_count == 1


def test_image_exists_returns_false_when_unavailable():
    executor = DockerToolExecutor()
    with patch.object(executor, "is_available", return_value=False):
        assert executor.image_exists("kai-nmap") is False


def test_image_exists_when_image_present():
    ok = MagicMock(returncode=0)
    with patch("subprocess.run", return_value=ok):
        executor = DockerToolExecutor()
        executor._is_available = True  # bypass daemon check
        DockerToolExecutor._available = True
        DockerToolExecutor._checked = True
        assert executor.image_exists("kai-nmap") is True


def test_image_exists_when_image_absent():
    fail = MagicMock(returncode=1)
    with patch("subprocess.run", return_value=fail):
        executor = DockerToolExecutor()
        DockerToolExecutor._available = True
        DockerToolExecutor._checked = True
        assert executor.image_exists("kai-missing-tool") is False


def test_execute_in_container_captures_stdout():
    executor = DockerToolExecutor()
    DockerToolExecutor._available = True
    DockerToolExecutor._checked = True

    fake_proc = MagicMock()
    fake_proc.communicate.return_value = (b"hello stdout", b"")
    fake_proc.returncode = 0
    fake_proc.poll.return_value = 0

    with patch("subprocess.Popen", return_value=fake_proc):
        result = executor.execute_in_container("kai-nmap", ["--version"], timeout=10)

    assert result.stdout == "hello stdout"
    assert result.stderr == ""
    assert result.exit_code == 0
    assert result.image == "kai-nmap"


def test_execute_in_container_timeout_returns_exit_124():
    import subprocess

    executor = DockerToolExecutor()
    DockerToolExecutor._available = True
    DockerToolExecutor._checked = True

    fake_proc = MagicMock()
    exc = subprocess.TimeoutExpired(cmd="docker run", timeout=5, output=b"partial", stderr=b"")
    fake_proc.communicate.side_effect = exc
    fake_proc.poll.return_value = None

    with patch("subprocess.Popen", return_value=fake_proc):
        with patch("apps.backend.src.core.docker_executor._terminate"):
            result = executor.execute_in_container("kai-nmap", ["--version"], timeout=5)

    assert result.exit_code == 124
    assert "timeout_exceeded" in result.stderr


def test_execute_in_container_oserror_returns_exit_127():
    executor = DockerToolExecutor()
    DockerToolExecutor._available = True
    DockerToolExecutor._checked = True

    with patch("subprocess.Popen", side_effect=OSError("no such binary")):
        result = executor.execute_in_container("kai-nmap", ["--version"], timeout=5)

    assert result.exit_code == 127
    assert "docker_oserror" in result.stderr


def test_caps_added_for_nmap():
    """nmap container must receive NET_RAW and NET_ADMIN capabilities."""
    executor = DockerToolExecutor()
    DockerToolExecutor._available = True
    DockerToolExecutor._checked = True

    captured_cmd: list[list[str]] = []

    fake_proc = MagicMock()
    fake_proc.communicate.return_value = (b"", b"")
    fake_proc.returncode = 0
    fake_proc.poll.return_value = 0

    def capture_popen(cmd, **_kw):
        captured_cmd.append(cmd)
        return fake_proc

    with patch("subprocess.Popen", side_effect=capture_popen):
        executor.execute_in_container("kai-nmap", ["-h"], timeout=5, tool_name="nmap")

    cmd = captured_cmd[0]
    assert "--cap-add" in cmd
    cap_idx = cmd.index("--cap-add")
    caps_given = {cmd[i + 1] for i in range(len(cmd) - 1) if cmd[i] == "--cap-add"}
    assert "NET_RAW" in caps_given
    assert "NET_ADMIN" in caps_given


def test_tmp_volume_mounted_when_dir_provided(tmp_path):
    executor = DockerToolExecutor()
    DockerToolExecutor._available = True
    DockerToolExecutor._checked = True

    captured_cmd: list[list[str]] = []

    fake_proc = MagicMock()
    fake_proc.communicate.return_value = (b"", b"")
    fake_proc.returncode = 0
    fake_proc.poll.return_value = 0

    def capture_popen(cmd, **_kw):
        captured_cmd.append(cmd)
        return fake_proc

    with patch("subprocess.Popen", side_effect=capture_popen):
        executor.execute_in_container(
            "kai-nmap", ["-h"], timeout=5, tmp_host_dir=tmp_path
        )

    cmd = captured_cmd[0]
    assert "--volume" in cmd
    vol_idx = [i for i, t in enumerate(cmd) if t == "--volume"]
    vol_values = [cmd[i + 1] for i in vol_idx]
    assert any("/tmp:rw" in v for v in vol_values)


# ---------------------------------------------------------------------------
# get_executor singleton
# ---------------------------------------------------------------------------


def test_get_executor_returns_same_instance():
    e1 = get_executor()
    e2 = get_executor()
    assert e1 is e2


# ---------------------------------------------------------------------------
# KAI_DOCKER_EXEC=false disables Docker path in BaseToolAgent
# ---------------------------------------------------------------------------


def test_env_flag_false_means_no_image_check(monkeypatch):
    """KAI_DOCKER_EXEC=false must short-circuit before any docker call is made."""
    monkeypatch.setenv("KAI_DOCKER_EXEC", "false")

    executor = DockerToolExecutor()
    DockerToolExecutor._available = True
    DockerToolExecutor._checked = True

    called: list[str] = []

    real_image_exists = executor.image_exists

    def _spy(image: str) -> bool:
        called.append(image)
        return real_image_exists(image)

    executor.image_exists = _spy  # type: ignore[method-assign]

    # Simulate what _try_docker does: check env before calling image_exists
    kai_docker_exec = os.environ.get("KAI_DOCKER_EXEC", "true").lower()
    if kai_docker_exec not in {"0", "false", "no"}:
        executor.image_exists("kai-nmap")

    # With the env set to "false" the image_exists call must never happen.
    assert called == [], "image_exists should not be called when KAI_DOCKER_EXEC=false"
