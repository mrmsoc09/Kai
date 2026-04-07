from __future__ import annotations

import importlib.util
import json
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
        "tool": "fullhunt",
        "tool_dir": "fullhunt",
        "class_name": "FullHuntAgent",
        "sample_output": (
            '{"hosts": [{"host": "api.example.com", "ip": "1.2.3.4", '
            '"cdn": false, "cloud": {"provider": "aws"}, "ports": [80, 443]}]}'
        ),
    },
    {
        "tool": "leakix",
        "tool_dir": "leakix",
        "class_name": "LeakIXAgent",
        "sample_output": (
            '[{"host": "exposed.example.com", "leak": "elasticsearch", '
            '"port": 9200, "protocol": "http"}]'
        ),
    },
    {
        "tool": "dehashed",
        "tool_dir": "dehashed",
        "class_name": "DehashedAgent",
        "sample_output": (
            '{"entries": [{"email": "user@example.com", "database_name": "breach2024", '
            '"obtained_from": "2024-01-01", "password": null, "hashed_password": "$2a$12$..."}]}'
        ),
    },
    {
        "tool": "grayhatwarfare",
        "tool_dir": "grayhatwarfare",
        "class_name": "GrayHatWarfareAgent",
        "sample_output": (
            '{"buckets": [{"bucket": "example-backup", "provider": "aws", '
            '"fileCount": 150, "keywords": ["example", "backup"]}]}'
        ),
    },
    {
        "tool": "nvd-nist",
        "tool_dir": "nvd_nist",
        "class_name": "NvdNistAgent",
        "sample_output": (
            '{"vulnerabilities": [{"cve": {"id": "CVE-2024-1234", "descriptions": '
            '[{"lang": "en", "value": "Test vulnerability"}], "metrics": '
            '{"cvssMetricV31": [{"cvssData": {"baseScore": 9.8, "vectorString": "CVSS:3.1/AV:N"}}]}}}]}'
        ),
    },
    {
        "tool": "ipinfo",
        "tool_dir": "ipinfo",
        "class_name": "IpInfoAgent",
        "sample_output": (
            '{"ip": "1.2.3.4", "org": "AS13335 Cloudflare, Inc.", '
            '"city": "Austin", "country": "US"}'
        ),
    },
]


def _load_agent_class(tool_dir: str, class_name: str):
    agent_path = REPO_ROOT / "apps" / "backend" / "src" / "agents" / "tools" / tool_dir / "agent.py"
    module_name = f"apps.backend.src.agents.tools.{tool_dir}.agent_testload"

    spec = importlib.util.spec_from_file_location(module_name, agent_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load module from {agent_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return getattr(module, class_name)


@pytest.mark.parametrize("case", TOOL_CASES, ids=[c["tool"] for c in TOOL_CASES])
def test_wave7_agent_contracts(case: dict[str, Any], tmp_path: Path) -> None:
    cls = _load_agent_class(case["tool_dir"], case["class_name"])
    assert cls is not None
    assert issubclass(cls, BaseToolAgent)

    memory_root = tmp_path / case["tool_dir"] / "memory"
    agent = cls(memory_root=memory_root)

    assert agent._get_tool_name() == case["tool"]

    command = agent.build_command(
        "example.com",
        {
            "artifact_dir": str(tmp_path / "artifacts"),
            "output_file": str(tmp_path / "output.json"),
            "prior_phase_findings": {"software_version": "nginx 1.24.0"},
        },
    )
    assert isinstance(command, list)
    assert command
    assert all(isinstance(item, str) and item for item in command)

    parsed = agent.parse_output(case["sample_output"], "example.com")
    assert isinstance(parsed, list)
    assert parsed, f"{case['tool']} parse_output produced no findings with sample output"

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
def test_wave7_knowledge_and_memory_scaffolding(case: dict[str, Any]) -> None:
    tool_root = REPO_ROOT / "apps" / "backend" / "src" / "agents" / "tools" / case["tool_dir"]
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


def test_dehashed_never_includes_actual_password_values() -> None:
    cls = _load_agent_class("dehashed", "DehashedAgent")
    agent = cls()

    sample_output = (
        '{"entries": [{"email": "user@example.com", "password": "plaintext_password_123", '
        '"hashed_password": "hash123", "database_name": "breach"}]}'
    )
    findings = agent.parse_output(sample_output, "example.com")
    assert findings

    for finding in findings:
        combined = f"{finding.get('raw_evidence', '')} {finding.get('context', {})}"
        assert "plaintext_password_123" not in combined
        assert "hash123" not in combined


def test_nvd_nist_maps_cvss_scores_to_expected_severity() -> None:
    cls = _load_agent_class("nvd_nist", "NvdNistAgent")
    agent = cls()

    cases = [
        (9.8, "critical"),
        (9.0, "critical"),
        (8.0, "high"),
        (7.0, "high"),
        (6.2, "medium"),
        (0.3, "low"),
    ]

    for score, expected in cases:
        sample = json.dumps(
            {
                "vulnerabilities": [
                    {
                        "cve": {
                            "id": "CVE-2024-TEST",
                            "descriptions": [{"lang": "en", "value": "Test"}],
                            "metrics": {
                                "cvssMetricV31": [
                                    {
                                        "cvssData": {
                                            "baseScore": score,
                                            "vectorString": "CVSS:3.1/AV:N",
                                        }
                                    }
                                ]
                            },
                        }
                    }
                ]
            }
        )
        findings = agent.parse_output(sample, "example.com")
        assert findings
        assert findings[0]["severity"] == expected


def test_leakix_escalates_severity_when_leak_type_present() -> None:
    cls = _load_agent_class("leakix", "LeakIXAgent")
    agent = cls()

    findings = agent.parse_output(
        '[{"host": "x.example.com", "leak": "elasticsearch", "port": 9200}]',
        "example.com",
    )
    assert findings
    signal, _ = agent.filter_noise(findings)
    assert signal
    assert signal[0]["context"]["leak_type"] == "elasticsearch"
    assert signal[0]["severity"] == "high"


@pytest.mark.parametrize("case", TOOL_CASES, ids=[c["tool"] for c in TOOL_CASES])
def test_agents_handle_empty_api_responses_gracefully(case: dict[str, Any]) -> None:
    cls = _load_agent_class(case["tool_dir"], case["class_name"])
    agent = cls()

    for raw_output in ["{}", "[]", "", "null"]:
        findings = agent.parse_output(raw_output, "example.com")
        assert isinstance(findings, list)
        assert len(findings) == 0
