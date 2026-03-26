from __future__ import annotations

from apps.backend.src.core.attack_graph_service import AttackGraphService


def test_attack_graph_service_builds_relationships_and_scores():
    service = AttackGraphService()
    findings = [
        {
            "finding_id": "f-1",
            "title": "Reflected XSS",
            "target": "app.example.com",
            "severity": "high",
            "severity_hint": "high",
            "vuln_type": "xss",
            "final_verdict": "confirmed",
            "final_confidence": 0.84,
            "confidence_score": 0.84,
            "parameter_name": "q",
            "recording_path": "/tmp/rec.webm",
            "screenshots": ["/tmp/shot1.png"],
        },
        {
            "finding_id": "f-2",
            "title": "CSRF chain",
            "target": "app.example.com",
            "severity": "medium",
            "severity_hint": "medium",
            "vuln_type": "csrf",
            "final_verdict": "escalate",
            "final_confidence": 0.55,
            "confidence_score": 0.55,
            "parameter_name": "token",
        },
    ]
    result = service.build_attack_graph(run_id="run-graph", findings=findings)
    assert result.summary.node_count > 0
    assert result.summary.edge_count > 0
    assert result.summary.dependency_count >= 0
    assert 0.0 <= result.summary.impact_score <= 1.0
    assert 0.0 <= result.summary.prioritization_score <= 1.0
    assert isinstance(result.explanation, str) and result.explanation
    assert result.chains is not None
    for chain in result.chains:
        assert "validated_chain" in chain
        assert "chain_priority" in chain
        assert 0.0 <= float(chain["chain_priority"]) <= 1.0


def test_attack_graph_service_enriches_findings_with_graph_context():
    service = AttackGraphService()
    findings = [
        {
            "finding_id": "f-1",
            "title": "SQLi",
            "target": "api.example.com",
            "severity_hint": "high",
            "vuln_type": "sqli",
            "final_confidence": 0.7,
        },
        {
            "finding_id": "f-2",
            "title": "RCE path",
            "target": "api.example.com",
            "severity_hint": "critical",
            "vuln_type": "rce",
            "final_confidence": 0.8,
        },
    ]
    enriched, graph = service.enrich_findings_with_graph_context(run_id="run-ctx", findings=findings)
    assert len(enriched) == 2
    assert graph.summary.node_count > 0
    for row in enriched:
        assert "graph_chain_priority" in row
        assert "graph_impact_score" in row
        assert "graph_prioritization_score" in row
        assert "graph_adjusted_priority" in row
        assert 0.0 <= float(row["graph_adjusted_priority"]) <= 1.0
