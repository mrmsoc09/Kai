from __future__ import annotations

import subprocess

import pytest

from apps.backend.src.core.tool_adapters_bugbounty import (
    CatalogBackedCLITool,
    CommandResult,
    IntegrationHookTool,
    InternalCorrelationTool,
    PriorityRankingTool,
    register_bugbounty_tools,
)
from apps.backend.src.core.tool_registry_catalog import get_catalog_entry
from apps.backend.src.core.tools import ToolStatus, get_registry


def test_catalog_backed_tool_executes_with_mocked_command(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path / "artifacts"))
    entry = get_catalog_entry("assetfinder")
    assert entry is not None
    tool = CatalogBackedCLITool(entry)
    monkeypatch.setattr(tool, "_which", lambda: "/usr/bin/assetfinder")
    mocked = CommandResult(
        success=True,
        stdout="a.example.com\nb.example.com\n",
        stderr="",
        exit_code=0,
        command=["/usr/bin/assetfinder", "example.com"],
        duration_ms=12.0,
    )
    monkeypatch.setattr(tool, "_run_with_retry", lambda *args, **kwargs: (mocked, 1))

    result = tool.execute(target="example.com", run_id="run-test")
    assert result.status == ToolStatus.COMPLETED
    assert result.output["parsed"]["items"] == ["a.example.com", "b.example.com"]
    assert result.output["evidence"]["tool"] == tool.id


def test_missing_binary_returns_failed_status(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path / "artifacts"))
    entry = get_catalog_entry("assetfinder")
    assert entry is not None
    tool = CatalogBackedCLITool(entry)
    monkeypatch.setattr(tool, "_which", lambda: None)

    result = tool.execute(target="example.com")
    assert result.status == ToolStatus.FAILED
    assert "not found in PATH" in (result.error or "")


def test_tool_timeout_returns_failed_status(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path / "artifacts"))
    entry = get_catalog_entry("assetfinder")
    assert entry is not None
    tool = CatalogBackedCLITool(entry)
    monkeypatch.setattr(tool, "_which", lambda: "/usr/bin/assetfinder")
    timeout_result = CommandResult(
        success=False,
        stdout="",
        stderr="command timed out after 180s",
        exit_code=124,
        command=["/usr/bin/assetfinder", "example.com"],
        duration_ms=180010.0,
    )
    monkeypatch.setattr(tool, "_run_with_retry", lambda *args, **kwargs: (timeout_result, 1))

    result = tool.execute(target="example.com")
    assert result.status == ToolStatus.FAILED
    assert "timed out" in (result.error or "")


def test_malformed_jsonl_output_is_skipped(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path / "artifacts"))
    entry = get_catalog_entry("tlsx")
    assert entry is not None
    tool = CatalogBackedCLITool(entry)
    monkeypatch.setattr(tool, "_which", lambda: "/usr/bin/tlsx")
    malformed_output = '{"host":"a.example.com"}\nnot json\n{"host":"b.example.com"}\n'
    mocked = CommandResult(
        success=True,
        stdout=malformed_output,
        stderr="",
        exit_code=0,
        command=["/usr/bin/tlsx", "example.com"],
        duration_ms=50.0,
    )
    monkeypatch.setattr(tool, "_run_with_retry", lambda *args, **kwargs: (mocked, 1))

    result = tool.execute(target="example.com")
    assert result.status == ToolStatus.COMPLETED
    items = result.output["parsed"]["items"]
    # malformed line should be skipped, only 2 valid objects
    assert len(items) == 2
    assert all(isinstance(item, dict) for item in items)


def test_empty_stdout_produces_empty_items(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path / "artifacts"))
    entry = get_catalog_entry("assetfinder")
    assert entry is not None
    tool = CatalogBackedCLITool(entry)
    monkeypatch.setattr(tool, "_which", lambda: "/usr/bin/assetfinder")
    mocked = CommandResult(
        success=True,
        stdout="",
        stderr="",
        exit_code=0,
        command=["/usr/bin/assetfinder", "example.com"],
        duration_ms=5.0,
    )
    monkeypatch.setattr(tool, "_run_with_retry", lambda *args, **kwargs: (mocked, 1))

    result = tool.execute(target="example.com")
    assert result.status == ToolStatus.COMPLETED
    assert result.output["parsed"] == {"items": []}


def test_nmap_malformed_xml_falls_back_gracefully(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path / "artifacts"))
    entry = get_catalog_entry("nmap")
    assert entry is not None
    tool = CatalogBackedCLITool(entry)
    monkeypatch.setattr(tool, "_which", lambda: "/usr/bin/nmap")
    bad_xml = "<not valid xml <<>>>"
    mocked = CommandResult(
        success=True,
        stdout=bad_xml,
        stderr="",
        exit_code=0,
        command=["/usr/bin/nmap", "example.com"],
        duration_ms=100.0,
    )
    monkeypatch.setattr(tool, "_run_with_retry", lambda *args, **kwargs: (mocked, 1))

    result = tool.execute(target="example.com")
    assert result.status == ToolStatus.COMPLETED
    # Fallback: raw_xml key
    assert "raw_xml" in result.output["parsed"]


