from __future__ import annotations

from apps.backend.src.core import report_engine as report_engine_module


def _configure_report_paths(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("K1_REPORT_ENGINE_STATE_PATH", str(tmp_path / "report_state.json"))
    monkeypatch.setenv("K1_REPORT_ENGINE_ARTIFACT_DIR", str(tmp_path / "reports"))
    report_engine_module._ENGINE = None


def _sample_payload() -> dict:
    return {
        "finding": {
            "finding_id": "finding-export-1",
            "title": "SQL Injection on api.example.com",
            "vuln_type": "sqli",
            "severity": "critical",
            "target": "api.example.com",
            "endpoint": "https://api.example.com/v1/users",
            "summary": "SQL injection signal was validated on the users endpoint.",
            "impact": "Attacker can read unauthorized records and potentially mutate data.",
            "remediation": "Use parameterized queries and strict input validation.",
            "validation_evidence": [
                "Database error signature returned for crafted payload.",
                "Reproduced with deterministic response delta.",
            ],
            "confidence_score": 0.92,
            "payload": "' OR 1=1 --",
        },
        "artifacts": [
            {
                "http_request": "GET /v1/users?id=' OR 1=1 -- HTTP/1.1\nHost: api.example.com",
                "http_response": "HTTP/1.1 500 Internal Server Error\n\nSQL syntax error near ...",
            }
        ],
    }


def test_reports_export_markdown_and_json(client, tmp_path, monkeypatch):
    _configure_report_paths(tmp_path, monkeypatch)

    create_response = client.post("/reports/generate", json=_sample_payload())
    assert create_response.status_code == 200
    report_id = create_response.json()["report"]["report_id"]

    markdown_response = client.get(f"/reports/{report_id}/export", params={"format": "markdown"})
    assert markdown_response.status_code == 200
    assert "text/markdown" in markdown_response.headers.get("content-type", "")
    assert f'filename="{report_id}.md"' in markdown_response.headers.get("content-disposition", "")
    assert "SQL Injection on api.example.com" in markdown_response.text

    json_response = client.get(f"/reports/{report_id}/export", params={"format": "json"})
    assert json_response.status_code == 200
    assert "application/json" in json_response.headers.get("content-type", "")
    assert f'filename="{report_id}.json"' in json_response.headers.get("content-disposition", "")
    payload = json_response.json()
    assert payload["report_id"] == report_id
    assert payload["vulnerability_type"] == "sqli"


def test_reports_export_rejects_unsupported_format(client, tmp_path, monkeypatch):
    _configure_report_paths(tmp_path, monkeypatch)

    create_response = client.post("/reports/generate", json=_sample_payload())
    report_id = create_response.json()["report"]["report_id"]

    export_response = client.get(f"/reports/{report_id}/export", params={"format": "pdf"})
    assert export_response.status_code == 400
    assert export_response.json()["detail"] == "unsupported_export_format"
