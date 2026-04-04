from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

from apps.backend.src.agents.tools.base_tool_agent import BaseToolAgent


REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FINDING_KEYS = {
    "type",
    "value",
    "target",
    "severity",
    "confidence",
    "source_tool",
    "raw_evidence",
    "context",
    "recommended_next_tools",
    "recommended_next_actions",
}

TOOL_CASES: list[dict[str, Any]] = [
    {"tool": "torbot", "class_name": "TorbotAgent"},
    {"tool": "onionsearch", "class_name": "OnionsearchAgent"},
    {"tool": "ahmia-client", "class_name": "AhmiaClientAgent"},
    {"tool": "trufflehog", "class_name": "TrufflehogAgent"},
    {"tool": "gitleaks", "class_name": "GitleaksAgent"},
    {"tool": "nikto", "class_name": "NiktoAgent"},
    {"tool": "testssl", "class_name": "TestsslAgent"},
    {"tool": "smuggler", "class_name": "SmugglerAgent"},
    {"tool": "searchsploit", "class_name": "SearchsploitAgent"},
    {"tool": "graphql-cop", "class_name": "GraphqlCopAgent"},
    {"tool": "clairvoyance", "class_name": "ClairvoyanceAgent"},
    {"tool": "owasp-zap", "class_name": "OwaspZapAgent"},
    {"tool": "caido", "class_name": "CaidoAgent"},
    {"tool": "faraday-community", "class_name": "FaradaycommunityAgent"},
]


def _load_agent_class(tool: str, class_name: str):
    agent_path = REPO_ROOT / "apps" / "backend" / "src" / "agents" / "tools" / tool / "agent.py"
    sanitized = tool.replace("-", "_")
    module_name = f"apps.backend.src.agents.tools.{sanitized}.agent_testload"

    spec = importlib.util.spec_from_file_location(module_name, agent_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {agent_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, class_name)


@pytest.mark.parametrize("case", TOOL_CASES, ids=[c["tool"] for c in TOOL_CASES])
def test_wave3_agent_inheritance(case: dict[str, Any], tmp_path: Path) -> None:
    tool = case["tool"]
    class_name = case["class_name"]

    cls = _load_agent_class(tool, class_name)
    assert cls is not None
    assert issubclass(cls, BaseToolAgent)

    memory_root = tmp_path / tool / "memory"
    agent = cls(memory_root=memory_root)
    assert agent.TOOL_NAME == tool


@pytest.mark.parametrize("case", TOOL_CASES, ids=[c["tool"] for c in TOOL_CASES])
def test_wave3_build_command(case: dict[str, Any], tmp_path: Path) -> None:
    tool = case["tool"]
    class_name = case["class_name"]

    cls = _load_agent_class(tool, class_name)
    memory_root = tmp_path / tool / "memory"
    agent = cls(memory_root=memory_root)

    cmd = agent.build_command("https://example.com")
    
    # Faraday returns empty list (no CLI tool)
    if tool == "faraday-community":
        assert cmd == []
    else:
        assert isinstance(cmd, list)


@pytest.mark.parametrize("case", TOOL_CASES, ids=[c["tool"] for c in TOOL_CASES])
def test_wave3_parse_output(case: dict[str, Any], tmp_path: Path) -> None:
    tool = case["tool"]
    class_name = case["class_name"]

    cls = _load_agent_class(tool, class_name)
    memory_root = tmp_path / tool / "memory"
    agent = cls(memory_root=memory_root)

    findings = agent.parse_output("", "example.com")
    assert isinstance(findings, list)


@pytest.mark.parametrize("case", TOOL_CASES, ids=[c["tool"] for c in TOOL_CASES])
def test_wave3_filter_noise(case: dict[str, Any], tmp_path: Path) -> None:
    tool = case["tool"]
    class_name = case["class_name"]

    cls = _load_agent_class(tool, class_name)
    memory_root = tmp_path / tool / "memory"
    agent = cls(memory_root=memory_root)

    signal, noise = agent.filter_noise([])
    assert isinstance(signal, list)
    assert isinstance(noise, list)


@pytest.mark.parametrize("case", TOOL_CASES, ids=[c["tool"] for c in TOOL_CASES])
def test_wave3_next_agent_instructions(case: dict[str, Any], tmp_path: Path) -> None:
    tool = case["tool"]
    class_name = case["class_name"]

    cls = _load_agent_class(tool, class_name)
    memory_root = tmp_path / tool / "memory"
    agent = cls(memory_root=memory_root)

    result = agent._generate_next_agent_instructions([], "example.com")
    assert isinstance(result, dict)
    assert "next_agents" in result


@pytest.mark.parametrize("case", TOOL_CASES, ids=[c["tool"] for c in TOOL_CASES])
def test_wave3_knowledge_files(case: dict[str, Any]) -> None:
    tool = case["tool"]
    tool_root = REPO_ROOT / "apps" / "backend" / "src" / "agents" / "tools" / tool
    knowledge_root = tool_root / "knowledge"

    knowledge_files = {
        "tool_overview.md": 100,
        "advanced_techniques.md": 200,
        "output_patterns.md": 150,
        "false_positives.md": 150,
        "use_cases.md": 200,
    }

    for file_name, min_chars in knowledge_files.items():
        path = knowledge_root / file_name
        assert path.exists(), f"missing knowledge file: {path}"
        content = path.read_text(encoding="utf-8")
        assert len(content) >= min_chars, (
            f"knowledge file too short: {path} "
            f"({len(content)} < {min_chars})"
        )


@pytest.mark.parametrize("case", TOOL_CASES, ids=[c["tool"] for c in TOOL_CASES])
def test_wave3_memory_scaffolding(case: dict[str, Any]) -> None:
    tool = case["tool"]
    tool_root = REPO_ROOT / "apps" / "backend" / "src" / "agents" / "tools" / tool
    memory_root = tool_root / "memory"

    assert memory_root.exists(), f"memory directory missing: {memory_root}"

    for file_name in ["scan_history.jsonl", "findings_correlation.jsonl"]:
        path = memory_root / file_name
        assert path.exists(), f"missing memory file: {path}"


def test_faraday_aggregate_findings_method(tmp_path: Path) -> None:
    """Faraday-community must implement aggregate_findings method."""
    tool = "faraday-community"
    class_name = "FaradaycommunityAgent"

    cls = _load_agent_class(tool, class_name)
    memory_root = tmp_path / tool / "memory"
    agent = cls(memory_root=memory_root)

    assert hasattr(agent, "aggregate_findings")
    assert callable(agent.aggregate_findings)
