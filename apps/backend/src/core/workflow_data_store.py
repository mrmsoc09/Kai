from __future__ import annotations

import json
from pathlib import Path
from typing import Any


MODEL_FILENAMES: dict[str, str] = {
    "targets": "targets.jsonl",
    "scope_rules": "scope_rules.jsonl",
    "workflow_runs": "workflow_runs.jsonl",
    "stage_runs": "stage_runs.jsonl",
    "tool_executions": "tool_executions.jsonl",
    "discovered_assets": "discovered_assets.jsonl",
    "dns_records": "dns_records.jsonl",
    "live_services": "live_services.jsonl",
    "web_applications": "web_applications.jsonl",
    "url_records": "url_records.jsonl",
    "endpoint_records": "endpoint_records.jsonl",
    "parameter_records": "parameter_records.jsonl",
    "technology_fingerprints": "technology_fingerprints.jsonl",
    "secret_findings": "secret_findings.jsonl",
    "vuln_candidates": "vuln_candidates.jsonl",
    "correlation_records": "correlation_records.jsonl",
    "analyst_exports": "analyst_exports.jsonl",
}


class WorkflowDataStore:
    def __init__(self, run_id: str, *, root: Path | None = None):
        base_root = root or Path("output").resolve()
        self.run_id = run_id
        self.base_root = base_root
        self.raw_dir = base_root / "raw" / run_id
        self.normalized_dir = base_root / "normalized" / run_id
        self.reports_dir = base_root / "reports" / run_id
        self.workflow_dir = base_root / "workflows" / run_id
        self.logs_dir = base_root / "logs"
        for directory in (
            self.raw_dir,
            self.normalized_dir,
            self.reports_dir,
            self.workflow_dir,
            self.logs_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

    def write_raw(self, relative_name: str, payload: dict[str, Any]) -> str:
        path = self.raw_dir / relative_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return str(path)

    def write_workflow_json(self, filename: str, payload: dict[str, Any]) -> str:
        path = self.workflow_dir / filename
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return str(path)

    def write_report_text(self, filename: str, content: str) -> str:
        path = self.reports_dir / filename
        path.write_text(content, encoding="utf-8")
        return str(path)

    def append_model(self, model_key: str, payload: dict[str, Any]) -> str:
        filename = MODEL_FILENAMES.get(model_key, f"{model_key}.jsonl")
        path = self.normalized_dir / filename
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str) + "\n")
        return str(path)

    def append_log(self, event: dict[str, Any]) -> str:
        path = self.logs_dir / f"workflow_{self.run_id}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, default=str) + "\n")
        return str(path)
