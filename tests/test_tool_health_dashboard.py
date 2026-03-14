from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from apps.backend.src.core import tool_health_service as health
from apps.backend.src.core.tool_registry_catalog import RetryPolicy, ToolCatalogEntry


def _entry(
    *,
    name: str = "subfinder",
    execution_mode: str = "native",
    api_keys_required: list[str] | None = None,
) -> ToolCatalogEntry:
    return ToolCatalogEntry(
        name=name,
        category="recon_asset_discovery",
        execution_mode=execution_mode,
        binary_path=name,
        container_image=None,
        install_verification_cmd=[name, "--version"],
        input_schema={"target": "domain"},
        output_schema={"items": "list[str]"},
        timeout_seconds=60,
        retry_policy=RetryPolicy(max_attempts=1, backoff_seconds=0.0),
        safety_classification="passive",
        tags=["recon"],
        dependencies=[],
        api_keys_required=api_keys_required or [],
        enabled_by_default=True,
    )


def _minimal_dashboard() -> dict:
    return {
        "generated_at": "2026-03-12T00:00:00+00:00",
        "install_timeout_seconds": 8,
        "telemetry_window": 20,
        "smoke_tests_enabled": False,
        "summary": {
            "total": 1,
            "healthy": 1,
            "degraded": 0,
            "unavailable": 0,
            "unchecked": 0,
            "total_tools": 1,
            "healthy_tools": 1,
            "tools_missing_binary": 0,
            "tools_missing_credentials": 0,
            "tools_with_failed_verification": 0,
        },
        "by_category": {},
        "tools": [
            {
                "tool_name": "subfinder",
                "name": "subfinder",
                "category": "recon_asset_discovery",
                "enabled_status": "enabled",
                "enabled": True,
                "execution_mode": "native",
                "safety_classification": "passive",
                "enabled_by_default": True,
                "policy_enabled": True,
                "tags": ["recon"],
                "api_keys_required": [],
                "timeout_seconds": 60,
                "binary_or_image_presence": {"status": "present"},
                "install_verification_status": "ok",
                "required_environment_variables_present": True,
                "credential_status": "not_required",
                "wrapper_smoke_test_status": "skipped",
                "safe_mode_compatibility": {"compatible": True, "requires_override": False},
                "last_execution_status": "COMPLETED",
                "last_failure_reason": None,
                "last_execution_at": "2026-03-12T00:00:00+00:00",
                "install": {"status": "ok", "detail": "", "checked_at": "2026-03-12T00:00:00+00:00"},
                "credentials": {
                    "status": "not_required",
                    "required_keys": [],
                    "present_keys": [],
                    "missing_keys": [],
                    "detail": "",
                },
                "wrapper": {"status": "ok", "registry_tool_id": "subfinder", "detail": ""},
                "smoke_test": {"status": "skipped", "detail": "disabled"},
                "recent_executions": {
                    "window_size": 20,
                    "total": 1,
                    "completed": 1,
                    "failed": 0,
                    "failure_rate": 0.0,
                    "last_status": "COMPLETED",
                    "last_executed_at": "2026-03-12T00:00:00+00:00",
                    "failure_reasons": [],
                },
                "overall_health": "healthy",
                "checked_at": "2026-03-12T00:00:00+00:00",
            }
        ],
    }


def test_missing_binary_detection(monkeypatch):
    entry = _entry()
    monkeypatch.setattr(health.shutil, "which", lambda _name: None)
    runtime = health.check_runtime_presence(entry)
    assert runtime["status"] == "missing"


def test_missing_environment_credentials(monkeypatch):
    entry = _entry(api_keys_required=["SHODAN_API_KEY", "CENSYS_API_ID"])
    monkeypatch.setenv("SHODAN_API_KEY", "present")
    monkeypatch.delenv("CENSYS_API_ID", raising=False)
    credentials = health.check_credentials(entry)
    assert credentials["status"] == "missing"
    assert credentials["missing_keys"] == ["CENSYS_API_ID"]


def test_hook_mode_runtime_not_required():
    entry = _entry(name="burp_suite_pro", execution_mode="hook")
    runtime = health.check_runtime_presence(entry)
    assert runtime["status"] == "not_required"


