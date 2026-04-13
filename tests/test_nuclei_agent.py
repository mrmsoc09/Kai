from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

from apps.backend.src.agents.tools.nuclei_scan.agent import NucleiScanAgent
from apps.backend.src.agents.tools.nuclei_scan.schemas import NucleiRawRecord, VulnerabilityRegistry


class _FakeContainer:
    def __init__(self, stdout_lines: list[str], status_code: int = 0) -> None:
        self._stdout_lines = stdout_lines
        self._status_code = status_code
        self.started = False
        self.removed = False
        self.killed = False

    def start(self) -> None:
        self.started = True

    def logs(self, stream: bool = False, follow: bool = False, stdout: bool = True, stderr: bool = False):
        if stream:
            for line in self._stdout_lines:
                yield line.encode("utf-8")
            return
        return b""

    def wait(self, timeout: int | None = None) -> dict[str, int]:
        return {"StatusCode": self._status_code}

    def remove(self, force: bool = False) -> None:
        self.removed = True

    def kill(self) -> None:
        self.killed = True


class _FakeContainersApi:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeContainer:
        self.created.append(kwargs)
        if kwargs.get("command") == ["-ut"]:
            return _FakeContainer([], status_code=0)
        return _FakeContainer(
            [
                '{"template-id":"cve-2024-0001","info":{"name":"Demo RCE","severity":"critical"},"matched-at":"https://app.example.com/login"}'
            ],
            status_code=0,
        )

    def prune(self, filters: dict[str, str] | None = None) -> dict[str, Any]:
        return {"ContainersDeleted": []}


class _FakeDockerClient:
    def __init__(self) -> None:
        self.containers = _FakeContainersApi()


def test_nuclei_mapping_contract_and_hash() -> None:
    raw = NucleiRawRecord.model_validate(
        {
            "template-id": "cve-2024-0001",
            "matched-at": "https://app.example.com/login",
            "info": {"name": "Demo RCE", "severity": "critical"},
        }
    )
    vuln_hash = NucleiScanAgent._build_vuln_hash(raw)
    registry = VulnerabilityRegistry.from_raw(raw, dedupe_hash=vuln_hash)
    assert registry.vuln_id == "cve-2024-0001"
    assert registry.vuln_name == "Demo RCE"
    assert registry.risk_level == "critical"
    assert registry.target_endpoint == "https://app.example.com/login"
    assert registry.dedupe_hash == vuln_hash


def test_nuclei_build_command_preserves_severity_guardrail() -> None:
    agent = NucleiScanAgent()
    cmd = agent.build_command("example.com", {"tech_list": ["Spring Boot"]})
    assert "nuclei" in cmd
    assert "tags/spring" in str(cmd)
    assert "-s" in cmd
    severity_idx = cmd.index("-s")
    assert cmd[severity_idx + 1] == "critical,high,medium"


def test_nuclei_execute_docker_volume_mount_custom_templates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent = NucleiScanAgent(memory_root=tmp_path / "memory")
    fake_client = _FakeDockerClient()

    monkeypatch.setattr("shutil.which", lambda binary: "/usr/bin/docker" if binary == "docker" else None)
    monkeypatch.setattr(agent, "_get_docker_client", lambda: fake_client)

    custom_templates = tmp_path / "k1-templates"
    custom_templates.mkdir(parents=True, exist_ok=True)

    result = agent.execute(
        "app.example.com",
        {
            "custom_template_dir": str(custom_templates),
            "skip_template_update": True,
            "require_sovereign_network": False,
        },
    )

    assert result.status == "success"
    assert len(fake_client.containers.created) == 1

    create_kwargs = fake_client.containers.created[0]
    volumes = create_kwargs.get("volumes", {})
    assert str(custom_templates) in volumes
    assert volumes[str(custom_templates)]["bind"] == "/root/nuclei-templates"


def test_nuclei_critical_telemetry_eventlog(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent = NucleiScanAgent(memory_root=tmp_path / "memory2")
    fake_client = _FakeDockerClient()

    monkeypatch.setattr("shutil.which", lambda binary: "/usr/bin/docker" if binary == "docker" else None)
    monkeypatch.setattr(agent, "_get_docker_client", lambda: fake_client)

    result = agent.execute("app.example.com", {"skip_template_update": True})
    telemetry = result.target_context.get("telemetry", [])

    assert any(event.get("key") == "VULNS_FOUND" for event in telemetry)
    assert any(
        event.get("key") == "EventLog"
        and "TOP10_PANEL:KINETIC_JITTER_PULSATING_RED:" in str(event.get("value"))
        for event in telemetry
    )


def test_nuclei_registry_yaml_vulnerability_assessment_category() -> None:
    registry_path = Path("tools/registry/tool_registry.yaml")
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    tools = payload.get("tools", []) if isinstance(payload, dict) else []

    entry = next((item for item in tools if item.get("name") == "nuclei_scan"), None)
    assert entry is not None
    assert entry.get("agent_class") == "NucleiScanAgent"
    assert entry.get("service_category") == "VULNERABILITY_ASSESSMENT"
    assert "VULNERABILITY_ASSESSMENT" in entry.get("tags", [])
