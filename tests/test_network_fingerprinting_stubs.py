from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from apps.backend.src.agents.tools.network_fingerprint_schemas import (
    PortServiceRegistry,
    TargetRegistry,
    TechStackRegistry,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_agent_class(tool: str, class_name: str):
    agent_path = REPO_ROOT / "apps" / "backend" / "src" / "agents" / "tools" / tool / "agent.py"
    module_name = f"apps.backend.src.agents.tools.{tool}.agent_network_stub_test"
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
                "allowlist": ["example.com", "198.51.100.0/24"],
                "denylist": [],
                "cidr_allowlist": ["198.51.100.0/24"],
                "safe_mode_default": True,
                "strict_allowlist": False,
            }
        ),
        encoding="utf-8",
    )
    return policy_path


def test_network_registry_models_validate() -> None:
    port_record = PortServiceRegistry.model_validate(
        {
            "target_ip": "198.51.100.10",
            "port_number": 443,
            "proto_type": "TCP",
            "service_name": "https",
        }
    )
    assert port_record.proto_type == "tcp"

    target_record = TargetRegistry.model_validate(
        {
            "target": "Example.COM",
            "waf_present": True,
            "waf_name": "Cloudflare",
        }
    )
    assert target_record.target == "example.com"

    tech_record = TechStackRegistry.model_validate(
        {
            "target": "example.com",
            "technology_name": "Apache",
            "category": "Server",
            "source": "WhatWeb",
        }
    )
    assert tech_record.category == "server"
    assert tech_record.source == "whatweb"


def test_nmap_xml_fixture_parsing_and_stealth_command(tmp_path: Path) -> None:
    cls = _load_agent_class("nmap", "NmapAgent")
    agent = cls(memory_root=tmp_path / "nmap" / "memory")
    policy_path = _make_scope_policy(tmp_path)

    command = agent.build_command(
        "example.com",
        {
            "K1_STEALTH": True,
            "snl_interface": "tun0",
            "output_file": str(tmp_path / "nmap.xml"),
        },
    )
    assert "-sV" in command and "-sC" in command and "-T2" in command
    assert "-e" in command and "tun0" in command

    xml_fixture = """
    <nmaprun>
      <host>
        <address addr="198.51.100.10" addrtype="ipv4"/>
        <ports>
          <port protocol="tcp" portid="443">
            <state state="open"/>
            <service name="https" product="nginx" version="1.24.0"/>
          </port>
          <port protocol="tcp" portid="9200">
            <state state="open"/>
            <service name="http" product="Elasticsearch" version="8.11.0"/>
          </port>
          <port protocol="tcp" portid="22">
            <state state="closed"/>
          </port>
        </ports>
      </host>
    </nmaprun>
    """

    result = agent.execute(
        "example.com",
        {
            "fixture_data": xml_fixture,
            "scope_policy_path": str(policy_path),
            "snl_interface": "tun0",
        },
    )
    assert result.status == "success"
    assert result.findings
    assert any("PORT_SCAN_ARCS" in str(e.get("value")) for e in result.target_context.get("telemetry", []))


def test_masscan_discovery_buffer_and_rate_override(tmp_path: Path) -> None:
    cls = _load_agent_class("masscan", "MasscanAgent")
    agent = cls(memory_root=tmp_path / "masscan" / "memory")
    policy_path = _make_scope_policy(tmp_path)

    command = agent.build_command(
        "198.51.100.0/24",
        {
            "rate": 2500,
            "snl_interface": "tun0",
            "discovery_buffer": ["198.51.100.0/28", "198.51.100.16/28"],
            "output_file": str(tmp_path / "masscan.json"),
        },
    )
    assert "--rate" in command and "2500" in command
    assert "198.51.100.0/28" in command and "198.51.100.16/28" in command

    fixture = [
        {"ip": "198.51.100.10", "ports": [{"port": 443, "proto": "tcp"}, {"port": 8080, "proto": "tcp"}]}
    ]
    result = agent.execute(
        "198.51.100.0/24",
        {
            "fixture_data": fixture,
            "scope_policy_path": str(policy_path),
            "snl_interface": "tun0",
        },
    )
    assert result.status == "success"
    assert len(result.findings) >= 1


def test_wafw00f_sets_target_registry_flag(tmp_path: Path) -> None:
    cls = _load_agent_class("wafw00f", "Wafw00fAgent")
    agent = cls(memory_root=tmp_path / "wafw00f" / "memory")
    policy_path = _make_scope_policy(tmp_path)

    fixture = {"waf_detected": True, "waf_name": "Cloudflare", "confidence": 0.97}
    result = agent.execute(
        "example.com",
        {
            "fixture_data": fixture,
            "scope_policy_path": str(policy_path),
        },
    )
    assert result.status == "success"
    assert result.findings
    raw = result.findings[0].raw_evidence
    assert raw.get("context", {}).get("target_registry", {}).get("waf_present") is True


def test_whatweb_maps_to_techstack_registry(tmp_path: Path) -> None:
    cls = _load_agent_class("whatweb", "WhatwebAgent")
    agent = cls(memory_root=tmp_path / "whatweb" / "memory")
    policy_path = _make_scope_policy(tmp_path)

    fixture_line = '{"plugins":{"Apache":{"version":["2.4.58"]},"WordPress":{"version":["6.5.3"]}}}'
    result = agent.execute(
        "example.com",
        {
            "fixture_data": fixture_line,
            "scope_policy_path": str(policy_path),
        },
    )
    assert result.status == "success"
    assert result.findings
    contexts = [f.raw_evidence.get("context", {}) for f in result.findings]
    assert any("techstack_registry" in context for context in contexts)


@pytest.mark.parametrize(
    ("tool", "class_name", "target"),
    [
        ("nmap", "NmapAgent", "example.com"),
        ("masscan", "MasscanAgent", "198.51.100.0/24"),
    ],
)
def test_network_stubs_block_bad_snl_interface(
    tool: str,
    class_name: str,
    target: str,
    tmp_path: Path,
) -> None:
    cls = _load_agent_class(tool, class_name)
    agent = cls(memory_root=tmp_path / tool / "memory")
    policy_path = _make_scope_policy(tmp_path)

    result = agent.execute(
        target,
        {
            "fixture_data": "[]",
            "scope_policy_path": str(policy_path),
            "snl_interface": "eth0",
        },
    )
    assert result.status == "failure"
    assert "policy_blocked" in str(result.target_context.get("error", ""))
