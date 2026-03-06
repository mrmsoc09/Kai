from __future__ import annotations

import json

from apps.backend.src.core.format_exporter import ReportExporter
from apps.backend.src.core.report_formats import render_report


def test_render_report_handles_canonical_evidence_object():
    fmt = {"name": "Unit Test Format", "stakeholder": "test"}
    finding = {"title": "Test Finding", "summary": "Summary", "impact": "Impact", "scope": "example.com"}
    mitigation = {"plan": "Patch", "timeline": "ASAP"}
    evidence = {
        "evidence_id": "ev-1",
        "type": "recon",
        "tool": "dnsx",
        "target": "example.com",
        "timestamp": "2026-03-05T00:00:00+00:00",
        "artifacts": [
            {
                "artifact_path": "artifacts/run-1/dnsx/ev-1.json",
                "sha256": "1234",
                "mime_type": "application/json",
                "description": "dns records",
            }
        ],
    }
    rendered = render_report(fmt, finding, evidence, mitigation)
    assert "dns records" in rendered
    assert "artifacts/run-1/dnsx/ev-1.json" in rendered


def test_exporter_json_includes_canonical_evidence_fields():
    exporter = ReportExporter(format_id="does-not-exist", stakeholder="test")
    finding = {"id": "f-1", "title": "Title"}
    mitigation = {"plan": "mitigate"}
    evidence = {
        "evidence_id": "ev-2",
        "type": "scan",
        "tool": "naabu",
        "target": "example.com",
        "timestamp": "2026-03-05T00:00:00+00:00",
        "artifacts": [
            {
                "artifact_path": "artifacts/r2/naabu/ev-2.json",
                "sha256": "bead",
                "mime_type": "application/json",
                "description": "port scan",
            }
        ],
    }
    raw = exporter.export(finding, evidence, mitigation, format_type="json", report_id="REPORT_X")
    parsed = json.loads(raw)
    assert parsed["evidence"]["artifacts"]["port scan"].endswith("ev-2.json")
    assert parsed["evidence"]["evidence_object"]["evidence_id"] == "ev-2"
