from __future__ import annotations

from apps.backend.src.core.confidence_engine import (
    assess_finding_confidence,
    enrich_findings_with_confidence,
)


def test_assess_finding_confidence_includes_breakdown_and_explanation():
    finding = {
        "title": "Potential SQL Injection",
        "target": "example.com",
        "severity_hint": "high",
        "source_tool": "nuclei",
        "evidence_ref": "/tmp/raw.json",
        "validated": True,
    }
    context = {
        "tool_status": "completed",
        "exit_code": 0,
        "tool_error": False,
        "parsed_ok": True,
        "parsed_items": 3,
        "scope_valid": True,
    }
    assessment = assess_finding_confidence(finding=finding, context=context, threshold=0.7)
    assert 0.0 <= assessment.confidence_score <= 1.0
    assert assessment.confidence_breakdown.tool_reliability >= 0.8
    assert isinstance(assessment.confidence_explanation, str)
    assert assessment.confidence_explanation
    assert assessment.trigger_decision.threshold == 0.7


def test_enrich_findings_with_confidence_injects_fields_and_score_records():
    findings = [
        {
            "title": "XSS candidate",
            "target": "app.example.com",
            "severity_hint": "medium",
            "source_tool": "dalfox",
            "evidence_ref": "/tmp/a.json",
        },
        {
            "title": "XSS candidate",
            "target": "app.example.com",
            "severity_hint": "medium",
            "source_tool": "dalfox",
            "evidence_ref": "/tmp/b.json",
        },
    ]
    enriched, records = enrich_findings_with_confidence(
        run_id="run-1",
        findings=findings,
        context={"tool_status": "completed", "scope_valid": True, "parsed_ok": True},
    )
    assert len(enriched) == 2
    assert len(records) == 2
    for row in enriched:
        assert "confidence_score" in row
        assert "confidence_breakdown" in row
        assert "confidence_explanation" in row
        assert "trigger_decision" in row
        assert "requires_validation" in row
        assert "validation_reason" in row
    assert records[0]["run_id"] == "run-1"
    assert "confidence_score" in records[0]
    assert "trigger_decision" in records[0]

