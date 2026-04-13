from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from apps.backend.src.agents.tools.content_discovery_schemas import CrawlRegistry, ParameterRegistry


REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_agent_class(tool: str, class_name: str):
    agent_path = REPO_ROOT / "apps" / "backend" / "src" / "agents" / "tools" / tool / "agent.py"
    module_name = f"apps.backend.src.agents.tools.{tool}.agent_content_stub_test"
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


def test_content_registry_validation() -> None:
    crawl = CrawlRegistry.model_validate(
        {
            "crawl_url": "https://example.com/static/app.js",
            "discovered_from": "Katana",
            "depth": 2,
            "asset_type": "JS Asset",
            "is_javascript": True,
        }
    )
    assert crawl.discovered_from == "katana"
    assert crawl.asset_type == "js_asset"

    param = ParameterRegistry.model_validate(
        {
            "endpoint_url": "https://example.com/api/users?id=1",
            "parameter_name": "id",
            "source": "ParamSpider",
        }
    )
    assert param.source == "paramspider"

    with pytest.raises(ValidationError):
        ParameterRegistry.model_validate(
            {
                "endpoint_url": "https://example.com/api/users",
                "parameter_name": "bad parameter",
            }
        )


def test_katana_headless_command_and_parse(tmp_path: Path) -> None:
    cls = _load_agent_class("katana", "KatanaAgent")
    agent = cls(memory_root=tmp_path / "katana" / "memory")

    cmd = agent.build_command("https://example.com", {"headless": True})
    assert "-headless" in cmd

    sample = '{"endpoint":"https://example.com/graphql","source":"js","tag":"api","depth":2}\n'
    parsed = agent.parse_output(sample, "example.com")
    assert parsed
    assert parsed[0]["context"].get("crawl_registry")


def test_paramspider_handoff_targets(tmp_path: Path) -> None:
    cls = _load_agent_class("paramspider", "ParamspiderAgent")
    agent = cls(memory_root=tmp_path / "paramspider" / "memory")

    sample = "https://example.com/api/users?id=7&redirect=/home\n"
    parsed = agent.parse_output(sample, "example.com")
    assert parsed

    instructions = agent._generate_next_agent_instructions(parsed, "example.com")
    next_agents = instructions.get("next_agents", [])
    assert "dalfox" in next_agents
    assert "sqlmap" in next_agents


def test_ferox_async_parallel_stub_execution(tmp_path: Path) -> None:
    cls = _load_agent_class("feroxbuster", "FeroxbusterAgent")
    agent = cls(memory_root=tmp_path / "ferox" / "memory")
    policy_path = _make_scope_policy(tmp_path)

    shard_a = '{"url":"https://example.com/admin","status":200,"content_length":123,"depth":1}'
    shard_b = '{"url":"https://example.com/api/v1/users","status":403,"content_length":456,"depth":2}'

    result = asyncio.run(
        agent.execute_async(
            "example.com",
            {
                "fixture_shards": [shard_a, shard_b],
                "scope_policy_path": str(policy_path),
                "tech_hint": "api",
            },
        )
    )
    assert result.status == "success"
    assert result.findings
    telemetry = result.target_context.get("telemetry", [])
    assert any(e.get("metric") == "CRAWL_DEPTH" for e in telemetry)
    assert any(e.get("metric") == "EventLog" and e.get("value") == "SPIDER_WEB_EXPANSION" for e in telemetry)


def test_ffuf_async_parallel_stub_execution(tmp_path: Path) -> None:
    cls = _load_agent_class("ffuf", "FfufAgent")
    agent = cls(memory_root=tmp_path / "ffuf" / "memory")
    policy_path = _make_scope_policy(tmp_path)

    shard_a = {"results": [{"url": "https://example.com/admin", "status": 200, "length": 321, "words": 12, "lines": 2, "depth": 1}]}
    shard_b = {"results": [{"url": "https://example.com/api", "status": 403, "length": 111, "words": 5, "lines": 1, "depth": 2}]}

    result = asyncio.run(
        agent.execute_async(
            "example.com",
            {
                "fixture_shards": [json.dumps(shard_a), json.dumps(shard_b)],
                "scope_policy_path": str(policy_path),
                "tech_hint": "php",
            },
        )
    )
    assert result.status == "success"
    assert result.findings
    telemetry = result.target_context.get("telemetry", [])
    assert any(e.get("metric") == "CRAWL_DEPTH" for e in telemetry)
