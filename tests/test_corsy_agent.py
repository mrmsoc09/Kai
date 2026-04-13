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

from apps.backend.src.agents.tools.corsy.agent import CorsyAgent
from apps.backend.src.agents.tools.corsy.schemas import CorsyRawRecord, WebPolicyRegistry
from apps.backend.src.core.gemini_orchestrator import GeminiOrchestrator
from apps.backend.src.core.tools import ToolAutonomyTier


class _FakePopen:
    def __init__(self, stdout_text: str, stderr_text: str, returncode: int = 0) -> None:
        self.stdout = io.StringIO(stdout_text)
        self.stderr = io.StringIO(stderr_text)
        self.returncode = returncode
        self.pid = 737373

    def wait(self, timeout: int | None = None) -> int:
        return self.returncode

    def poll(self) -> int:
        return self.returncode


def test_web_policy_registry_mapping_contract() -> None:
    raw = CorsyRawRecord.model_validate(
        {
            "url": "https://api.example.com/account",
            "type": "origin_reflection",
            "severity": "high",
            "access_control_allow_origin": "https://evil.example",
            "access_control_allow_credentials": "true",
            "reflected_origin": "https://evil.example",
        }
    )
    registry = WebPolicyRegistry.from_raw(
        raw,
        allows_credentials=True,
        data_leak_potential="high",
        poc_javascript="fetch('https://api.example.com/account')",
    )
    assert registry.target_endpoint == "https://api.example.com/account"
    assert registry.misconfig_type == "origin_reflection"
    assert registry.risk_level == "high"
    assert registry.allows_credentials is True
    assert registry.data_leak_potential == "high"


def test_corsy_schema_rejects_malformed_url() -> None:
    with pytest.raises(ValidationError):
        CorsyRawRecord.model_validate(
            {
                "url": "not-a-url",
                "type": "wildcard_acao",
                "severity": "medium",
            }
        )

    with pytest.raises(ValidationError):
        WebPolicyRegistry.model_validate(
            {
                "target_endpoint": "bad://url",
                "misconfig_type": "origin_reflection",
                "risk_level": "high",
            }
        )


def test_corsy_parse_output_differentiates_sensitive_vs_public() -> None:
    agent = CorsyAgent()
    raw_output = (
        '{"url":"https://api.example.com/account","type":"origin_reflection","severity":"high",'
        '"access_control_allow_credentials":"true","access_control_allow_origin":"https://evil.example"}\n'
        '{"url":"https://public.example.com/status","type":"wildcard_acao","severity":"medium",'
        '"access_control_allow_origin":"*"}\n'
    )
    findings = agent.parse_output(raw_output, "https://api.example.com")
    assert len(findings) == 2

    signal, noise = agent.filter_noise(findings)
    assert len(signal) == 1
    assert len(noise) == 1
    assert signal[0]["severity"] == "critical"
    assert signal[0]["context"]["data_leak_potential"] == "high"
    assert "credentials: 'include'" in signal[0]["context"]["poc_javascript"]
    assert noise[0].get("noise_reason") == "public_or_low_impact_cors"


def test_corsy_build_command_respects_thread_cap(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = CorsyAgent()
    monkeypatch.setenv("K1_GLOBAL_THREAD_LIMIT", "8")
    cmd = agent.build_command(
        "https://example.com",
        {
            "threads": 32,
            "header": "Origin: https://evil.example",
            "json_output": True,
            "proxy": "socks5://127.0.0.1:9050",
        },
    )
    assert "corsy" in cmd
    assert "-t" in cmd
    assert cmd[cmd.index("-t") + 1] == "8"
    assert "--json" in cmd
    assert "-H" in cmd
    assert "--proxy" in cmd


def test_corsy_execute_emits_telemetry_and_critical_visual(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent = CorsyAgent(memory_root=tmp_path / "memory")

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/corsy")
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: _FakePopen(
            stdout_text=(
                '{"url":"https://admin.example.com/api/user","type":"origin_reflection",'
                '"severity":"critical","access_control_allow_credentials":"true"}\n'
            ),
            stderr_text="",
            returncode=0,
        ),
    )

    result = agent.execute(
        "https://admin.example.com",
        {"proxy": "socks5://127.0.0.1:9050"},
    )

    assert result.status == "success"
    assert result.target_context.get("cors_misconfigs_total") == 1
    assert result.target_context.get("data_leak_potential", {}).get("high", 0) >= 1
    telemetry = result.target_context.get("telemetry", [])
    assert any(event.get("key") == "CORS_MISCONFIGS_TOTAL" for event in telemetry)
    assert any(event.get("key") == "DATA_LEAK_POTENTIAL" for event in telemetry)
    assert any(event.get("key") == "DATA_LEAK_POTENTIAL_LEVEL" for event in telemetry)
    assert any(
        event.get("key") == "EventLog"
        and "DATA_LEAKAGE:PURPLE_RING_EXPAND:" in str(event.get("value"))
        for event in telemetry
    )


def test_corsy_opsec_blocks_when_sovereign_network_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent = CorsyAgent(memory_root=tmp_path / "memory2")
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/corsy")
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


def test_corsy_registry_yaml_has_access_control_audit_category() -> None:
    registry_path = Path("tools/registry/tool_registry.yaml")
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    tools = payload.get("tools", []) if isinstance(payload, dict) else []
    entry = next((item for item in tools if item.get("name") == "corsy"), None)
    assert entry is not None
    assert entry.get("agent_class") == "CorsyAgent"
    assert entry.get("service_category") == "ACCESS_CONTROL_AUDIT"
    assert "ACCESS_CONTROL_AUDIT" in entry.get("tags", [])


@pytest.mark.asyncio
async def test_corsy_orchestrator_dispatch_handshake(
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
            if tool_name == "corsy":
                return _DummyTool()
            return None

    monkeypatch.setattr("apps.backend.src.core.tools.initialize_default_tools", lambda: None)
    monkeypatch.setattr("apps.backend.src.core.tools.get_registry", lambda: _DummyRegistry())
    fake_tool_runner_module = types.ModuleType("apps.backend.src.core.tool_runner")
    fake_tool_runner_module.tool_runner = types.SimpleNamespace(
        enqueue=lambda **kwargs: "task-corsy-1"
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
    dispatch = await orchestrator._dispatch_tool("corsy", {"target": "https://api.example.com"})
    assert dispatch["status"] == "queued"
    assert dispatch["tool"] == "corsy"
    assert dispatch["task_id"] == "task-corsy-1"
