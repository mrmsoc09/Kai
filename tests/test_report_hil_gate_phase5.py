from __future__ import annotations

import json
from pathlib import Path

from apps.backend.src.core.report_hil_gate import ReportState, get_report_hil_gate_service


def _make_recording(artifacts_root: Path, run_id: str) -> str:
    rec_dir = artifacts_root / "recordings" / run_id
    rec_dir.mkdir(parents=True, exist_ok=True)
    rec_file = rec_dir / "seg_0000.mp4"
    rec_file.write_bytes(b"ftypmp42")
    return str(rec_file)


def _ready_payload(recording_path: str, *, confidence: float = 0.91) -> dict:
    return {
        "run_id": "phase5-run-001",
        "format_id": "google_vrp",
        "finding": {
            "title": "Stored XSS in ticket notes",
            "summary": "User-provided HTML is reflected without output encoding.",
            "impact": "An attacker can execute JavaScript in victim sessions.",
            "reproduction_steps": [
                "Authenticate as a normal user.",
                "Submit a ticket note containing a script payload.",
                "Load the ticket detail page and observe script execution.",
            ],
            "confidence_score": confidence,
            "validated": True,
        },
        "recording_path": recording_path,
        "arbitration": {
            "final_verdict": "confirmed",
            "final_confidence": confidence,
            "arbitration_reason": "structured and validation evidence agree",
            "conflict_detected": False,
        },
        "attack_chain_context": {
            "entry": "ticket_note",
            "pivot": "session_cookie_theft",
            "impact": "account_takeover",
        },
    }


def test_phase5_report_gate_requires_mandatory_fields(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    service = get_report_hil_gate_service()

    result = service.evaluate_report(
        run_id="phase5-missing",
        stakeholder="google_vrp",
        payload={"finding": {"title": "Incomplete finding"}},
    )

    assert result.readiness.report_ready is False
    assert result.readiness.report_state == ReportState.DRAFT
    assert "full_screen_recording_required" in result.readiness.missing_requirements
    assert "validated_exploit_evidence_required" in result.readiness.missing_requirements
    assert "confidence_score_required" in result.readiness.missing_requirements
    assert "arbitration_summary_required" in result.readiness.missing_requirements


def test_phase5_report_gate_generates_bbp_artifacts(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    recording_path = _make_recording(tmp_path, "phase5-run-001")
    service = get_report_hil_gate_service()

    payload = _ready_payload(recording_path)
    result = service.evaluate_report(
        run_id="phase5-run-001",
        stakeholder="google_vrp",
        payload=payload,
    )

    assert result.readiness.report_ready is True
    assert result.readiness.report_state == ReportState.VALIDATED

    report_json_path = Path(result.artifacts.report_json_path)
    report_md_path = Path(result.artifacts.report_markdown_path)
    assert report_json_path.exists()
    assert report_md_path.exists()

    report_payload = json.loads(report_json_path.read_text(encoding="utf-8"))
    assert report_payload["video_recording"] == str(Path(recording_path).resolve())
    assert report_payload["confidence_score"] == 0.91
    assert report_payload["arbitration_summary"]["final_verdict"] == "confirmed"
    assert report_payload["chain_of_custody"]["artifacts"][0]["sha256"]


def test_phase5_finalize_after_hil_is_immutable(monkeypatch, tmp_path):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))
    recording_path = _make_recording(tmp_path, "phase5-run-immut")
    service = get_report_hil_gate_service()

    payload = _ready_payload(recording_path, confidence=0.93)
    payload["hil_approved"] = True

    first = service.finalize_after_hil(
        run_id="phase5-run-immut",
        stakeholder="google_vrp",
        payload=payload,
        actor="pytest",
    )
    assert first.readiness.report_state == ReportState.FINALIZED
    assert first.report["immutable"] is True

    state_path = Path(first.artifacts.state_path)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["report_state"] == ReportState.FINALIZED
    assert state["immutable"] is True
    assert state["final_report_hash"]

    mutated_payload = _ready_payload(recording_path, confidence=0.40)
    mutated_payload["hil_approved"] = True
    second = service.finalize_after_hil(
        run_id="phase5-run-immut",
        stakeholder="google_vrp",
        payload=mutated_payload,
        actor="pytest",
    )
    assert second.readiness.report_ready is False
    assert second.readiness.reason == "report_finalized_immutable"
