from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from apps.backend.src.agents.tools.darknet_leak_schemas import DiscoveryRegistry, VulnerabilityRegistry


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_agent_class(tool: str, class_name: str):
    agent_path = REPO_ROOT / "apps" / "backend" / "src" / "agents" / "tools" / tool / "agent.py"
    module_name = f"apps.backend.src.agents.tools.{tool.replace('-', '_')}.agent_darknet_stub_test"
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


def test_discovery_registry_requires_onion_domain() -> None:
    record = DiscoveryRegistry.model_validate(
        {
            "discovered_domain": "HTTP://EXAMPLEONIONADDRESS1234.onion/path",
            "intel_source": "TOR",
        }
    )
    assert record.discovered_domain.endswith(".onion")
    assert record.intel_source == "tor"

    with pytest.raises(ValidationError):
        DiscoveryRegistry.model_validate(
            {
                "discovered_domain": "example.com",
                "intel_source": "tor",
            }
        )


def test_vulnerability_registry_forces_critical() -> None:
    record = VulnerabilityRegistry.model_validate(
        {
            "vuln_type": "api key",
            "location": "src/.env",
            "risk_level": "low",
            "source_tool": "gitleaks",
        }
    )
    assert record.risk_level == "critical"
    assert record.masked is True


def test_torbot_policy_requires_tor_proxy(tmp_path: Path) -> None:
    cls = _load_agent_class("torbot", "TorbotAgent")
    agent = cls(memory_root=tmp_path / "torbot" / "memory")
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


def test_onionsearch_aggregates_multi_engine_results(tmp_path: Path) -> None:
    cls = _load_agent_class("onionsearch", "OnionsearchAgent")
    agent = cls(memory_root=tmp_path / "onionsearch" / "memory")

    fixture = {
        "results": [
            {
                "url": "http://abcdefghijklmnop.onion/login",
                "engine": "ahmia",
                "snippet": "leaked credentials dump",
            },
            {
                "url": "http://abcdefghijklmnop.onion/login",
                "engine": "darksearch",
                "snippet": "credential reuse",
            },
        ]
    }
    findings = agent.parse_output(json.dumps(fixture), "example.com")

    assert len(findings) == 1
    context = findings[0]["context"]
    assert sorted(context["source_engines"]) == ["ahmia", "darksearch"]
    assert findings[0]["severity"] == "high"


def test_trufflehog_cli_variants_and_masking(tmp_path: Path) -> None:
    cls = _load_agent_class("trufflehog", "TrufflehogAgent")
    agent = cls(memory_root=tmp_path / "trufflehog" / "memory")

    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()

    cmd_v3 = agent.build_command(str(repo_dir), {"cli_variant": "v3"})
    cmd_v2 = agent.build_command("https://github.com/example/repo", {"cli_variant": "v2"})

    assert cmd_v3[:2] == ["trufflehog", "filesystem"]
    assert cmd_v2[:2] == ["trufflehog", "--json"]

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
    assert len(result.findings) == 1
    dumped = json.dumps(result.findings[0].model_dump(mode="json"), ensure_ascii=True)
    assert "AKIA1234567890SECRET" not in dumped


def test_gitleaks_filters_fixture_paths_and_masks(tmp_path: Path) -> None:
    cls = _load_agent_class("gitleaks", "GitleaksAgent")
    agent = cls(memory_root=tmp_path / "gitleaks" / "memory")

    fixture = [
        {"RuleID": "aws", "File": "tests/fixture.env"},
        {"RuleID": "github_pat", "File": "src/config/.env"},
    ]

    findings = agent.parse_output(json.dumps(fixture), "example.com")
    assert len(findings) == 1
    evidence = json.loads(findings[0]["raw_evidence"])
    assert evidence["location"] == "src/config/.env"
    assert "secret" not in json.dumps(evidence).lower()


def test_dark_tools_present_in_registries() -> None:
    tools_registry = (REPO_ROOT / "tools" / "registry" / "tool_registry.yaml").read_text(encoding="utf-8")
    config_registry = (REPO_ROOT / "config" / "registry" / "tool_registry.yaml").read_text(encoding="utf-8")

    for token in ["torbot", "onionsearch", "ahmia-client", "trufflehog", "gitleaks"]:
        assert token in tools_registry
        assert token in config_registry
