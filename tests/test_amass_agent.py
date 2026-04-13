from __future__ import annotations

import io
import subprocess
import sys
import types
from typing import Any

import pytest

from apps.backend.src.agents.tools.amass.agent import AmassAgent
from apps.backend.src.agents.tools.amass.schemas import AmassNormalizedAsset, AmassRawRecord
from apps.backend.src.core.gemini_orchestrator import GeminiOrchestrator
from apps.backend.src.core.tools import ToolAutonomyTier


def test_amass_schema_mapping_contract() -> None:
    raw = AmassRawRecord.model_validate(
        {
            "name": "api.example.com",
            "domain": "example.com",
            "addresses": [{"ip": "1.2.3.4"}, "5.6.7.8"],
            "source": "censys",
            "tag": "api",
        }
    )

    normalized = AmassNormalizedAsset.from_raw(raw)

    assert normalized.fqdn == "api.example.com"
    assert normalized.ip_registry == ["1.2.3.4", "5.6.7.8"]
    assert normalized.intel_origin == "censys"


def test_amass_parse_output_requires_json_lines() -> None:
    agent = AmassAgent()
    mixed_output = (
        "api.example.com\n"
        '{"name":"api.example.com","addresses":[{"ip":"1.2.3.4"}],"source":"crtsh"}\n'
    )
    findings = agent.parse_output(mixed_output, "example.com")

    assert len(findings) == 1
    finding = findings[0]
    assert finding["subdomain"] == "api.example.com"
    assert finding["context"]["ip_registry"] == ["1.2.3.4"]
    assert finding["context"]["intel_origin"] == "crtsh"


class _FakePopen:
    def __init__(self, stdout_text: str, stderr_text: str, returncode: int = 0) -> None:
        self.stdout = io.StringIO(stdout_text)
        self.stderr = io.StringIO(stderr_text)
        self.returncode = returncode
        self.pid = 99999

    def wait(self, timeout: int | None = None) -> int:
        return self.returncode

    def poll(self) -> int:
        return self.returncode


def test_amass_execute_rate_limit_transitions_to_cooldown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    agent = AmassAgent(memory_root=tmp_path / "amass-memory")

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/amass")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args=args, returncode=0, stdout="v5.8.0", stderr=""),
    )
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: _FakePopen(
            stdout_text='{"name":"api.example.com","addresses":[{"ip":"1.2.3.4"}],"source":"archive"}\n',
            stderr_text="HTTP 429 Too Many Requests\n",
            returncode=1,
        ),
    )

    result = agent.execute("example.com", mission_id="mission-amass-test")

    assert result.status == "cooldown"
    assert any(
        event.get("key") == "AGENT_STATUS" and event.get("value") == "COOLDOWN"
        for event in result.target_context.get("telemetry", [])
    )
    assert result.target_context.get("discovery_count") == 1


@pytest.mark.asyncio
async def test_gemini_dispatch_uses_standard_registry_for_amass(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _DummyTool:
        autonomy_tier = ToolAutonomyTier.TIER_1_NOTIFY

        @staticmethod
        def validate_parameters(**kwargs: Any) -> tuple[bool, str | None]:
            return True, None

    class _DummyRegistry:
        @staticmethod
        def get(tool_name: str) -> Any:
            if tool_name == "amass_enum":
                return _DummyTool()
            return None

    monkeypatch.setattr("apps.backend.src.core.tools.initialize_default_tools", lambda: None)
    monkeypatch.setattr("apps.backend.src.core.tools.get_registry", lambda: _DummyRegistry())
    fake_tool_runner_module = types.ModuleType("apps.backend.src.core.tool_runner")
    fake_tool_runner_module.tool_runner = types.SimpleNamespace(
        enqueue=lambda **kwargs: "task-amass-enum-1"
    )
    monkeypatch.setitem(sys.modules, "apps.backend.src.core.tool_runner", fake_tool_runner_module)
    class _InlineLoop:
        @staticmethod
        async def run_in_executor(executor: Any, func: Any) -> Any:
            return func()

    monkeypatch.setattr(
        "apps.backend.src.core.gemini_orchestrator.asyncio.get_running_loop",
        lambda: _InlineLoop(),
    )

    orchestrator = object.__new__(GeminiOrchestrator)
    dispatch = await orchestrator._dispatch_tool("amass_enum", {"domain": "example.com"})

    assert dispatch["status"] == "queued"
    assert dispatch["tool"] == "amass_enum"
    assert dispatch["task_id"] == "task-amass-enum-1"
