from __future__ import annotations

from apps.backend.src.core.report_validator import build_evidence_trace_matrix, evaluate_report_quality_gate


def test_trace_matrix_links_claims_to_artifacts():
    finding = {"claims": ["Sensitive token is exposed in response body"]}
    evidence = {"artifacts": {"response_body": "artifacts/r1/httpx/response_token_dump.json"}}
    trace = build_evidence_trace_matrix(finding, evidence)
    assert trace["claims_count"] == 1
    assert trace["ok"] is True
    assert trace["rows"][0]["linked"] is True


def test_quality_gate_fails_when_claims_unlinked():
    finding = {"claims": ["Privilege escalation via hidden admin endpoint"]}
    evidence = {"artifacts": {}}
    rendered = "# Report\n## Summary\ntext\n## Impact\ntext\n## Steps to Reproduce\n1. a\n2. b\n3. c\n## Evidence\nnone\n## Mitigation\nfix\n## Timeline\nsoon\n"
    gate = evaluate_report_quality_gate(
        stakeholder="google_vrp",
        rendered_content=rendered,
        has_recording=True,
        finding_data=finding,
        evidence_data=evidence,
    )
    assert gate["trace_matrix"]["ok"] is False
    assert gate["ok"] is False
