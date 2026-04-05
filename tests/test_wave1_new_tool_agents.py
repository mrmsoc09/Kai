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
    {
        "tool": "assetfinder",
        "class_name": "AssetfinderAgent",
        "sample_output": "api.example.com\nmail.example.com\n",
    },
    {
        "tool": "findomain",
        "class_name": "FindomainAgent",
        "sample_output": "staging.example.com\nportal.example.com\n",
    },
    {
        "tool": "chaos",
        "class_name": "ChaosAgent",
        "sample_output": "admin.example.com\ninternal.example.com\n",
    },
    {
        "tool": "github-subdomains",
        "class_name": "GithubSubdomainsAgent",
        "sample_output": "dev-api.example.com\ninternal.example.com\n",
    },
    {
        "tool": "nmap",
        "class_name": "NmapAgent",
        "sample_output": "9200/tcp open  http Elasticsearch 7.10\n80/tcp open  http nginx\n",
    },
    {
        "tool": "masscan",
        "class_name": "MasscanAgent",
        "sample_output": (
            '[{"ip":"1.1.1.1","ports":[{"port":9090,"proto":"tcp"},{"port":80,"proto":"tcp"}]}]'
        ),
    },
    {
        "tool": "wafw00f",
        "class_name": "Wafw00fAgent",
        "sample_output": '{"waf_detected":true,"waf_name":"Cloudflare","confidence":0.97}',
    },
    {
        "tool": "gowitness",
        "class_name": "GoWitnessAgent",
        "sample_output": (
            '{"url":"https://example.com/admin","title":"Admin Login","status_code":200,'
            '"screenshot_path":"/tmp/shot.png"}'
        ),
    },
    {
        "tool": "eyewitness",
        "class_name": "EyewitnessAgent",
        "sample_output": "[200] https://example.com/admin title: Admin Console",
    },
    {
        "tool": "whatweb",
        "class_name": "WhatwebAgent",
        "sample_output": '{"plugins":{"Apache":{"version":["2.4.58"]},"HTML5":{}}}',
    },
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
def test_wave1_agent_contracts(case: dict[str, Any], tmp_path: Path) -> None:
    tool = case["tool"]
    class_name = case["class_name"]

    cls = _load_agent_class(tool, class_name)
    assert cls is not None
    assert issubclass(cls, BaseToolAgent)

    memory_root = tmp_path / tool / "memory"
    agent = cls(memory_root=memory_root)

    assert agent._get_tool_name() == tool

    command = agent.build_command(
        "example.com",
        {
            "artifact_dir": str(tmp_path / "artifacts"),
            "hosts_file": str(tmp_path / "hosts.txt"),
            "output_file": str(tmp_path / "output.txt"),
            "open_ports_file": str(tmp_path / "ports.txt"),
        },
    )
    assert isinstance(command, list)
    assert command
    assert all(isinstance(item, str) and item for item in command)

    parsed = agent.parse_output(case["sample_output"], "example.com")
    assert isinstance(parsed, list)
    assert parsed, f"{tool} parse_output produced no findings with sample output"

    for finding in parsed:
        assert isinstance(finding, dict)
        assert REQUIRED_FINDING_KEYS.issubset(set(finding.keys()))

    signal, noise = agent.filter_noise(parsed)
    assert isinstance(signal, list)
    assert isinstance(noise, list)

    instructions = agent._generate_next_agent_instructions(signal, "example.com")
    assert isinstance(instructions, dict)
    assert "next_agents" in instructions


@pytest.mark.parametrize("case", TOOL_CASES, ids=[c["tool"] for c in TOOL_CASES])
def test_wave1_knowledge_and_memory_scaffolding(case: dict[str, Any]) -> None:
    tool = case["tool"]
    tool_root = REPO_ROOT / "apps" / "backend" / "src" / "agents" / "tools" / tool
    knowledge_root = tool_root / "knowledge"
    memory_root = tool_root / "memory"

    knowledge_files = [
        "tool_overview.md",
        "advanced_techniques.md",
        "output_patterns.md",
        "false_positives.md",
        "use_cases.md",
    ]

    for file_name in knowledge_files:
        path = knowledge_root / file_name
        assert path.exists(), f"missing knowledge file: {path}"
        content = path.read_text(encoding="utf-8")
        assert len(content) > 100, f"knowledge file too short: {path}"

    for file_name in ["scan_history.jsonl", "findings_correlation.jsonl"]:
        path = memory_root / file_name
        assert path.exists(), f"missing memory file: {path}"
