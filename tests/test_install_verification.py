from __future__ import annotations

import importlib.util
from pathlib import Path

from apps.backend.src.core.tool_registry_catalog import RetryPolicy, ToolCatalogEntry


def _load_verify_module():
    root = Path(__file__).resolve().parents[1]
    script_path = root / "scripts" / "verify_tool_registry_install.py"
    spec = importlib.util.spec_from_file_location("verify_tool_registry_install", script_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def test_verify_tool_registry_install_writes_report(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("K1_WORKFLOW_OUTPUT_ROOT", str(tmp_path))
    module = _load_verify_module()

    fake_entries = [
        ToolCatalogEntry(
            name="subfinder",
            category="recon_asset_discovery",
            execution_mode="native",
            binary_path="subfinder",
            container_image=None,
            install_verification_cmd=["subfinder", "-version"],
            input_schema={"target": "domain"},
            output_schema={"subdomains": "list[str]"},
            timeout_seconds=60,
            retry_policy=RetryPolicy(max_attempts=1, backoff_seconds=0.0),
            safety_classification="passive",
            tags=["recon"],
            dependencies=[],
            api_keys_required=[],
            enabled_by_default=True,
        )
    ]

    monkeypatch.setattr(module, "list_catalog_entries", lambda enabled_only=False: fake_entries)
    monkeypatch.setattr(module, "_run_verify", lambda command: (True, "ok"))

    code = module.main()
    assert code == 0
    report = tmp_path / "reports" / "tool_install_verification.json"
    assert report.exists()
    contents = report.read_text(encoding="utf-8")
    assert "subfinder" in contents
