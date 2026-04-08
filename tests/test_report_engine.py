from __future__ import annotations

from apps.backend.src.core.report_engine import ReportEngine


def _sample_finding(**overrides):
    base = {
        "finding_id": "finding-001",
        "title": "Reflected XSS on search endpoint",
        "vuln_type": "xss",
        "severity": "high",
        "target": "app.example.com",
        "endpoint": "https://app.example.com/search",
        "parameter": "q",
        "payload": "<script>alert(1)</script>",
        "summary": "Untrusted input is reflected without output encoding.",
        "impact": "Attacker can execute script in victim browser context.",
        "remediation": "Encode output and sanitize untrusted input.",
        "validation_evidence": [
            "Sentinel reflected in response body.",
            "Response diff confirmed deterministic behavior.",
        ],
        "confidence_score": 0.89,
    }
    base.update(overrides)
    return base


def _sample_chain():
    return {
        "chain_id": "chain-1",
        "score": 0.82,
        "confidence_score": 0.76,
        "reasoning_summary": "XSS signal chains into session takeover path.",
        "nodes": [
            {"node_id": "n1", "value": "finding-001", "vuln_type": "xss"},
            {"node_id": "n2", "value": "finding-010", "vuln_type": "session_hijack"},
        ],
        "edges": [{"edge_id": "e1", "source_id": "n1", "target_id": "n2", "edge_type": "bypasses"}],
    }


def test_report_creation_includes_chain_and_quality(tmp_path, monkeypatch):
    monkeypatch.setenv("K1_REPORT_ENGINE_STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setenv("K1_REPORT_ENGINE_ARTIFACT_DIR", str(tmp_path / "reports"))
    engine = ReportEngine()

    report, deduplicated = engine.generate_and_store_report(
        finding=_sample_finding(),
        exploit_chain=_sample_chain(),
        artifacts=[
            {
                "http_request": "GET /search?q=%3Cscript%3Ealert(1)%3C/script%3E HTTP/1.1\nHost: app.example.com",
                "http_response": "HTTP/1.1 200 OK\n\n<script>alert(1)</script>",
            }
        ],
        mission_id="mission-1",
        opportunity_id="opp-1",
        generated_by="tester",
    )

    assert deduplicated is False
    assert report.exploit_chain is not None
    assert report.quality_score > 0.6
    assert report.mission_id == "mission-1"
    assert report.opportunity_id == "opp-1"
    assert report.artifact_uri is not None
    assert report.http_requests
    assert report.http_responses


def test_report_deduplication_uses_duplicate_hash(tmp_path, monkeypatch):
    monkeypatch.setenv("K1_REPORT_ENGINE_STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setenv("K1_REPORT_ENGINE_ARTIFACT_DIR", str(tmp_path / "reports"))
    engine = ReportEngine()

    first, first_dedup = engine.generate_and_store_report(finding=_sample_finding(), exploit_chain=None, artifacts=[])
    second, second_dedup = engine.generate_and_store_report(finding=_sample_finding(), exploit_chain=None, artifacts=[])

    assert first_dedup is False
    assert second_dedup is True
    assert first.report_id == second.report_id
    assert first.duplicate_hash == second.duplicate_hash


def test_report_listing_filters_by_mission_and_severity(tmp_path, monkeypatch):
    monkeypatch.setenv("K1_REPORT_ENGINE_STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setenv("K1_REPORT_ENGINE_ARTIFACT_DIR", str(tmp_path / "reports"))
    engine = ReportEngine()

    engine.generate_and_store_report(
        finding=_sample_finding(finding_id="f-1", severity="critical", target="critical.example.com"),
        mission_id="mission-critical",
    )
    engine.generate_and_store_report(
        finding=_sample_finding(finding_id="f-2", severity="low", target="low.example.com", payload="payload-2"),
        mission_id="mission-low",
    )

    critical_reports = engine.list_reports(severity="critical")
    mission_low_reports = engine.reports_for_mission("mission-low")

    assert len(critical_reports) == 1
    assert critical_reports[0].severity == "critical"
    assert len(mission_low_reports) == 1
    assert mission_low_reports[0].mission_id == "mission-low"


def test_report_listing_filters_by_opportunity_id(tmp_path, monkeypatch):
    monkeypatch.setenv("K1_REPORT_ENGINE_STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setenv("K1_REPORT_ENGINE_ARTIFACT_DIR", str(tmp_path / "reports"))
    engine = ReportEngine()

    engine.generate_and_store_report(
        finding=_sample_finding(finding_id="f-11", payload="payload-11"),
        mission_id="mission-11",
        opportunity_id="opp-keep",
    )
    engine.generate_and_store_report(
        finding=_sample_finding(finding_id="f-12", payload="payload-12"),
        mission_id="mission-12",
        opportunity_id="opp-drop",
    )

    kept = engine.list_reports(opportunity_id="opp-keep")
    assert len(kept) == 1
    assert kept[0].opportunity_id == "opp-keep"


def test_report_quality_score_is_capped_when_submission_candidate_false(tmp_path, monkeypatch):
    monkeypatch.setenv("K1_REPORT_ENGINE_STATE_PATH", str(tmp_path / "state.json"))
    monkeypatch.setenv("K1_REPORT_ENGINE_ARTIFACT_DIR", str(tmp_path / "reports"))
    engine = ReportEngine()

    finding = _sample_finding(
        finding_id="f-low-impact",
        vulnerability_type="xss",
        summary="Thin evidence",
        validation_evidence=[],
        confidence_score=0.9,
        baseline_response={"status_code": 200, "body": "ok"},
        exploit_response={"status_code": 200, "body": "ok"},
    )
    report, _ = engine.generate_and_store_report(finding=finding, exploit_chain=None, artifacts=[])
    assert report.submission_candidate is False
    assert report.quality_score <= 0.74
