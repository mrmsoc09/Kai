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
        "tool": "feroxbuster",
        "class_name": "FeroxbusterAgent",
        "sample_output": '{"url":"https://example.com/admin","status":200,"content_length":321}\n',
    },
    {
        "tool": "katana",
        "class_name": "KatanaAgent",
        "sample_output": '{"endpoint":"https://example.com/graphql","source":"js","tag":"api"}\n',
    },
    {
        "tool": "paramspider",
        "class_name": "ParamspiderAgent",
        "sample_output": 'https://example.com/api/users?id=7&redirect=/home\n',
    },
    {
        "tool": "arjun",
        "class_name": "ArjunAgent",
        "sample_output": '{"https://example.com/api":["id","q"]}',
    },
    {
        "tool": "hakrawler",
        "class_name": "HakrawlerAgent",
        "sample_output": 'https://example.com/api/v1/users\n',
    },
    {
        "tool": "ffuf",
        "class_name": "FfufAgent",
        "sample_output": '{"results":[{"url":"https://example.com/admin","status":403,"length":444,"words":20,"lines":7}]}',
    },
    {
        "tool": "gf",
        "class_name": "GfAgent",
        "sample_output": 'sqli\thttps://example.com/item?id=1\n',
    },
    {
        "tool": "spiderfoot",
        "class_name": "SpiderfootAgent",
        "sample_output": '[{"type":"CREDENTIAL_COMPROMISED","data":"alice@example.com","module":"sfp_pwned"}]',
    },
    {
        "tool": "sherlock",
        "class_name": "SherlockAgent",
        "sample_output": '[+] GitHub: https://github.com/exampleuser\n',
    },
    {
        "tool": "phoneinfoga",
        "class_name": "PhoneinfogaAgent",
        "sample_output": '{"number":"+15551234567","country":"US","carrier":"TestCarrier","linked_accounts":[{"username":"alice"}]}',
    },
    {
        "tool": "social-analyzer",
        "class_name": "SocialAnalyzerAgent",
        "sample_output": '{"profiles":[{"platform":"github","url":"https://github.com/exampleuser","followers":10,"bio":"security","links":["https://example.com"]}]}',
    },
    {
        "tool": "reconftw",
        "class_name": "ReconftfwAgent",
        "sample_output": 'found api.example.com in passive sources\nsummary total found 10\n',
    },
]


def _load_agent_class(tool: str, class_name: str):
    agent_path = REPO_ROOT / "apps" / "backend" / "src" / "agents" / "tools" / tool / "agent.py"
    sanitized = tool.replace("-", "_")
    module_name = f"apps.backend.src.agents.tools.{sanitized}.agent_testload_wave2"

    spec = importlib.util.spec_from_file_location(module_name, agent_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {agent_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, class_name)


@pytest.mark.parametrize("case", TOOL_CASES, ids=[c["tool"] for c in TOOL_CASES])
def test_wave2_agent_contracts(case: dict[str, Any], tmp_path: Path) -> None:
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
            "output_file": str(tmp_path / "output.json"),
            "open_ports_file": str(tmp_path / "ports.txt"),
            "rate_limit": 10,
            "waf_detected": False,
            "username": "exampleuser",
            "phone_number": "+15551234567",
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
def test_wave2_knowledge_and_memory_scaffolding(case: dict[str, Any]) -> None:
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
