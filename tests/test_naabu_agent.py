from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from apps.backend.src.agents.tools.naabu.agent import NaabuAgent
from apps.backend.src.agents.tools.naabu.schemas import NaabuRawRecord, PortRegistry


class _FakePopen:
    def __init__(self, stdout_text: str, stderr_text: str, returncode: int = 0) -> None:
        self.stdin = io.StringIO()
        self.stdout = io.StringIO(stdout_text)
        self.stderr = io.StringIO(stderr_text)
        self.returncode = returncode
        self.pid = 212121

    def wait(self, timeout: int | None = None) -> int:
        return self.returncode

    def poll(self) -> int:
        return self.returncode


def test_port_registry_mapping_contract() -> None:
    raw = NaabuRawRecord.model_validate(
        {
            "ip": "1.2.3.4",
            "host": "api.example.com",
            "port": "443",
            "protocol": "TCP",
        }
    )
    registry = PortRegistry.from_raw(
        raw,
        target_scope="example.com",
        service_hint="https",
        is_web_port=True,
    )
    assert registry.target_ip == "1.2.3.4"
    assert registry.port_number == 443
    assert registry.proto_type == "tcp"


def test_port_registry_rejects_invalid_port() -> None:
    with pytest.raises(ValidationError):
        NaabuRawRecord.model_validate({"ip": "1.2.3.4", "port": 70000})


def test_naabu_build_command_profiles() -> None:
    agent = NaabuAgent()

    cmd_bbp = agent.build_command("example.com")
    assert "-p" in cmd_bbp
    assert agent.BBP_WEB_PORTS in cmd_bbp
    assert "-rate" in cmd_bbp and "1000" in cmd_bbp

    cmd_top = agent.build_command("example.com", {"scan_profile": "top1000"})
    assert "-top-ports" in cmd_top
    assert "1000" in cmd_top

    cmd_full = agent.build_command("10.0.0.0/24", {"full_scan": True})
    assert "-p" in cmd_full
    assert "-" in cmd_full


def test_naabu_parse_output_handoff_to_httpx_probe() -> None:
    agent = NaabuAgent()
    raw = '{"ip":"1.2.3.4","port":443,"protocol":"tcp"}\n'
    findings = agent.parse_output(raw, "example.com")
    assert len(findings) == 1
    finding = findings[0]
    assert finding["context"]["port_number"] == 443
    assert finding["context"]["service_hint"] == "https"
    assert "httpx_probe" in finding["recommended_next_tools"]


def test_naabu_execute_emits_telemetry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    agent = NaabuAgent(memory_root=tmp_path / "memory")

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/naabu")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="naabu v2.3.0",
            stderr="",
        ),
    )
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: _FakePopen(
            stdout_text=(
                '{"ip":"1.2.3.4","port":80,"protocol":"tcp"}\n'
                '{"ip":"1.2.3.4","port":443,"protocol":"tcp"}\n'
                '{"ip":"5.6.7.8","port":22,"protocol":"tcp"}\n'
            ),
            stderr_text="",
            returncode=0,
        ),
    )

    result = agent.execute("example.com")
    assert result.status == "success"
    assert result.target_context.get("open_ports_discovered") == 3
    telemetry = result.target_context.get("telemetry", [])
    assert any(event.get("key") == "OPEN_PORTS_DISCOVERED" for event in telemetry)
    assert any(event.get("key") == "SCAN_VELOCITY" for event in telemetry)
    assert any(
        event.get("key") == "EventLog" and "PORT_BEACON:" in str(event.get("value"))
        for event in telemetry
    )


def test_naabu_full_scan_cooldown_blocks_repeat(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent = NaabuAgent(memory_root=tmp_path / "memory2")

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/naabu")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="naabu v2.3.0",
            stderr="",
        ),
    )
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: _FakePopen(
            stdout_text='{"ip":"10.10.0.2","port":80,"protocol":"tcp"}\n',
            stderr_text="",
            returncode=0,
        ),
    )

    first = agent.execute("10.10.0.0/24", {"full_scan": True})
    assert first.status == "success"

    second = agent.execute("10.10.0.0/24", {"full_scan": True})
    assert second.status == "cooldown"
    assert "Cooldown active" in second.target_context.get("stderr", "")


def test_naabu_sovereign_enforcement(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    agent = NaabuAgent(memory_root=tmp_path / "memory3")

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/naabu")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout="naabu v2.3.0",
            stderr="",
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


def test_naabu_registry_yaml_has_network_enumeration_category() -> None:
    registry_path = Path("tools/registry/tool_registry.yaml")
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    tools = payload.get("tools", []) if isinstance(payload, dict) else []
    entry = next((item for item in tools if item.get("name") == "naabu"), None)
    assert entry is not None
    assert entry.get("agent_class") == "NaabuAgent"
    assert entry.get("service_category") == "NETWORK_ENUMERATION"
    assert "NETWORK_ENUMERATION" in entry.get("tags", [])
