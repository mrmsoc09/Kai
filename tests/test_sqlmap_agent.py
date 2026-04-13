from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pytest
import yaml

from apps.backend.src.agents.tools.sqlmap.agent import SqlmapAgent
from apps.backend.src.agents.tools.sqlmap.schemas import DatabaseSecurityRegistry, SqlmapRawRecord


class _FakePopen:
    def __init__(self, stdout_text: str, stderr_text: str, returncode: int = 0) -> None:
        self.stdout = io.StringIO(stdout_text)
        self.stderr = io.StringIO(stderr_text)
        self.returncode = returncode
        self.pid = 919191

    def wait(self, timeout: int | None = None) -> int:
        return self.returncode

    def poll(self) -> int:
        return self.returncode


def test_sqlmap_phase_transition_command_profiles() -> None:
    agent = SqlmapAgent()

    testing = agent.build_command(
        "https://app.example.com/item?id=1",
        {
            "scan_phase": "testing",
            "proxy": "socks5://127.0.0.1:9050",
            "k1_pgp_fingerprint": "ABCD1234",
        },
    )
    assert "--level" in testing and "1" in testing
    assert "--risk" in testing and "1" in testing
    assert "--technique" in testing and "B" in testing
    assert "--schema" not in testing

    exploitation = agent.build_command(
        "https://app.example.com/item?id=1",
        {
            "scan_phase": "exploitation",
            "deep_dive": True,
            "proxy": "socks5://127.0.0.1:9050",
            "k1_pgp_fingerprint": "ABCD1234",
            "map_schema": True,
        },
    )
    assert "--level" in exploitation and "5" in exploitation
    assert "--risk" in exploitation and "3" in exploitation
    assert "--schema" in exploitation


def test_sqlmap_pgp_header_embedded() -> None:
    agent = SqlmapAgent()
    cmd = agent.build_command(
        "https://api.example.com/search?q=1",
        {
            "proxy": "http://127.0.0.1:8080",
            "k1_pgp_fingerprint": "FPR-TEST-001",
        },
    )
    assert "--headers" in cmd
    idx = cmd.index("--headers")
    assert "X-K1-PGP-Fingerprint: FPR-TEST-001" == cmd[idx + 1]


def test_sqlmap_production_deep_dive_requires_authorization(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent = SqlmapAgent(memory_root=tmp_path / "memory")
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/sqlmap")

    result = agent.execute(
        "https://prod.example.com/item?id=2",
        {
            "environment_tag": "production",
            "scan_phase": "exploitation",
            "deep_dive": True,
            "proxy": "socks5://127.0.0.1:9050",
            "production_authorized": False,
        },
    )
    assert result.status == "failure"
    assert "Production deep-dive blocked" in result.target_context.get("stderr", "")


def test_sqlmap_requires_proxy_or_tor(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent = SqlmapAgent(memory_root=tmp_path / "memory2")
    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/sqlmap")

    result = agent.execute("https://staging.example.com/item?id=2", {"scan_phase": "testing"})
    assert result.status == "failure"
    assert "requires --proxy or --tor" in result.target_context.get("stderr", "")


def test_sqlmap_parse_and_registry_mapping() -> None:
    sample = (
        "[INFO] back-end DBMS: PostgreSQL\n"
        "Parameter: id (GET)\n"
        "Payload: id=1 AND 1=1\n"
        "[CRITICAL] target URL appears to be vulnerable\n"
    )
    agent = SqlmapAgent()
    findings = agent.parse_output(sample, "https://staging.example.com/item?id=1")
    assert len(findings) >= 1
    ctx = findings[0]["context"]
    assert ctx["db_technology"].lower().startswith("postgres")
    assert ctx["injection_point"] == "get"
    assert ctx["vuln_parameter"] == "id"


def test_sqlmap_session_persistence_reuses_target_dir() -> None:
    agent = SqlmapAgent()
    d1 = agent._session_dir_for_target("https://example.com/a?id=1")
    d2 = agent._session_dir_for_target("https://example.com/a?id=1")
    d3 = agent._session_dir_for_target("https://example.com/a?id=2")
    assert d1 == d2
    assert d1 != d3


def test_sqlmap_execute_telemetry_transition(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    agent = SqlmapAgent(memory_root=tmp_path / "memory3")

    monkeypatch.setattr("shutil.which", lambda _: "/usr/bin/sqlmap")
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda *args, **kwargs: _FakePopen(
            stdout_text=(
                "[INFO] back-end DBMS: MySQL\n"
                "Parameter: user (GET)\n"
                "[CRITICAL] target URL appears to be vulnerable\n"
                "database schema retrieved\n"
            ),
            stderr_text="",
            returncode=0,
        ),
    )

    result = agent.execute(
        "https://staging.example.com/u?user=1",
        {
            "scan_phase": "testing",
            "proxy": "socks5://127.0.0.1:9050",
            "k1_pgp_fingerprint": "FPR-ABC",
        },
    )
    assert result.status == "success"
    assert result.target_context.get("db_vulns_confirmed", 0) >= 1
    assert result.target_context.get("table_schema_mapped", 0) >= 1
    telemetry = result.target_context.get("telemetry", [])
    assert any(event.get("key") == "DB_VULNS_CONFIRMED" for event in telemetry)
    assert any(event.get("key") == "TABLE_SCHEMA_MAPPED" for event in telemetry)
    assert any(
        event.get("key") == "EventLog" and "DATABASE_BREACH:FALLING_GOLD_HEX" in str(event.get("value"))
        for event in telemetry
    )


def test_sqlmap_registry_yaml_database_exploitation_category() -> None:
    registry_path = Path("tools/registry/tool_registry.yaml")
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    tools = payload.get("tools", []) if isinstance(payload, dict) else []
    entry = next((item for item in tools if item.get("name") == "sqlmap"), None)
    assert entry is not None
    assert entry.get("agent_class") == "SqlmapAgent"
    assert entry.get("service_category") == "DATABASE_EXPLOITATION"
    assert "DATABASE_EXPLOITATION" in entry.get("tags", [])
