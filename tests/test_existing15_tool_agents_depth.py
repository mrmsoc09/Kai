from __future__ import annotations

import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from apps.backend.src.agents.tools.base_tool_agent import BaseToolAgent


REPO_ROOT = Path(__file__).resolve().parents[1]

EXISTING_15: list[dict[str, str]] = [
    {"tool": "subfinder", "class_name": "SubfinderAgent"},
    {"tool": "amass", "class_name": "AmassAgent"},
    {"tool": "dnsx", "class_name": "DnsxAgent"},
    {"tool": "gau", "class_name": "GauAgent"},
    {"tool": "waybackurls", "class_name": "WaybackurlsAgent"},
    {"tool": "httpx_probe", "class_name": "HttpxProbeAgent"},
    {"tool": "naabu", "class_name": "NaabuAgent"},
    {"tool": "nuclei_scan", "class_name": "NucleiScanAgent"},
    {"tool": "dalfox", "class_name": "DalfoxAgent"},
    {"tool": "sqlmap", "class_name": "SqlmapAgent"},
    {"tool": "ssrfmap", "class_name": "SsrfmapAgent"},
    {"tool": "corsy", "class_name": "CorsyAgent"},
    {"tool": "crlfuzz", "class_name": "CrlfuzzAgent"},
    {"tool": "jwt_tool", "class_name": "JwtToolAgent"},
    {"tool": "kiterunner", "class_name": "KiterunnerAgent"},
]


def _load_agent_class(tool: str, class_name: str):
    agent_path = REPO_ROOT / "apps" / "backend" / "src" / "agents" / "tools" / tool / "agent.py"
    module_name = f"apps.backend.src.agents.tools.{tool.replace('-', '_')}.agent_depth_test"
    spec = importlib.util.spec_from_file_location(module_name, agent_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {agent_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, class_name)


@pytest.mark.parametrize("case", EXISTING_15, ids=[c["tool"] for c in EXISTING_15])
def test_existing15_agent_contract_and_handoff(case: dict[str, str], tmp_path: Path) -> None:
    tool = case["tool"]
    cls = _load_agent_class(tool, case["class_name"])
    assert issubclass(cls, BaseToolAgent)

    agent = cls(memory_root=tmp_path / tool / "memory")

    command = agent.build_command(
        "example.com",
        {
            "artifact_dir": str(tmp_path / "artifacts"),
            "output_file": str(tmp_path / "output.txt"),
            "rate_limit": 10,
        },
    )
    assert isinstance(command, list)
    assert command

    parsed = agent.parse_output("https://example.com/?id=1\n", "example.com")
    assert isinstance(parsed, list)

    filtered = agent.filter_noise(parsed)
    assert isinstance(filtered, tuple)
    assert len(filtered) == 2
    assert isinstance(filtered[0], list)
    assert isinstance(filtered[1], list)

    if hasattr(agent, "_generate_next_agent_instructions"):
        instructions = agent._generate_next_agent_instructions(filtered[0], "example.com")
        assert isinstance(instructions, dict)

    started = datetime.now(UTC)
    result = agent.map_output(
        target="example.com",
        command=command,
        stdout="https://example.com/?id=1\n",
        stderr="",
        exit_code=0,
        started_at=started,
        ended_at=started,
        runtime_ms=0,
        mission_id="mission-depth-test",
        status="success",
        options={"artifact_dir": str(tmp_path / "artifacts")},
    )
    handoff = result.target_context.get("handoff_report")
    assert isinstance(handoff, dict)
    assert handoff.get("tool") == tool
    assert "next_agent_instructions" in handoff


@pytest.mark.parametrize("case", EXISTING_15, ids=[c["tool"] for c in EXISTING_15])
def test_existing15_knowledge_and_memory_assets(case: dict[str, str]) -> None:
    tool = case["tool"]
    tool_root = REPO_ROOT / "apps" / "backend" / "src" / "agents" / "tools" / tool
    knowledge_root = tool_root / "knowledge"
    memory_root = tool_root / "memory"

    for file_name in [
        "tool_overview.md",
        "advanced_techniques.md",
        "output_patterns.md",
        "false_positives.md",
        "use_cases.md",
    ]:
        path = knowledge_root / file_name
        assert path.exists(), f"missing knowledge file: {path}"
        assert len(path.read_text(encoding="utf-8")) > 100

    for file_name in ["scan_history.jsonl", "findings_correlation.jsonl"]:
        path = memory_root / file_name
        assert path.exists(), f"missing memory file: {path}"
