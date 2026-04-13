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

from apps.backend.src.agents.tools.httpx_probe.agent import HttpxProbeAgent
from apps.backend.src.agents.tools.httpx_probe.schemas import HttpxRawRecord, ServiceRegistry
from apps.backend.src.core.gemini_orchestrator import GeminiOrchestrator
from apps.backend.src.core.tools import ToolAutonomyTier


class _FakePopen:
    def __init__(self, stdout_text: str, stderr_text: str, returncode: int = 0) -> None:
        self.stdin = io.StringIO()
        self.stdout = io.StringIO(stdout_text)
        self.stderr = io.StringIO(stderr_text)
        self.returncode = returncode
        self.pid = 123456

    def wait(self, timeout: int | None = None) -> int:
        return self.returncode

    def poll(self) -> int:
        return self.returncode


def test_service_registry_handles_tech_stack_formats() -> None:
    raw_list = HttpxRawRecord.model_validate(
        {
            "url": "https://app.example.com",
            "status_code": 200,
            "tech": ["nginx", "react"],
            "server": "nginx",
            "content_length": 123,
        }
    )
    reg_list = ServiceRegistry.from_raw(raw_list, target_domain="example.com")
    assert reg_list.tech_stack == ["nginx", "react"]
    assert reg_list.http_status == 200

    raw_string = HttpxRawRecord.model_validate(
        {
            "url": "https://api.example.com",
            "status_code": "403",
            "tech": "nginx, express;node",
            "webserver": "cloudflare",
            "content_length": "456",
        }
    )
    reg_string = ServiceRegistry.from_raw(raw_string, target_domain="example.com")
    assert reg_string.http_status == 403
    assert sorted(reg_string.tech_stack) == ["express", "nginx", "node"]
    assert reg_string.server_header == "cloudflare"


def test_service_registry_rejects_malformed_url() -> None:
    with pytest.raises(ValidationError):
        HttpxRawRecord.model_validate({"url": "not-a-url", "status_code": 200})


def test_httpx_parse_output_maps_json_to_service_registry() -> None:
    agent = HttpxProbeAgent()
    raw = (
        '{"url":"https://api.example.com","status_code":403,"title":"Forbidden","tech":["nginx"],'
        '"server":"cloudflare","content_length":0,"cdn":true,"ip":"1.1.1.1","cname":"api.edge.example.net"}\n'
    )
    findings = agent.parse_output(raw, "example.com")
    assert len(findings) == 1
    finding = findings[0]
    assert finding["url"] == "https://api.example.com"
    assert finding["context"]["status_code"] == 403
    assert finding["context"]["title"] == "Forbidden"
    assert finding["context"]["tech"] == ["nginx"]
    assert finding["context"]["server"] == "cloudflare"
    assert finding["context"]["content_length"] == 0


def test_httpx_execute_emits_live_service_telemetry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agent = HttpxProbeAgent(memory_root=tmp_path / "memory")

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/httpx")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args, returncode=0, stdout="httpx v1.6.5", stderr=""
        ),
    )
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: _FakePopen(
            stdout_text=(
                '{"url":"https://a.example.com","status_code":200}\n'
                '{"url":"https://b.example.com","status_code":302}\n'
                '{"url":"https://c.example.com","status_code":404}\n'
                '{"url":"https://d.example.com","status_code":403}\n'
            ),
            stderr_text="",
            returncode=0,
        ),
    )

    result = agent.execute("example.com")
    assert result.status == "success"
    assert result.target_context.get("live_web_services") == 3
    telemetry = result.target_context.get("telemetry", [])
    assert any(event.get("key") == "LIVE_WEB_SERVICES" for event in telemetry)
    assert any(
        event.get("key") == "EventLog" and "WEB_SERVICE_DETECTED_GOLD:" in str(event.get("value"))
        for event in telemetry
    )


def test_httpx_execute_requires_sovereign_network_when_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    agent = HttpxProbeAgent(memory_root=tmp_path / "memory2")

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/httpx")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args, returncode=0, stdout="httpx v1.6.5", stderr=""
        ),
    )
    monkeypatch.setenv("K1_REQUIRE_SOVEREIGN_NETWORK", "true")
    monkeypatch.setattr(
        agent,
        "_runtime_environment",
        {
            "vpn_interfaces": ("tun0",),
            "vpn_up_interfaces": [],
            "proxychains_file": None,
            "proxychains_enabled": False,
        },
    )

    result = agent.execute("example.com")
    assert result.status == "failure"
    assert "Sovereign Network Layer not detected" in result.target_context.get("stderr", "")


def test_httpx_registry_yaml_has_service_enumeration_category() -> None:
    registry_path = Path("tools/registry/tool_registry.yaml")
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    tools = payload.get("tools", []) if isinstance(payload, dict) else []
    entry = next((item for item in tools if item.get("name") == "httpx_probe"), None)
    assert entry is not None
    assert entry.get("agent_class") == "HttpxProbeAgent"
    assert entry.get("service_category") == "SERVICE_ENUMERATION"
    assert "SERVICE_ENUMERATION" in entry.get("tags", [])


@pytest.mark.asyncio
async def test_httpx_orchestrator_dispatch_handshake(
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
            if tool_name == "httpx_probe":
                return _DummyTool()
            return None

    monkeypatch.setattr("apps.backend.src.core.tools.initialize_default_tools", lambda: None)
    monkeypatch.setattr("apps.backend.src.core.tools.get_registry", lambda: _DummyRegistry())
    fake_tool_runner_module = types.ModuleType("apps.backend.src.core.tool_runner")
    fake_tool_runner_module.tool_runner = types.SimpleNamespace(
        enqueue=lambda **kwargs: "task-httpx-1"
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
    dispatch = await orchestrator._dispatch_tool("httpx_probe", {"target": "https://example.com"})
    assert dispatch["status"] == "queued"
    assert dispatch["tool"] == "httpx_probe"
    assert dispatch["task_id"] == "task-httpx-1"