def test_install_verification_uses_cached_report():
    entry = _entry(name="subfinder")
    cached = {"subfinder": {"ok": False, "output": "missing binary"}}
    install = health.check_install(entry, cached_report=cached)
    assert install["status"] == "missing"
    assert install["source"] == "cached_report"


def test_load_install_report_cache(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("K1_WORKFLOW_OUTPUT_ROOT", str(tmp_path))
    report = tmp_path / "reports" / "tool_install_verification.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        json.dumps([{"tool": "subfinder", "ok": True, "output": "ok"}]),
        encoding="utf-8",
    )
    cache = health._load_install_report_cache()
    assert cache["subfinder"]["ok"] is True


def test_healthy_tool_status(monkeypatch):
    entry = _entry(name="healthytool")
    monkeypatch.setattr(
        health,
        "check_runtime_presence",
        lambda _entry: {"status": "present"},
    )
    monkeypatch.setattr(
        health,
        "check_install",
        lambda _entry, timeout=8, cached_report=None: {
            "status": "ok",
            "detail": "ok",
            "checked_at": "2026-03-12T00:00:00+00:00",
            "source": "live_check",
        },
    )
    monkeypatch.setattr(
        health,
        "check_credentials",
        lambda _entry: {
            "status": "not_required",
            "required_keys": [],
            "present_keys": [],
            "missing_keys": [],
            "detail": "",
        },
    )
    monkeypatch.setattr(
        health,
        "check_wrapper",
        lambda _entry: {"status": "ok", "registry_tool_id": "healthytool", "detail": "", "tool": object()},
    )
    monkeypatch.setattr(
        health,
        "check_wrapper_smoke",
        lambda _entry, wrapper_result, run_smoke_tests: {"status": "ok", "detail": "ok"},
    )
    monkeypatch.setattr(health, "check_policy", lambda _entry: True)
    monkeypatch.setattr(
        health,
        "check_safe_mode_compatibility",
        lambda _entry: {"compatible": True, "requires_override": False, "detail": "safe-mode compatible"},
    )
    monkeypatch.setattr(health, "_load_recent_telemetry", lambda _name, window: [])
    report = health.check_tool(entry, run_smoke_tests=True)
    assert report["overall_health"] == "healthy"
    assert report["tool_name"] == "healthytool"


def test_tools_health_api_endpoint(client, monkeypatch):
    import importlib

    tools_router = importlib.import_module("apps.backend.src.routers.tools")

    class _Registry:
        def count(self) -> int:
            return 1

    dashboard = _minimal_dashboard()

    monkeypatch.setattr(tools_router, "get_tool_registry", lambda: _Registry())
    monkeypatch.setattr(tools_router, "build_dashboard", lambda **_kwargs: dashboard)
    monkeypatch.setattr(tools_router, "apply_execution_history", lambda *_args, **_kwargs: None)

    async def _fake_load_last_execution_records(_db, *, limit: int = 2000):
        return {}

    monkeypatch.setattr(tools_router, "load_last_execution_records", _fake_load_last_execution_records)
    monkeypatch.setattr(tools_router, "write_dashboard_report", lambda _dashboard: "/tmp/tool_health_report.json")

    response = client.get("/api/v1/tools/health?write_report=true")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    data = payload["data"]
    assert data["total_tools"] == 1
    assert data["summary"]["healthy_tools"] == 1
    assert data["tools"][0]["tool_name"] == "subfinder"
    assert data["report_path"] == "/tmp/tool_health_report.json"


def test_tools_health_cli_json_and_report(monkeypatch, tmp_path: Path):
    import importlib

    tools_cmd = importlib.import_module("apps.backend.src.cli.commands.tools")

    dashboard = _minimal_dashboard()
    report_path_override = tmp_path / "tool-health.json"

    monkeypatch.setattr(tools_cmd, "build_dashboard", lambda **_kwargs: dashboard)
    monkeypatch.setattr(
        tools_cmd,
        "write_dashboard_report",
        lambda _dashboard, report_path=None: str(report_path or report_path_override),
    )

    runner = CliRunner()
    result = runner.invoke(
        tools_cmd.tools,
        ["health", "--json-output", "--write-report", "--report-file", str(report_path_override)],
    )
    assert result.exit_code == 0
    assert "Tool Health" in result.output
    assert "subfinder" in result.output
