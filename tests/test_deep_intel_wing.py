from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from apps.backend.src.agents.tools.darknet_leak_schemas import DiscoveryRegistry, SecretLeakRegistry
from apps.backend.src.agents.tools.deep_intel_install import build_install_plan


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_agent_class(tool: str, class_name: str):
    agent_path = REPO_ROOT / "apps" / "backend" / "src" / "agents" / "tools" / tool / "agent.py"
    module_name = f"apps.backend.src.agents.tools.{tool.replace('-', '_')}.agent_deep_intel_test"
    spec = importlib.util.spec_from_file_location(module_name, agent_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {agent_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, class_name)


def _make_scope_policy(tmp_path: Path) -> Path:
    policy_path = tmp_path / "scope_guardrails.yaml"
    policy_path.write_text(
        yaml.safe_dump(
            {
                "allowlist": ["example.com"],
                "denylist": [],
                "cidr_allowlist": [],
                "safe_mode_default": True,
                "strict_allowlist": False,
            }
        ),
        encoding="utf-8",
    )
    return policy_path


def _metric_values(events: list[dict[str, Any]], metric: str) -> list[Any]:
    return [e.get("value") for e in events if e.get("metric") == metric]


def test_secret_leak_registry_forces_critical() -> None:
    record = SecretLeakRegistry.model_validate(
        {
            "vuln_type": "aws_key",
            "location": "src/config/.env",
            "risk_level": "low",
            "source_tool": "trufflehog",
        }
    )
    assert record.risk_level == "critical"
    assert record.masked is True


def test_discovery_registry_accepts_darknet_tag() -> None:
    record = DiscoveryRegistry.model_validate(
        {
            "discovered_domain": "abcdefghijklmnop.onion",
            "intel_source": "INTEL:DARKNET",
        }
    )
    assert record.discovered_domain.endswith(".onion")
    assert "darknet" in record.intel_source


def test_ahmia_requires_default_tor_proxy(tmp_path: Path) -> None:
    cls = _load_agent_class("ahmia-client", "AhmiaClientAgent")
    agent = cls(memory_root=tmp_path / "ahmia-client" / "memory")
    scope_policy = _make_scope_policy(tmp_path)

    blocked = agent.check_policy(
        "example.com",
        {
            "scope_policy_path": str(scope_policy),
            "tor_proxy": "127.0.0.1:9150",
        },
    )
    assert blocked["allowed"] is False
    assert str(blocked["reason"]).startswith("tor_proxy_required:")


def test_trufflehog_secret_masking_and_telemetry(tmp_path: Path) -> None:
    cls = _load_agent_class("trufflehog", "TrufflehogAgent")
    agent = cls(memory_root=tmp_path / "trufflehog" / "memory")
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    fixture_line = {
        "Result": {
            "DetectorName": "AWS",
            "SourceMetadata": {"Data": {"Filesystem": {"file": "config/.env"}}},
            "Raw": "AKIA1234567890SECRET",
        }
    }
    result = agent.execute(
        str(repo_dir),
        {
            "fixture_data": json.dumps(fixture_line),
            "snl_interface": "tun0",
        },
    )
    assert result.status == "success"
    dumped = json.dumps(result.findings[0].model_dump(mode="json"), ensure_ascii=True)
    assert "AKIA1234567890SECRET" not in dumped

    telemetry = result.target_context.get("telemetry", [])
    assert _metric_values(telemetry, "SECRETS_EXPOSED") == [1]
    assert _metric_values(telemetry, "EventLog") == ["CREDENTIAL_LEAK_ALARM_HIGH_INTENSITY_RED"]


def test_onionsearch_darknet_normalization(tmp_path: Path) -> None:
    cls = _load_agent_class("onionsearch", "OnionsearchAgent")
    agent = cls(memory_root=tmp_path / "onionsearch" / "memory")
    scope_policy = _make_scope_policy(tmp_path)
    fixture = {
        "results": [
            {
                "url": "http://abcdefghijklmnop.onion/login",
                "engine": "ahmia",
                "snippet": "leaked credentials dump",
            }
        ]
    }
    findings = agent.parse_output(json.dumps(fixture), "example.com")
    assert len(findings) == 1
    registry = findings[0]["context"]["discovery_registry"]
    assert registry["discovered_domain"] == "abcdefghijklmnop.onion"
    assert "darknet" in registry["intel_source"]
    assert findings[0]["context"]["intel_source"] == "INTEL:DARKNET"

    result = agent.execute(
        "example.com",
        {
            "scope_policy_path": str(scope_policy),
            "fixture_data": json.dumps(fixture),
            "snl_interface": "tun0",
            "tor_proxy": "127.0.0.1:9050",
        },
    )
    telemetry = result.target_context.get("telemetry", [])
    assert _metric_values(telemetry, "DARK_SITES_DISCOVERED") == [1]


def test_spiderfoot_fixture_execution_and_policy_gate(tmp_path: Path) -> None:
    cls = _load_agent_class("spiderfoot", "SpiderfootAgent")
    agent = cls(memory_root=tmp_path / "spiderfoot" / "memory")
    scope_policy = _make_scope_policy(tmp_path)
    fixture = {
        "results": [
            {"type": "SOCIAL_MEDIA", "data": "https://github.com/security-researcher", "module": "sfp_socialprofiles"},
            {"type": "DARKWEB_MENTION", "data": "http://abcdefghijklmnop.onion/forum", "module": "sfp_dns"},
        ]
    }
    result = agent.execute(
        "example.com",
        {
            "scope_policy_path": str(scope_policy),
            "fixture_data": json.dumps(fixture),
            "snl_interface": "tun0",
        },
    )
    assert result.status == "success"
    assert result.target_context.get("mode") == "stub_fixture"
    telemetry = result.target_context.get("telemetry", [])
    assert _metric_values(telemetry, "INTEL_NODES_ACTIVE") == [len(result.findings)]
    assert any(
        "identity_registry" in (f.raw_evidence.get("context", {}) if isinstance(f.raw_evidence, dict) else {})
        for f in result.findings
    )
    assert any(
        "discovery_registry" in (f.raw_evidence.get("context", {}) if isinstance(f.raw_evidence, dict) else {})
        for f in result.findings
    )


def test_spiderfoot_requires_fixture_data(tmp_path: Path) -> None:
    cls = _load_agent_class("spiderfoot", "SpiderfootAgent")
    agent = cls(memory_root=tmp_path / "spiderfoot" / "memory")
    scope_policy = _make_scope_policy(tmp_path)
    result = agent.execute(
        "example.com",
        {
            "scope_policy_path": str(scope_policy),
            "snl_interface": "tun0",
        },
    )
    assert result.status == "failure"
    assert "fixture_data is required" in str(result.target_context.get("error", ""))


def test_deep_intel_install_plan_includes_tor_bootstrap() -> None:
    plan = build_install_plan()
    assert ["sudo", "apt-get", "install", "-y", "tor"] in plan.tor_setup_commands
    assert ["systemctl", "is-active", "tor"] in plan.verification_commands
    assert any(cmd[:2] == ["trufflehog", "version"] for cmd in plan.verification_commands)
