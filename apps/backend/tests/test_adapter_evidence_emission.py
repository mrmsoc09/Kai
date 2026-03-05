from __future__ import annotations

import json
from pathlib import Path

from apps.backend.src.core.tool_adapters_osint import (
    HttpxTool,
    NaabuTool,
    FfufTool,
    ShodanHostTool,
)
from apps.backend.src.core.tool_adapters_scan import TrivyTool
from apps.backend.src.core.tools import ToolStatus


def _assert_evidence_shape(output: dict, expected_tool: str, artifacts_root: Path):
    evidence = output.get("evidence")
    assert evidence
    assert evidence["tool"] == expected_tool
    artifact = evidence["artifacts"][0]
    path = Path(artifact["artifact_path"])
    assert path.exists()
    assert artifacts_root in path.parents
    assert len(artifact["sha256"]) == 64


def test_httpx_emits_evidence(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    tool = HttpxTool()
    stdout = json.dumps({"url": "https://example.com", "status_code": 200})
    monkeypatch.setattr(tool, "_run", lambda *_: (True, stdout, ""))

    result = tool.execute(target="https://example.com", run_id="run-httpx")
    assert result.status == ToolStatus.COMPLETED
    _assert_evidence_shape(result.output, "httpx_probe", tmp_path)


def test_naabu_emits_evidence(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    tool = NaabuTool()
    monkeypatch.setattr(tool, "_run", lambda *_: (True, "example.com:443\nexample.com:80", ""))

    result = tool.execute(host="example.com", run_id="run-naabu")
    assert result.status == ToolStatus.COMPLETED
    _assert_evidence_shape(result.output, "naabu", tmp_path)


def test_ffuf_emits_evidence(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    tool = FfufTool()
    payload = json.dumps({"results": [{"url": "https://example.com/admin", "status": 200}]})
    monkeypatch.setattr(tool, "_run", lambda *_: (True, payload, ""))

    result = tool.execute(url="https://example.com/FUZZ", run_id="run-ffuf")
    assert result.status == ToolStatus.COMPLETED
    _assert_evidence_shape(result.output, "ffuf", tmp_path)


def test_trivy_emits_evidence(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    tool = TrivyTool()
    monkeypatch.setattr(tool, "_run", lambda *_: (True, '{"Results":[]}', ""))

    result = tool.execute(target=".", mode="fs", run_id="run-trivy")
    assert result.status == ToolStatus.COMPLETED
    _assert_evidence_shape(result.output, "trivy_scan", tmp_path)


def test_shodan_emits_evidence(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    monkeypatch.setenv("K1_SECRET_BACKEND", "env")
    monkeypatch.setenv("SHODAN_API_KEY", "test-key")
    monkeypatch.setattr("apps.backend.src.core.secret_manager._SECRET_MANAGER", None)

    class _Resp:
        status_code = 200
        text = ""

        def json(self):
            return {"ports": [80, 443], "vulns": {}}

    monkeypatch.setattr("apps.backend.src.core.tool_adapters_osint.httpx.get", lambda *a, **k: _Resp())
    tool = ShodanHostTool()

    result = tool.execute(ip="1.1.1.1", run_id="run-shodan")
    assert result.status == ToolStatus.COMPLETED
    _assert_evidence_shape(result.output, "shodan_host", tmp_path)
