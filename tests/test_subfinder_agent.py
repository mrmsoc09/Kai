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

from apps.backend.src.agents.tools.subfinder.agent import SubfinderAgent
from apps.backend.src.agents.tools.subfinder.schemas import IntelRegistry, SubfinderRawRecord
from apps.backend.src.core.gemini_orchestrator import GeminiOrchestrator
from apps.backend.src.core.tools import ToolAutonomyTier


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


def test_subfinder_schema_rejects_malformed_data() -> None:
    with pytest.raises(ValidationError):
        SubfinderRawRecord.model_validate({"host": "bad..host", "source": "crtsh"})

    raw = SubfinderRawRecord.model_validate(
        {"host": "api.example.com", "source": "chaos", "ip": ["1.2.3.4"]}
    )
    normalized = IntelRegistry.from_raw(raw)
    assert normalized.fqdn == "api.example.com"
    assert normalized.intel_origin == "chaos"
    assert normalized.resolved_ips == ["1.2.3.4"]


def test_subfinder_parse_output_maps_json_to_intel_registry() -> None:
    agent = SubfinderAgent()
    raw_output = (
        '{"host":"api.example.com","source":"github","ip":"1.2.3.4"}\n'
        "legacy.example.com\n"  # backward-compatible fallback parser
    )
    findings = agent.parse_output(raw_output, "example.com")

    assert len(findings) == 2
    first = findings[0]
    assert first["subdomain"] == "api.example.com"
    assert first["context"]["intel_origin"] == "github"
    assert first["context"]["resolved_ips"] == ["1.2.3.4"]


def test_subfinder_execute_caps_discovery_and_sets_partial(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    provider = tmp_path / "provider-config.yaml"
    provider.write_text(
        """
chaos:
  - key: "x"
github:
  - key: "y"
shodan:
  - key: "z"
""".strip(),
        encoding="utf-8",
    )

    agent = SubfinderAgent(memory_root=tmp_path / "memory")

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/subfinder")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args, returncode=0, stdout="v2.7.0", stderr=""
        ),
    )
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: _FakePopen(
            stdout_text=(
                '{"host":"a.example.com","source":"chaos"}\n'
                '{"host":"b.example.com","source":"chaos"}\n'
                '{"host":"c.example.com","source":"chaos"}\n'
            ),
            stderr_text="",
            returncode=0,
        ),
    )

    result = agent.execute(
        "example.com",
        options={"provider_config": str(provider), "max_discovery_cap": 2},
        mission_id="mission-subfinder-cap",
    )

    assert result.status == "partial"
    assert result.target_context.get("cap_reached") is True
    assert result.target_context.get("discovery_count") == 2


def test_subfinder_execute_rate_limit_sets_cooldown(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    provider = tmp_path / "provider-config.yaml"
    provider.write_text("chaos: []\ngithub: []\nshodan: []\n", encoding="utf-8")

    agent = SubfinderAgent(memory_root=tmp_path / "memory2")

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/subfinder")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args, returncode=0, stdout="v2.7.0", stderr=""
        ),
    )
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: _FakePopen(
            stdout_text='{"host":"api.example.com","source":"github"}\n',
            stderr_text="api rate limit exceeded",
            returncode=1,
        ),
    )

    result = agent.execute("example.com", options={"provider_config": str(provider)})
    assert result.status == "cooldown"
    assert any(
        event.get("key") == "AGENT_STATUS" and event.get("value") == "COOLDOWN"
        for event in result.target_context.get("telemetry", [])
    )


def test_subfinder_respects_sovereign_network_requirement(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    provider = tmp_path / "provider-config.yaml"
    provider.write_text("chaos: []\ngithub: []\nshodan: []\n", encoding="utf-8")
    agent = SubfinderAgent(memory_root=tmp_path / "memory3")

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/subfinder")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args, returncode=0, stdout="v2.7.0", stderr=""
        ),
    )
    monkeypatch.setenv("K1_REQUIRE_SOVEREIGN_NETWORK", "true")
    monkeypatch.setattr(agent, "_runtime_environment", {
        "vpn_interfaces": ("tun0",),
        "vpn_up_interfaces": [],
        "proxychains_file": None,
        "proxychains_enabled": False,
    })

    result = agent.execute("example.com", options={"provider_config": str(provider)})
    assert result.status == "failure"
    assert "Sovereign Network Layer not detected" in result.target_context.get("stderr", "")


def test_subfinder_registry_yaml_has_recon_passive_tag() -> None:
    registry_path = Path("tools/registry/tool_registry.yaml")
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    tools = payload.get("tools", []) if isinstance(payload, dict) else []
    subfinder_entry = next((item for item in tools if item.get("name") == "subfinder"), None)

    assert subfinder_entry is not None
    assert subfinder_entry.get("agent_class") == "SubfinderAgent"
    tags = subfinder_entry.get("tags", [])
    assert "RECON_PASSIVE" in tags


@pytest.mark.asyncio
async def test_subfinder_orchestrator_dispatch_handshake(
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
            if tool_name == "subfinder":
                return _DummyTool()
            return None

    monkeypatch.setattr("apps.backend.src.core.tools.initialize_default_tools", lambda: None)
    monkeypatch.setattr("apps.backend.src.core.tools.get_registry", lambda: _DummyRegistry())

    fake_tool_runner_module = types.ModuleType("apps.backend.src.core.tool_runner")
    fake_tool_runner_module.tool_runner = types.SimpleNamespace(
        enqueue=lambda **kwargs: "task-subfinder-1"
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
    dispatch = await orchestrator._dispatch_tool("subfinder", {"domain": "example.com"})

    assert dispatch["status"] == "queued"
    assert dispatch["tool"] == "subfinder"
    assert dispatch["task_id"] == "task-subfinder-1"
