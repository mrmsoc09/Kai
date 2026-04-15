from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml
from pydantic import ValidationError

from apps.backend.src.agents.tools.content_discovery_schemas import (
    WebDiscoveryRegistry,
    XssRegistry,
)
from apps.backend.src.agents.tools.content_mining_install import build_install_plan


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_agent_class(tool: str, class_name: str):
    agent_path = REPO_ROOT / "apps" / "backend" / "src" / "agents" / "tools" / tool / "agent.py"
    module_name = f"apps.backend.src.agents.tools.{tool.replace('-', '_')}.agent_content_wing_test"
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


def test_web_discovery_registry_validation() -> None:
    record = WebDiscoveryRegistry.model_validate(
        {
            "endpoint_url": "https://example.com/api/v1/users?id=7",
            "endpoint_path": "api/v1/users",
            "source_tool": "FFUF",
            "http_status": 200,
            "content_length": 321,
        }
    )
    assert record.endpoint_path == "/api/v1/users"
    assert record.source_tool == "ffuf"

    with pytest.raises(ValidationError):
        WebDiscoveryRegistry.model_validate(
            {
                "endpoint_url": "notaurl",
                "endpoint_path": "/api",
                "source_tool": "gau",
            }
        )


def test_xss_registry_validation() -> None:
    record = XssRegistry.model_validate(
        {
            "vulnerable_url": "https://example.com/search?q=test",
            "vulnerable_parameter": "q",
            "payload": "<svg/onload=alert(1)>",
            "vuln_type": "reflected",
            "risk_level": "high",
        }
    )
    assert record.vuln_type == "reflected_xss"

    with pytest.raises(ValidationError):
        XssRegistry.model_validate(
            {
                "vulnerable_url": "https://example.com",
                "vulnerable_parameter": "bad param",
                "payload": "x",
                "vuln_type": "reflected_xss",
                "risk_level": "high",
            }
        )


@pytest.mark.parametrize(
    ("tool", "class_name", "fixture_payload", "telemetry_metric"),
    [
        (
            "ffuf",
            "FfufAgent",
            {
                "results": [
                    {
                        "url": "https://example.com/admin",
                        "status": 403,
                        "length": 120,
                        "words": 10,
                        "lines": 2,
                        "depth": 1,
                    }
                ]
            },
            "FUZZ_STREAM",
        ),
        (
            "arjun",
            "ArjunAgent",
            {"https://example.com/api": ["id", "redirect"]},
            "PARAM_MAP",
        ),
        (
            "hakrawler",
            "HakrawlerAgent",
            "https://example.com/api/v1/users\n",
            "FUZZ_STREAM",
        ),
        (
            "gau",
            "GauAgent",
            "https://example.com/api/v1/users?id=1\n",
            "FUZZ_STREAM",
        ),
        (
            "dalfox",
            "DalfoxAgent",
            json.dumps(
                {
                    "type": "reflected",
                    "url": "https://example.com/search?q=x",
                    "param": "q",
                    "payload": "<svg/onload=alert(1)>",
                    "evidence": "<svg/onload=alert(1)>",
                }
            ),
            "XSS_CONFIRMED",
        ),
        (
            "smuggler",
            "SmugglerAgent",
            "possible te.cl desync detected\n",
            "FUZZ_STREAM",
        ),
    ],
)
def test_content_wing_execute_fixture_mode(
    tool: str,
    class_name: str,
    fixture_payload: str | dict[str, Any],
    telemetry_metric: str,
    tmp_path: Path,
) -> None:
    cls = _load_agent_class(tool, class_name)
    agent = cls(memory_root=tmp_path / tool / "memory")
    scope_policy_path = _make_scope_policy(tmp_path)

    result = agent.execute(
        "example.com",
        {
            "fixture_data": fixture_payload,
            "scope_policy_path": str(scope_policy_path),
            "snl_interface": "tun0",
            "max_requests_per_second": 7,
        },
    )

    assert result.status == "success"
    assert result.target_context.get("mode") == "stub_fixture"
    assert result.target_context.get("snl_interface") == "tun0"
    telemetry = result.target_context.get("telemetry", [])
    assert any(e.get("metric") == telemetry_metric for e in telemetry)


def test_content_wing_policy_blocks_bad_scope(tmp_path: Path) -> None:
    cls = _load_agent_class("dalfox", "DalfoxAgent")
    agent = cls(memory_root=tmp_path / "dalfox" / "memory")
    scope_policy_path = _make_scope_policy(tmp_path)

    result = agent.execute(
        "example.com",
        {
            "fixture_data": "{}",
            "scope_policy_path": str(scope_policy_path),
            "research_scope": "Unapproved Scope",
        },
    )
    assert result.status == "failure"
    assert "policy_blocked" in str(result.target_context.get("error", ""))


def test_install_plan_contains_go_python_and_wordlist_steps() -> None:
    plan = build_install_plan(venv_python=".venv/bin/python", nvme_root="/mnt/nvme/k1-wordlists")

    assert plan.go_install_commands
    assert any(cmd[-2:] == ["install", "github.com/ffuf/ffuf/v2@latest"] for cmd in plan.go_install_commands)
    assert any("hakrawler" in " ".join(cmd) for cmd in plan.go_install_commands)

    assert plan.python_install_commands
    assert any("arjun" in " ".join(cmd) for cmd in plan.python_install_commands)
    assert any("smuggler" in " ".join(cmd) for cmd in plan.python_install_commands)

    assert plan.wordlist_commands
    joined = "\n".join(" ".join(cmd) for cmd in plan.wordlist_commands)
    assert "SecLists" in joined
    assert "top-1k-discovery.txt" in joined
