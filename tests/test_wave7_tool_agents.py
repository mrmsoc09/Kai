from __future__ import annotations

from typing import Any

import pytest

from apps.backend.src.agents.tools.fullhunt.agent import FullHuntAgent
from apps.backend.src.agents.tools.leakix.agent import LeakIXAgent
from apps.backend.src.agents.tools.dehashed.agent import DehashedAgent
from apps.backend.src.agents.tools.grayhatwarfare.agent import GrayHatWarfareAgent
from apps.backend.src.agents.tools.nvd_nist.agent import NvdNistAgent
from apps.backend.src.agents.tools.ipinfo.agent import IpInfoAgent


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
        "agent_class": FullHuntAgent,
        "sample_output": '{"hosts": [{"host": "api.example.com", "ip": "1.2.3.4", "cdn": false, "cloud": {}, "ports": [80, 443]}]}',
    },
    {
        "tool": "leakix",
        "agent_class": LeakIXAgent,
        "sample_output": '[{"host": "exposed.example.com", "leak": "elasticsearch", "port": 9200, "protocol": "http"}]',
    },
    {
        "tool": "dehashed",
        "agent_class": DehashedAgent,
        "sample_output": '{"entries": [{"email": "user@example.com", "database_name": "breach2024", "obtained_from": "2024-01-01", "password": null, "hashed_password": "$2a$12$..."}]}',
    },
    {
        "tool": "grayhatwarfare",
        "agent_class": GrayHatWarfareAgent,
        "sample_output": '{"buckets": [{"bucket": "example-backup", "provider": "s3", "fileCount": 150, "keywords": ["example", "backup"]}]}',
    },
    {
        "tool": "nvd-nist",
        "agent_class": NvdNistAgent,
        "sample_output": '{"vulnerabilities": [{"cve": {"id": "CVE-2024-1234", "descriptions": [{"lang": "en", "value": "Test"}], "metrics": {"cvssMetricV31": [{"cvssData": {"baseScore": 9.8, "vectorString": "CVSS:3.1/AV:N"}}]}}}]}',
    },
    {
        "tool": "ipinfo",
        "agent_class": IpInfoAgent,
        "sample_output": '{"ip": "1.2.3.4", "org": "AS12345 Example Corp", "city": "San Francisco", "country": "US"}',
    },
]


@pytest.mark.parametrize("case", TOOL_CASES, ids=[c["tool"] for c in TOOL_CASES])
def test_agent_can_be_instantiated(case: dict[str, Any]) -> None:
    """Verify agent can be instantiated."""
    agent = case["agent_class"]()
    assert agent is not None
    assert agent.TOOL_NAME == case["tool"]


@pytest.mark.parametrize("case", TOOL_CASES, ids=[c["tool"] for c in TOOL_CASES])
def test_agent_parse_output(case: dict[str, Any]) -> None:
    """Verify agent can parse sample output."""
    agent = case["agent_class"]()

    findings = agent.parse_output(case["sample_output"], "example.com")
    assert isinstance(findings, list)

    for finding in findings:
        assert isinstance(finding, dict)
        assert REQUIRED_FINDING_KEYS <= set(finding.keys())

        assert finding["target"] == "example.com"
        assert finding["severity"] in [
            "critical",
            "high",
            "medium",
            "low",
            "info",
        ]
        assert 0 <= finding["confidence"] <= 1.0
        assert finding["source_tool"] == case["tool"]


def test_dehashed_never_includes_passwords() -> None:
    """Verify DehashedAgent never includes plaintext passwords in findings."""
    agent = DehashedAgent()

    sample_output = '{"entries": [{"email": "user@example.com", "password": "plaintext_password_123", "database_name": "breach"}]}'
    findings = agent.parse_output(sample_output, "example.com")

    for finding in findings:
        evidence = finding.get("raw_evidence", "")
        context = finding.get("context", {})

        assert "plaintext_password" not in evidence
        assert "password_123" not in evidence
        assert "plaintext_password" not in str(context)


def test_nvd_nist_cvss_to_severity_mapping() -> None:
    """Verify NVD/NIST correctly maps CVSS scores to severity."""
    agent = NvdNistAgent()

    test_cases = [
        (9.8, "critical"),
        (8.5, "high"),
        (6.5, "medium"),
        (3.5, "low"),
        (0.1, "low"),
    ]

    for cvss_score, expected_severity in test_cases:
        sample = f'{{"vulnerabilities": [{{"cve": {{"id": "CVE-2024-TEST", "descriptions": [{{"lang": "en", "value": "Test"}}], "metrics": {{"cvssMetricV31": [{{"cvssData": {{"baseScore": {cvss_score}, "vectorString": "CVSS:3.1/AV:N"}}}}]}}}}}}]}}'
        findings = agent.parse_output(sample, "example.com")

        if findings:
            assert findings[0]["severity"] == expected_severity


def test_leakix_escalates_severity_on_leak_type() -> None:
    """Verify LeakIX escalates severity when leak_type is present."""
    agent = LeakIXAgent()

    with_leak = '[{"host": "exposed.example.com", "leak": "elasticsearch", "port": 9200}]'
    without_leak = '[{"host": "normal.example.com", "port": 80}]'

    findings_with_leak = agent.parse_output(with_leak, "example.com")
    findings_without_leak = agent.parse_output(without_leak, "example.com")

    assert len(findings_with_leak) > 0
    assert findings_with_leak[0]["severity"] == "high"

    assert len(findings_without_leak) > 0
    assert findings_without_leak[0]["severity"] == "info"


@pytest.mark.parametrize("case", TOOL_CASES, ids=[c["tool"] for c in TOOL_CASES])
def test_agent_handles_empty_response(case: dict[str, Any]) -> None:
    """Verify agent handles empty API responses gracefully."""
    agent = case["agent_class"]()

    empty_outputs = ["{}", "[]", "", "null"]

    for empty_output in empty_outputs:
        findings = agent.parse_output(empty_output, "example.com")
        assert isinstance(findings, list)
        assert len(findings) == 0
