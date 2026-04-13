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

from apps.backend.src.agents.tools.kiterunner.agent import KiterunnerAgent
from apps.backend.src.agents.tools.kiterunner.schemas import EndpointRegistry, KiterunnerRawRecord
from apps.backend.src.agents.tools.kiterunner.wordlists import KiterunnerWordlistManager
from apps.backend.src.core.gemini_orchestrator import GeminiOrchestrator
from apps.backend.src.core.tools import ToolAutonomyTier


class _FakePopen:
    def __init__(self, stdout_text: str, stderr_text: str, returncode: int = 0) -> None:
        self.stdout = io.StringIO(stdout_text)
        self.stderr = io.StringIO(stderr_text)
        self.returncode = returncode
        self.pid = 636363

    def wait(self, timeout: int | None = None) -> int:
        return self.returncode

    def poll(self) -> int:
        return self.returncode


def test_endpoint_registry_mapping_contract() -> None:
    raw = KiterunnerRawRecord.model_validate(
        {
            "url": "https://api.example.com/api/v1/users",
            "method": "GET",
            "status": 200,
            "content_length": 321,
        }
    )
    registry = EndpointRegistry.from_raw(raw, target_url="https://api.example.com")
    assert registry.endpoint_path == "/api/v1/users"
    assert registry.http_status == 200
    assert registry.http_method == "GET"
    assert registry.response_size == 321


def test_kiterunner_schema_rejects_invalid_url() -> None:
    with pytest.raises(ValidationError):
        KiterunnerRawRecord.model_validate({"url": "not-a-url", "status": 200})


def test_wordlist_manager_selects_swagger_wordlist() -> None:
    manager = KiterunnerWordlistManager()
    selected = manager.select_wordlist(tech_stack=["openapi", "nginx"], mode="scan")
    assert selected.endswith("swagger-list.kite")


def test_kiterunner_build_command_brute_mode_uses_delay_and_concurrency() -> None:
    agent = KiterunnerAgent()
    cmd = agent.build_command(
        "https://api.example.com",
        {
            "mode": "brute",
            "concurrency": 20,
            "delay_ms": 120,
            "wordlist": "/tmp/custom.kite",
        },
    )
    assert "kr" in cmd
    assert "brute" in cmd
    assert "-w" in cmd and "/tmp/custom.kite" in cmd
    assert "-c" in cmd and "20" in cmd
    assert "--delay" in cmd and "120" in cmd


def test_kiterunner_parse_output_handles_json_and_legacy() -> None:
    agent = KiterunnerAgent()
    raw_output = (
        '{"url":"https://api.example.com/api/v2/internal","method":"GET","status":403,"content_length":12}\n'
        "[POST] [200] [456] https://api.example.com/api/v1/users\n"
    )
    findings = agent.parse_output(raw_output, "https://api.example.com")
    assert len(findings) == 2
    assert findings[0]["context"]["endpoint_path"] == "/api/v2/internal"
    assert findings[0]["context"]["status_code"] == "403"
    assert findings[1]["context"]["method"] == "POST"
    assert findings[1]["context"]["status_code"] == "200"


def test_kiterunner_execute_emits_telemetry_and_recursive_queue(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent = KiterunnerAgent(memory_root=tmp_path / "memory")
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/kr")
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: _FakePopen(
            stdout_text=(
                '{"url":"https://api.example.com/api/v2/internal","method":"GET","status":200,"content_length":50}\n'
                '{"url":"https://api.example.com/api/v1/users","method":"POST","status":403,"content_length":20}\n'
            ),
            stderr_text="",
            returncode=0,
        ),
    )
    result = agent.execute(
        "https://api.example.com",
        {
            "proxy": "socks5://127.0.0.1:9050",
            "scan_depth": 1,
            "max_depth": 2,
            "enable_recursive": True,
        },
    )
    assert result.status == "success"
    assert result.target_context.get("api_routes_discovered") == 2
    recursive_queue = result.target_context.get("recursive_scan_queue", [])
    assert any("/api/v2/internal" in item for item in recursive_queue)
    telemetry = result.target_context.get("telemetry", [])
    assert any(event.get("key") == "API_ROUTES_DISCOVERED" for event in telemetry)
    assert any(event.get("key") == "SCAN_DEPTH" for event in telemetry)
    assert any(
        event.get("key") == "EventLog" and "NETWORK_BRANCHING:GOLD_WEB:" in str(event.get("value"))
        for event in telemetry
    )


def test_kiterunner_opsec_enforced_without_sovereign_layer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent = KiterunnerAgent(memory_root=tmp_path / "memory2")
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/kr")
    monkeypatch.setattr(
        agent,
        "_runtime_environment",
        {
            "vpn_interfaces": ("tun0",),
            "vpn_up_interfaces": [],
            "proxychains_enabled": False,
        },
    )
    result = agent.execute("https://api.example.com", {})
    assert result.status == "failure"
    assert "Sovereign Network Layer not detected" in result.target_context.get("stderr", "")


def test_kiterunner_registry_yaml_has_endpoint_enumeration_category() -> None:
    registry_path = Path("tools/registry/tool_registry.yaml")
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    tools = payload.get("tools", []) if isinstance(payload, dict) else []
    entry = next((item for item in tools if item.get("name") == "kiterunner"), None)
    assert entry is not None
    assert entry.get("agent_class") == "KiterunnerAgent"
    assert entry.get("service_category") == "ENDPOINT_ENUMERATION"
    assert "ENDPOINT_ENUMERATION" in entry.get("tags", [])


@pytest.mark.asyncio
async def test_kiterunner_orchestrator_dispatch_handshake(
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
            if tool_name == "kiterunner":
                return _DummyTool()
            return None

    monkeypatch.setattr("apps.backend.src.core.tools.initialize_default_tools", lambda: None)
    monkeypatch.setattr("apps.backend.src.core.tools.get_registry", lambda: _DummyRegistry())
    fake_tool_runner_module = types.ModuleType("apps.backend.src.core.tool_runner")
    fake_tool_runner_module.tool_runner = types.SimpleNamespace(
        enqueue=lambda **kwargs: "task-kiterunner-1"
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
    dispatch = await orchestrator._dispatch_tool("kiterunner", {"target": "https://api.example.com"})
    assert dispatch["status"] == "queued"
    assert dispatch["tool"] == "kiterunner"
    assert dispatch["task_id"] == "task-kiterunner-1"
