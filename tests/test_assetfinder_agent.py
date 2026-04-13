from __future__ import annotations

import io
import subprocess
import sys
import types
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from apps.backend.src.agents.tools.assetfinder.agent import AssetfinderAgent
from apps.backend.src.agents.tools.assetfinder.schemas import DiscoveryRegistry
from apps.backend.src.core.gemini_orchestrator import GeminiOrchestrator
from apps.backend.src.core.tools import ToolAutonomyTier


class _FakePopen:
    def __init__(self, stdout_text: str, stderr_text: str, returncode: int = 0) -> None:
        self.stdout = io.StringIO(stdout_text)
        self.stderr = io.StringIO(stderr_text)
        self.returncode = returncode
        self.pid = 515151

    def wait(self, timeout: int | None = None) -> int:
        return self.returncode

    def poll(self) -> int:
        return self.returncode


def test_discovery_registry_validation() -> None:
    registry = DiscoveryRegistry.model_validate(
        {
            "discovered_domain": "api.example.com",
            "source": "passive_assetfinder",
            "root_domain": "example.com",
        }
    )
    assert registry.discovered_domain == "api.example.com"
    assert registry.source == "passive_assetfinder"

    with pytest.raises(ValidationError):
        DiscoveryRegistry.model_validate({"discovered_domain": "invalid_domain", "source": "x"})


def test_assetfinder_parse_output_deduplicates_and_normalizes() -> None:
    agent = AssetfinderAgent()
    raw = (
        "api.example.com\n"
        "api.example.com\n"
        "*.staging.example.com\n"
        "portal.example.com\n"
        "not a domain\n"
    )
    findings = agent.parse_output(raw, "example.com")
    values = sorted({item["value"] for item in findings})
    assert values == ["api.example.com", "portal.example.com", "staging.example.com"]
    assert all(item["context"]["source"] == "passive_assetfinder" for item in findings)


def test_assetfinder_build_command_uses_subs_only_by_default() -> None:
    agent = AssetfinderAgent()
    cmd = agent.build_command("example.com")
    assert cmd[0] == "assetfinder"
    assert "--subs-only" in cmd
    assert "example.com" in cmd


def test_assetfinder_execute_emits_telemetry_and_discovery_trigger(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent = AssetfinderAgent(memory_root=tmp_path / "memory")
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/assetfinder")
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: _FakePopen(
            stdout_text=(
                "api.example.com\n"
                "admin.example.com\n"
                "dev.example.com\n"
                "portal.example.com\n"
                "mail.example.com\n"
                "staging.example.com\n"
                "internal.example.com\n"
                "beta.example.com\n"
                "alpha.example.com\n"
                "qa.example.com\n"
                "api.example.com\n"
            ),
            stderr_text="",
            returncode=0,
        ),
    )

    result = agent.execute("example.com", {"proxy": "socks5://127.0.0.1:9050"})
    assert result.status == "success"
    assert result.target_context.get("passive_assets_found") == 10
    trigger = result.target_context.get("discovery_trigger", {})
    assert trigger.get("next_agent") == "findomain"
    telemetry = result.target_context.get("telemetry", [])
    assert any(event.get("key") == "PASSIVE_ASSETS_FOUND" for event in telemetry)
    assert any(event.get("key") == "DISCOVERY_TRIGGER" for event in telemetry)
    assert any(
        event.get("key") == "EventLog" and "STAR_MAP_IGNITION:EXPANDING_WHITE_NODES:10" in str(event.get("value"))
        for event in telemetry
    )


def test_assetfinder_listener_mode_ingests_multiple_targets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent = AssetfinderAgent(memory_root=tmp_path / "memory2")
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/assetfinder")

    calls: list[list[str]] = []

    def _fake_popen(*args: Any, **kwargs: Any) -> _FakePopen:
        cmd = list(args[0]) if args else []
        calls.append(cmd)
        target = cmd[-1]
        return _FakePopen(stdout_text=f"api.{target}\n", stderr_text="", returncode=0)

    monkeypatch.setattr(subprocess, "Popen", _fake_popen)

    result = agent.execute(
        "example.com",
        {
            "listener_mode": True,
            "input_data": "example.com\nexample.org\n",
            "proxy": "socks5://127.0.0.1:9050",
        },
    )
    assert result.status == "success"
    assert len(calls) == 2
    assert result.target_context.get("passive_assets_found") == 2


def test_assetfinder_registry_yaml_has_passive_recon_category() -> None:
    registry_path = Path("tools/registry/tool_registry.yaml")
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    tools = payload.get("tools", []) if isinstance(payload, dict) else []
    entry = next((item for item in tools if item.get("name") == "assetfinder"), None)
    assert entry is not None
    assert entry.get("agent_class") == "AssetfinderAgent"
    assert entry.get("service_category") == "PASSIVE_RECON"
    assert "PASSIVE_RECON" in entry.get("tags", [])


@pytest.mark.asyncio
async def test_assetfinder_orchestrator_dispatch_handshake(
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
            if tool_name == "assetfinder":
                return _DummyTool()
            return None

    monkeypatch.setattr("apps.backend.src.core.tools.initialize_default_tools", lambda: None)
    monkeypatch.setattr("apps.backend.src.core.tools.get_registry", lambda: _DummyRegistry())
    fake_tool_runner_module = types.ModuleType("apps.backend.src.core.tool_runner")
    fake_tool_runner_module.tool_runner = types.SimpleNamespace(
        enqueue=lambda **kwargs: "task-assetfinder-1"
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
    dispatch = await orchestrator._dispatch_tool("assetfinder", {"target": "example.com"})
    assert dispatch["status"] == "queued"
    assert dispatch["tool"] == "assetfinder"
    assert dispatch["task_id"] == "task-assetfinder-1"
