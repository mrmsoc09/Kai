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

from apps.backend.src.agents.tools.findomain.agent import FindomainAgent
from apps.backend.src.agents.tools.findomain.schemas import DiscoveryRegistry
from apps.backend.src.core.gemini_orchestrator import GeminiOrchestrator
from apps.backend.src.core.tools import ToolAutonomyTier


class _FakePopen:
    def __init__(self, stdout_text: str, stderr_text: str, returncode: int = 0) -> None:
        self.stdout = io.StringIO(stdout_text)
        self.stderr = io.StringIO(stderr_text)
        self.returncode = returncode
        self.pid = 424242

    def wait(self, timeout: int | None = None) -> int:
        return self.returncode

    def poll(self) -> int:
        return self.returncode


def test_discovery_registry_enrichment() -> None:
    record = DiscoveryRegistry.model_validate(
        {
            "discovered_domain": "api.example.com",
            "source": "passive_findomain",
            "root_domain": "example.com",
            "resolved_ips": ["1.2.3.4"],
            "http_status": 200,
        }
    )
    assert record.discovered_domain == "api.example.com"
    assert record.resolved_ips == ["1.2.3.4"]
    assert record.http_status == 200

    with pytest.raises(ValidationError):
        DiscoveryRegistry.model_validate({"discovered_domain": "bad_domain"})


def test_findomain_parse_json_and_plain_output() -> None:
    agent = FindomainAgent()
    raw = (
        '{"subdomain":"api.example.com","ip":["1.2.3.4"],"http_status":200}\n'
        "portal.example.com\n"
        "portal.example.com\n"
    )
    findings = agent.parse_output(raw, "example.com")
    assert len(findings) == 2
    values = sorted(item["value"] for item in findings)
    assert values == ["api.example.com", "portal.example.com"]
    api = next(item for item in findings if item["value"] == "api.example.com")
    assert api["context"]["resolved_ips"] == ["1.2.3.4"]
    assert api["context"]["http_status"] == 200


def test_findomain_build_command_json_resolved_http_status() -> None:
    agent = FindomainAgent()
    cmd = agent.build_command(
        "example.com",
        {"resolved": True, "http_status": True, "scope_size": 500, "output_file": "/tmp/findomain.json"},
    )
    assert "findomain" in cmd
    assert "--json" in cmd
    assert "--resolved" in cmd
    assert "--http-status" in cmd
    assert "--threads" in cmd
    assert "--output" in cmd


def test_findomain_execute_rate_limit_sets_cooldown(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent = FindomainAgent(memory_root=tmp_path / "memory")
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/findomain")
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: _FakePopen(
            stdout_text='{"subdomain":"api.example.com"}\n',
            stderr_text="external api rate limit exceeded",
            returncode=1,
        ),
    )
    result = agent.execute("example.com", {"proxy": "socks5://127.0.0.1:9050"})
    assert result.status == "cooldown"
    telemetry = result.target_context.get("telemetry", [])
    assert any(event.get("key") == "AGENT_STATUS" and event.get("value") == "COOLDOWN" for event in telemetry)


def test_findomain_execute_emits_telemetry_and_visuals(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent = FindomainAgent(memory_root=tmp_path / "memory2")
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/findomain")
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: _FakePopen(
            stdout_text=(
                '{"subdomain":"a.example.com","ip":["1.1.1.1"],"http_status":200}\n'
                '{"subdomain":"b.example.com","ip":["1.1.1.2"],"http_status":200}\n'
                '{"subdomain":"c.example.com"}\n'
                '{"subdomain":"d.example.com"}\n'
                '{"subdomain":"e.example.com"}\n'
                '{"subdomain":"f.example.com"}\n'
                '{"subdomain":"g.example.com"}\n'
                '{"subdomain":"h.example.com"}\n'
                '{"subdomain":"i.example.com"}\n'
                '{"subdomain":"j.example.com"}\n'
            ),
            stderr_text="",
            returncode=0,
        ),
    )
    result = agent.execute("example.com", {"proxy": "socks5://127.0.0.1:9050"})
    assert result.status == "success"
    assert result.target_context.get("unique_subdomains") == 10
    assert result.target_context.get("resolved_hosts", 0) >= 2
    telemetry = result.target_context.get("telemetry", [])
    assert any(event.get("key") == "UNIQUE_SUBDOMAINS" for event in telemetry)
    assert any(event.get("key") == "RESOLVED_HOSTS" for event in telemetry)
    assert any(
        event.get("key") == "EventLog" and "DIGITAL_RAIN:GOLD_TINT:10" in str(event.get("value"))
        for event in telemetry
    )


def test_findomain_opsec_blocks_active_resolution_without_tunnel(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent = FindomainAgent(memory_root=tmp_path / "memory3")
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/findomain")
    monkeypatch.setattr(
        agent,
        "_runtime_environment",
        {
            "vpn_interfaces": ("tun0",),
            "vpn_up_interfaces": [],
            "proxychains_enabled": False,
        },
    )
    result = agent.execute("example.com", {"resolved": True, "http_status": True})
    assert result.status == "failure"
    assert "Sovereign Network Layer not detected" in result.target_context.get("stderr", "")


def test_findomain_registry_yaml_has_subdomain_enumeration_category() -> None:
    registry_path = Path("tools/registry/tool_registry.yaml")
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    tools = payload.get("tools", []) if isinstance(payload, dict) else []
    entry = next((item for item in tools if item.get("name") == "findomain"), None)
    assert entry is not None
    assert entry.get("agent_class") == "FindomainAgent"
    assert entry.get("service_category") == "SUBDOMAIN_ENUMERATION"
    assert "SUBDOMAIN_ENUMERATION" in entry.get("tags", [])


@pytest.mark.asyncio
async def test_findomain_orchestrator_dispatch_handshake(
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
            if tool_name == "findomain":
                return _DummyTool()
            return None

    monkeypatch.setattr("apps.backend.src.core.tools.initialize_default_tools", lambda: None)
    monkeypatch.setattr("apps.backend.src.core.tools.get_registry", lambda: _DummyRegistry())
    fake_tool_runner_module = types.ModuleType("apps.backend.src.core.tool_runner")
    fake_tool_runner_module.tool_runner = types.SimpleNamespace(
        enqueue=lambda **kwargs: "task-findomain-1"
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
    dispatch = await orchestrator._dispatch_tool("findomain", {"target": "example.com"})
    assert dispatch["status"] == "queued"
    assert dispatch["tool"] == "findomain"
    assert dispatch["task_id"] == "task-findomain-1"