def test_nmap_valid_xml_is_parsed(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path / "artifacts"))
    entry = get_catalog_entry("nmap")
    assert entry is not None
    tool = CatalogBackedCLITool(entry)
    monkeypatch.setattr(tool, "_which", lambda: "/usr/bin/nmap")
    valid_xml = (
        '<?xml version="1.0"?>'
        '<nmaprun><host><address addr="192.168.1.1" addrtype="ipv4"/>'
        "<ports><port protocol=\"tcp\" portid=\"80\"><state state=\"open\"/>"
        '<service name="http"/></port></ports></host></nmaprun>'
    )
    mocked = CommandResult(
        success=True,
        stdout=valid_xml,
        stderr="",
        exit_code=0,
        command=["/usr/bin/nmap", "192.168.1.1"],
        duration_ms=200.0,
    )
    monkeypatch.setattr(tool, "_run_with_retry", lambda *args, **kwargs: (mocked, 1))

    result = tool.execute(target="192.168.1.1")
    assert result.status == ToolStatus.COMPLETED
    hosts = result.output["parsed"]["hosts"]
    assert len(hosts) == 1
    assert hosts[0]["address"] == "192.168.1.1"
    assert hosts[0]["ports"][0]["port"] == "80"


def test_internal_correlation_and_ranking_tools():
    correlation = InternalCorrelationTool().execute(
        target="api.example.com",
        inputs=[
            {"host": "api.example.com", "port": 443, "url": "https://api.example.com/v1/users?id=1"},
            {"host": "api.example.com", "port": 443, "service": "https"},
        ],
    )
    assert correlation.status == ToolStatus.COMPLETED
    assert "api.example.com" in correlation.output["correlation"]["hosts"]

    ranking = PriorityRankingTool().execute(
        target="api.example.com",
        signals=[{"host": "api.example.com", "port": 443}],
    )
    assert ranking.status == ToolStatus.COMPLETED
    assert ranking.output["priority_score"] >= 20


def test_correlation_tool_with_empty_inputs():
    result = InternalCorrelationTool().execute(target="example.com", inputs=[])
    assert result.status == ToolStatus.COMPLETED
    assert "example.com" in result.output["correlation"]["hosts"]


def test_correlation_tool_deduplicates_signals():
    duplicate = {"host": "api.example.com", "port": 443, "service": "https"}
    result = InternalCorrelationTool().execute(
        target="api.example.com",
        inputs=[duplicate, duplicate, duplicate],
    )
    assert result.status == ToolStatus.COMPLETED
    assert result.output["duplicates_suppressed"] is True


def test_ranking_tool_bucket_assignment():
    # No signals → low bucket
    r_low = PriorityRankingTool().execute(target="example.com", signals=[])
    assert r_low.output["priority_bucket"] == "low"

    # Many signals with ports → high bucket
    signals = [{"host": "x.example.com", "port": p, "severity": "high"} for p in range(20)]
    r_high = PriorityRankingTool().execute(target="x.example.com", signals=signals)
    assert r_high.output["priority_bucket"] in ("medium", "high")


def test_register_bugbounty_tools_is_idempotent():
    before = get_registry().count()
    register_bugbounty_tools()
    middle = get_registry().count()
    register_bugbounty_tools()
    after = get_registry().count()
    assert middle >= before
    assert after == middle


def test_integration_hook_postman_reads_collection(monkeypatch, tmp_path):
    artifacts_root = tmp_path / "artifacts"
    artifacts_root.mkdir()
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(artifacts_root))
    collection = artifacts_root / "postman.json"
    collection.write_text('{"info":{"name":"demo"},"item":[]}', encoding="utf-8")
    entry = get_catalog_entry("postman_collection_export")
    assert entry is not None
    tool = IntegrationHookTool(entry)
    result = tool.execute(target=str(collection), run_id="r1")
    assert result.status == ToolStatus.COMPLETED
    summary = result.output.get("collection_summary")
    assert isinstance(summary, dict)
    assert summary["source_path"] == str(collection.resolve())


def test_integration_hook_path_outside_artifacts_root_is_rejected(monkeypatch, tmp_path):
    artifacts_root = tmp_path / "artifacts"
    artifacts_root.mkdir()
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(artifacts_root))
    # File outside artifacts root — should be denied
    outside = tmp_path / "sensitive.json"
    outside.write_text('{"secret": "value"}', encoding="utf-8")
    entry = get_catalog_entry("postman_collection_export")
    assert entry is not None
    tool = IntegrationHookTool(entry)
    result = tool.execute(target=str(outside), run_id="r-path-traversal")
    assert result.status == ToolStatus.COMPLETED
    # Must not read files outside artifacts root
    assert result.output.get("collection_summary") is None


def test_integration_hook_missing_collection_file_does_not_crash(monkeypatch, tmp_path):
    artifacts_root = tmp_path / "artifacts"
    artifacts_root.mkdir()
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(artifacts_root))
    entry = get_catalog_entry("postman_collection_export")
    assert entry is not None
    tool = IntegrationHookTool(entry)
    result = tool.execute(target=str(artifacts_root / "nonexistent.json"), run_id="r2")
    assert result.status == ToolStatus.COMPLETED
    # collection_summary should be None — file not found is not a fatal error
    assert result.output.get("collection_summary") is None


def test_integration_hook_invalid_json_in_collection(monkeypatch, tmp_path):
    artifacts_root = tmp_path / "artifacts"
    artifacts_root.mkdir()
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(artifacts_root))
    collection = artifacts_root / "bad.json"
    collection.write_text("not json at all {{", encoding="utf-8")
    entry = get_catalog_entry("postman_collection_export")
    assert entry is not None
    tool = IntegrationHookTool(entry)
    result = tool.execute(target=str(collection), run_id="r3")
    assert result.status == ToolStatus.COMPLETED
    assert result.output.get("collection_summary") is None
