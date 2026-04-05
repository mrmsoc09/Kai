from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]

CREW_AGENTS = [
    {"class": "OSINTIntelligenceAgent", "module": "osint_intelligence_agent"},
    {"class": "DarkWebIntelAgent", "module": "dark_web_intel_agent"},
    {"class": "SecretScannerAgent", "module": "secret_scanner_agent"},
    {"class": "ContentDiscoveryAgent", "module": "content_discovery_agent"},
    {"class": "VulnerabilityAgent", "module": "vulnerability_agent"},
    {"class": "APISecurityAgent", "module": "api_security_agent"},
    {"class": "FaradayCoordinatorAgent", "module": "faraday_coordinator_agent"},
]


def _load_crew_agent_class(module_name: str, class_name: str):
    agent_path = (
        REPO_ROOT / "apps" / "backend" / "src" / "agents"
        / "crew" / f"{module_name}.py"
    )
    spec = importlib.util.spec_from_file_location(
        f"agents.crew.{module_name}_testload", agent_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {agent_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[f"agents.crew.{module_name}_testload"] = module
    spec.loader.exec_module(module)
    return getattr(module, class_name)


@pytest.mark.parametrize("case", CREW_AGENTS, ids=[c["class"] for c in CREW_AGENTS])
def test_crew_agent_importable(case: dict[str, Any]) -> None:
    cls = _load_crew_agent_class(case["module"], case["class"])
    assert cls is not None


@pytest.mark.parametrize("case", CREW_AGENTS, ids=[c["class"] for c in CREW_AGENTS])
def test_crew_agent_interface(case: dict[str, Any]) -> None:
    cls = _load_crew_agent_class(case["module"], case["class"])
    agent = cls()

    assert hasattr(agent, "get_tool_agents")
    assert callable(agent.get_tool_agents)

    assert hasattr(agent, "get_execution_order")
    assert callable(agent.get_execution_order)

    assert hasattr(agent, "build_tool_context")
    assert callable(agent.build_tool_context)

    assert hasattr(agent, "aggregate_tool_results")
    assert callable(agent.aggregate_tool_results)

    assert hasattr(agent, "execute")
    assert callable(agent.execute)


@pytest.mark.parametrize("case", CREW_AGENTS, ids=[c["class"] for c in CREW_AGENTS])
def test_crew_agent_get_tool_agents(case: dict[str, Any]) -> None:
    cls = _load_crew_agent_class(case["module"], case["class"])
    agent = cls()

    tools = agent.get_tool_agents()
    assert isinstance(tools, list)
    assert len(tools) > 0


@pytest.mark.parametrize("case", CREW_AGENTS, ids=[c["class"] for c in CREW_AGENTS])
def test_crew_agent_get_execution_order(case: dict[str, Any]) -> None:
    cls = _load_crew_agent_class(case["module"], case["class"])
    agent = cls()

    order = agent.get_execution_order({})
    assert isinstance(order, list)
    assert all(isinstance(group, list) for group in order)


@pytest.mark.parametrize("case", CREW_AGENTS, ids=[c["class"] for c in CREW_AGENTS])
def test_crew_agent_build_tool_context(case: dict[str, Any]) -> None:
    cls = _load_crew_agent_class(case["module"], case["class"])
    agent = cls()

    ctx = agent.build_tool_context("any_tool", {}, {})
    assert isinstance(ctx, dict)
    assert "scan_id" in ctx or "target" in ctx or "mission_id" in ctx or "artifact_dir" in ctx


@pytest.mark.parametrize("case", CREW_AGENTS, ids=[c["class"] for c in CREW_AGENTS])
def test_crew_agent_aggregate_tool_results(case: dict[str, Any]) -> None:
    cls = _load_crew_agent_class(case["module"], case["class"])
    agent = cls()

    result = agent.aggregate_tool_results([], {})
    assert isinstance(result, dict)
    assert any(k.endswith("_complete") for k in result.keys())


def test_dark_web_intel_verify_tor() -> None:
    cls = _load_crew_agent_class("dark_web_intel_agent", "DarkWebIntelAgent")
    agent = cls()

    assert hasattr(agent, "verify_tor_service")
    assert callable(agent.verify_tor_service)

    result = agent.verify_tor_service()
    assert isinstance(result, bool)


def test_secret_scanner_escalation() -> None:
    cls = _load_crew_agent_class("secret_scanner_agent", "SecretScannerAgent")
    agent = cls()

    result = agent.aggregate_tool_results([], {})
    assert isinstance(result, dict)

    # With verified secrets
    tool_results = [
        {
            "parsed_findings": [
                {"confidence": 0.95, "type": "secret"}
            ]
        }
    ]
    result_with_secrets = agent.aggregate_tool_results(tool_results, {})
    assert result_with_secrets.get("escalate_immediately") is True
    assert "escalation_reason" in result_with_secrets


def test_faraday_coordinator_returns_faraday() -> None:
    cls = _load_crew_agent_class("faraday_coordinator_agent", "FaradayCoordinatorAgent")
    agent = cls()

    tools = agent.get_tool_agents()
    assert tools == ["faraday-community"]


def test_api_security_graphql_split() -> None:
    cls = _load_crew_agent_class("api_security_agent", "APISecurityAgent")
    agent = cls()

    # Without GraphQL endpoints
    order_no_graphql = agent.get_execution_order({})
    assert len(order_no_graphql) == 1

    # With GraphQL endpoints
    order_with_graphql = agent.get_execution_order({
        "graphql_endpoints": ["https://example.com/graphql"]
    })
    assert len(order_with_graphql) > 1
