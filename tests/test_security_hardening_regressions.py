from __future__ import annotations

import inspect

import pytest

from apps.backend.src.core.intelligence_engine import IntelligenceEngine
from apps.backend.src.core.mission_graph import _phase_failed
from apps.backend.src.core.tool_runner import ToolRunner
from apps.backend.src.core.praison_sandbox_manager import SandboxConfig, SandboxHandle
from apps.backend.src.routers import model_bidding, ollama
from apps.backend.src.worker.celery_app import run_tool_task


def test_run_tool_task_accepts_extra_headers_kwarg() -> None:
    signature = inspect.signature(run_tool_task)
    assert "extra_headers" in signature.parameters


def test_tool_runner_sanitizes_headers() -> None:
    raw_headers = {
        " X-Test ": "  ok  ",
        "": "ignored",
        "X-Too-Long": "x" * 9000,
        123: "invalid-key",  # type: ignore[dict-item]
        "X-Other": 10,  # type: ignore[dict-item]
    }
    sanitized = ToolRunner._sanitize_headers(raw_headers)  # noqa: SLF001 - targeted unit test
    assert sanitized == {"X-Test": "ok"}


def test_intelligence_engine_item_id_is_stable() -> None:
    engine = IntelligenceEngine()
    first = engine._stable_item_id("nvd", "https://example.com/advisory/1")  # noqa: SLF001
    second = engine._stable_item_id("nvd", "https://example.com/advisory/1")  # noqa: SLF001
    assert first == second
    assert first.startswith("nvd_")


def test_intelligence_engine_normalizes_datetimes_to_utc() -> None:
    engine = IntelligenceEngine()
    parsed = engine._normalize_datetime("2026-01-01T12:30:00Z")  # noqa: SLF001
    assert parsed is not None
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_phase_failed_handles_common_failure_aliases() -> None:
    class _R:
        def __init__(self, status: str) -> None:
            self.status = status

    assert _phase_failed([_R("failed"), _R("timeout")]) is True
    assert _phase_failed([_R("success"), _R("failed")]) is False


@pytest.mark.asyncio
async def test_sandbox_blocks_open_builtin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("K1_SANDBOX_ALLOW_INPROCESS", "true")
    handle = SandboxHandle(SandboxConfig.safe_default(agent_id="tester", execution_mode="live"))
    result = await handle.execute("open('/etc/passwd').read()", timeout_seconds=2)
    assert result.success is False
    assert "open" in result.error.lower()


def test_sensitive_routers_require_auth_dependencies() -> None:
    assert ollama.router.dependencies, "ollama router should enforce role-based auth"
    assert model_bidding.router.dependencies, "model_bidding router should enforce role-based auth"
