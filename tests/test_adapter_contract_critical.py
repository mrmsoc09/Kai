from __future__ import annotations

import hashlib
import json
from pathlib import Path

from apps.backend.src.core.tool_adapters_osint import (
    CensysHostTool,
    DnsxTool,
    FfufTool,
    GauTool,
    HttpxTool,
    NaabuTool,
    ShodanHostTool,
)
from apps.backend.src.core.tool_adapters_scan import TrivyTool
from apps.backend.src.core.tools import ToolStatus


FIXTURES = Path(__file__).resolve().parent / "fixtures" / "adapters"


def _fixture(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def _assert_evidence_integrity(evidence: dict) -> None:
    assert evidence["evidence_id"]
    assert evidence["tool"]
    assert evidence["target"]
    assert evidence["structured_data"] is not None
    assert evidence["scope_status"] == "validated"
    assert evidence["artifacts"]
    artifact = evidence["artifacts"][0]
    artifact_path = Path(artifact["artifact_path"])
    assert artifact_path.exists()
    digest = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
    assert artifact["sha256"] == digest


def test_dnsx_contract_fixture(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path / "artifacts"))
    tool = DnsxTool()
    monkeypatch.setattr(tool, "_run", lambda spec: (True, _fixture("dnsx_stdout.jsonl"), ""))
    result = tool.execute(target="api.example.com", record_type="a", run_id="run-1")
    assert result.status == ToolStatus.COMPLETED
    _assert_evidence_integrity(result.output["evidence"])


def test_httpx_contract_fixture(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path / "artifacts"))
    tool = HttpxTool()
    monkeypatch.setattr(tool, "_run", lambda spec: (True, _fixture("httpx_stdout.jsonl"), ""))
    result = tool.execute(target="https://api.example.com", run_id="run-2")
    assert result.status == ToolStatus.COMPLETED
    _assert_evidence_integrity(result.output["evidence"])


def test_naabu_contract_fixture(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path / "artifacts"))
    tool = NaabuTool()
    monkeypatch.setattr(tool, "_run", lambda spec: (True, _fixture("naabu_stdout.txt"), ""))
    result = tool.execute(host="api.example.com", ports="80,443", run_id="run-3")
    assert result.status == ToolStatus.COMPLETED
    _assert_evidence_integrity(result.output["evidence"])


def test_gau_contract_fixture(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path / "artifacts"))
    tool = GauTool()
    monkeypatch.setattr(tool, "_run", lambda spec: (True, _fixture("gau_stdout.txt"), ""))
    result = tool.execute(domain="example.com", run_id="run-4")
    assert result.status == ToolStatus.COMPLETED
    _assert_evidence_integrity(result.output["evidence"])


def test_ffuf_contract_fixture(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path / "artifacts"))
    tool = FfufTool()
    monkeypatch.setattr(tool, "_run", lambda spec: (True, _fixture("ffuf_stdout.json"), ""))
    result = tool.execute(url="https://example.com/FUZZ", run_id="run-5")
    assert result.status == ToolStatus.COMPLETED
    _assert_evidence_integrity(result.output["evidence"])


def test_trivy_contract_fixture(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path / "artifacts"))
    tool = TrivyTool()
    monkeypatch.setattr(tool, "_run", lambda spec: (True, _fixture("trivy_stdout.txt"), ""))
    result = tool.execute(target="/tmp/project", mode="fs", severity="HIGH,CRITICAL", run_id="run-6")
    assert result.status == ToolStatus.COMPLETED
    _assert_evidence_integrity(result.output["evidence"])


class _FakeSecretManager:
    def get_required(self, key: str) -> str:
        return f"fake-{key.lower()}"


class _FakeResponse:
    def __init__(self, body: dict):
        self.status_code = 200
        self._body = body
        self.text = json.dumps(body)

    def json(self) -> dict:
        return self._body


def test_shodan_contract_fixture(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path / "artifacts"))
    from apps.backend.src.core import tool_adapters_osint as mod

    monkeypatch.setattr(mod, "get_secret_manager", lambda: _FakeSecretManager())
    body = json.loads(_fixture("shodan_response.json"))
    monkeypatch.setattr(mod.httpx, "get", lambda *args, **kwargs: _FakeResponse(body))

    tool = ShodanHostTool()
    result = tool.execute(ip="1.2.3.4", run_id="run-7")
    assert result.status == ToolStatus.COMPLETED
    _assert_evidence_integrity(result.output["evidence"])


def test_censys_contract_fixture(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path / "artifacts"))
    from apps.backend.src.core import tool_adapters_osint as mod

    monkeypatch.setattr(mod, "get_secret_manager", lambda: _FakeSecretManager())
    body = json.loads(_fixture("censys_response.json"))
    monkeypatch.setattr(mod.httpx, "get", lambda *args, **kwargs: _FakeResponse(body))

    tool = CensysHostTool()
    result = tool.execute(ip="1.2.3.4", run_id="run-8")
    assert result.status == ToolStatus.COMPLETED
    _assert_evidence_integrity(result.output["evidence"])
