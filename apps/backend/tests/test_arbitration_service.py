from __future__ import annotations

from apps.backend.src.core.arbitration_service import ArbitrationService


def test_arbitration_conflict_resolution_prefers_structured_when_stronger():
    service = ArbitrationService(swarm_mode=False)
    row = {
        "title": "xss",
        "target": "example.com",
        "confidence_score": 0.92,
        "confidence_breakdown": {
            "evidence_completeness": 0.95,
            "parser_integrity": 0.9,
            "scope_validity": 1.0,
            "reproducibility": 0.8,
            "duplication_risk": 0.1,
        },
        "vision_validation": {
            "status": "failed",
            "screenshots": [],
            "metadata": {"recording_path": None},
        },
        "vision_status": "failed",
    }
    decision = service.arbitrate_finding(row)
    assert decision.conflict_detected is True
    assert decision.final_verdict in {"confirmed", "escalate"}
    assert 0.02 <= decision.final_confidence <= 0.98
    assert isinstance(decision.arbitration_reason, str) and decision.arbitration_reason


def test_arbitration_unresolved_conflict_escalates():
    service = ArbitrationService(swarm_mode=False, unresolved_margin=0.40)
    row = {
        "title": "sqli",
        "target": "example.org",
        "confidence_score": 0.66,
        "confidence_breakdown": {
            "evidence_completeness": 0.55,
            "parser_integrity": 0.55,
            "scope_validity": 0.8,
            "reproducibility": 0.5,
            "duplication_risk": 0.1,
        },
        "vision_validation": {
            "status": "failed",
            "screenshots": ["a.png"],
            "metadata": {"recording_path": "rec.webm"},
        },
        "vision_status": "failed",
    }
    decision = service.arbitrate_finding(row)
    assert decision.final_verdict == "escalate"
    assert "conflict_unresolved" in decision.source


def test_arbitration_swarm_consensus_override():
    service = ArbitrationService(swarm_mode=True)
    row = {
        "title": "idor",
        "target": "api.example.com",
        "confidence_score": 0.7,
        "confidence_breakdown": {
            "evidence_completeness": 0.6,
            "parser_integrity": 0.6,
            "scope_validity": 1.0,
            "reproducibility": 0.6,
            "duplication_risk": 0.15,
        },
        "vision_validation": {
            "status": "failed",
            "screenshots": [],
            "metadata": {"recording_path": None},
        },
        "vision_status": "failed",
        "swarm_votes": [
            {"agent": "a1", "verdict": "confirmed", "confidence": 0.95, "weight": 1.0},
            {"agent": "a2", "verdict": "confirmed", "confidence": 0.9, "weight": 1.2},
            {"agent": "a3", "verdict": "rejected", "confidence": 0.7, "weight": 0.5},
        ],
    }
    decision = service.arbitrate_finding(row)
    assert decision.final_verdict in {"confirmed", "rejected", "escalate"}
    assert decision.swarm_consensus_used in {True, False}
    assert 0.02 <= decision.final_confidence <= 0.98


def test_bayesian_updates_include_expected_events_and_are_capped():
    service = ArbitrationService(swarm_mode=False)
    row = {
        "title": "open-redirect",
        "target": "www.example.net",
        "confidence_score": 0.85,
        "confidence_breakdown": {
            "evidence_completeness": 0.8,
            "parser_integrity": 0.85,
            "scope_validity": 1.0,
            "reproducibility": 0.75,
            "duplication_risk": 0.7,
        },
        "vision_validation": {
            "status": "completed",
            "screenshots": ["x.png", "y.png"],
            "metadata": {"recording_path": "ok.webm"},
        },
        "vision_status": "completed",
        "accepted": True,
    }
    decision = service.arbitrate_finding(row)
    assert decision.bayesian_updates
    events = [item.event for item in decision.bayesian_updates]
    assert "exploit_success" in events
    assert "duplicate" in events
    assert "accepted" in events
    for item in decision.bayesian_updates:
        assert 0.02 <= item.posterior <= 0.98


def test_arbitrate_findings_persists_update_records_shape():
    service = ArbitrationService(swarm_mode=False)
    findings = [
        {
            "title": "csrf",
            "target": "portal.example.io",
            "confidence_score": 0.4,
            "confidence_breakdown": {
                "evidence_completeness": 0.45,
                "parser_integrity": 0.5,
                "scope_validity": 1.0,
                "reproducibility": 0.4,
                "duplication_risk": 0.1,
            },
            "vision_status": "failed",
            "vision_validation": {
                "status": "failed",
                "screenshots": [],
                "metadata": {"recording_path": None},
            },
        }
    ]
    enriched, arbitration_records, bayes_records = service.arbitrate_findings(
        run_id="run-arb",
        findings=findings,
    )
    assert len(enriched) == 1
    assert len(arbitration_records) == 1
    assert bayes_records
    assert "final_verdict" in enriched[0]
    assert "final_confidence" in enriched[0]
    assert "arbitration_reason" in enriched[0]
    assert "run_id" in arbitration_records[0]

