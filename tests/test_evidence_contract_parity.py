from __future__ import annotations

from apps.backend.src.core.evidence_contract import ensure_evidence_object, normalize_report_evidence


def test_ensure_evidence_object_from_canonical_payload():
    payload = {
        "evidence_id": "ev-123",
        "type": "recon",
        "tool": "dnsx",
        "target": "example.com",
        "timestamp": "2026-03-05T00:00:00+00:00",
        "structured_data": {"records": ["A 1.1.1.1"]},
        "confidence_score": 0.9,
        "artifacts": [
            {
                "artifact_path": "artifacts/run-1/dnsx/ev-123.json",
                "sha256": "abc123",
                "mime_type": "application/json",
                "description": "dns output",
            }
        ],
        "scope_status": "validated",
    }
    evidence = ensure_evidence_object(payload)
    assert evidence.evidence_id == "ev-123"
    assert evidence.tool == "dnsx"
    assert evidence.scope_status == "validated"
    assert evidence.artifacts[0].artifact_path.endswith("ev-123.json")


def test_ensure_evidence_object_from_legacy_payload():
    payload = {
        "id": "ev-legacy",
        "source": "naabu",
        "metadata": {"target": "api.example.com", "scope_status": "validated"},
        "path": "artifacts/r1/naabu/result.json",
        "hash": "deadbeef",
    }
    evidence = ensure_evidence_object(payload)
    assert evidence.evidence_id == "ev-legacy"
    assert evidence.tool == "naabu"
    assert evidence.target == "api.example.com"
    assert evidence.artifacts[0].sha256 == "deadbeef"


def test_normalize_report_evidence_emits_map_and_canonical_object():
    payload = {
        "evidence_id": "ev-777",
        "type": "http_probe",
        "tool": "httpx",
        "target": "https://example.com",
        "timestamp": "2026-03-05T00:00:00+00:00",
        "artifacts": [
            {
                "artifact_path": "artifacts/run-7/httpx/ev-777.json",
                "sha256": "cafebabe",
                "mime_type": "application/json",
                "description": "httpx output",
            }
        ],
    }
    normalized = normalize_report_evidence(payload)
    assert normalized["artifacts"]["httpx output"].endswith("ev-777.json")
    assert normalized["evidence_object"]["evidence_id"] == "ev-777"
    assert normalized["artifacts_list"][0]["sha256"] == "cafebabe"
