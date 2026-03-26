from __future__ import annotations

import json
from pathlib import Path

from apps.backend.src.core.evidence_integrity_service import EvidenceIntegrityService


def _line_count(path: Path) -> int:
    if not path.exists():
        return 0
    return len([line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])


def test_evidence_integrity_hashing_and_immutability(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path / "artifacts"))

    screenshot = tmp_path / "shot.png"
    recording = tmp_path / "rec.webm"
    wf_log = tmp_path / "workflow.log"
    screenshot.write_bytes(b"image-bytes")
    recording.write_bytes(b"video-bytes")
    wf_log.write_text("log-line\n", encoding="utf-8")

    service = EvidenceIntegrityService()
    finding = {
        "screenshots": [str(screenshot)],
        "recording_path": str(recording),
        "arbitration": {"final_verdict": "confirmed", "final_confidence": 0.8},
    }
    chain_record, provenance = service.track_finding_evidence(
        run_id="run-evidence",
        finding_key="finding-1",
        finding=finding,
        workflow_log_path=str(wf_log),
    )
    assert chain_record.status == "tracked"
    assert chain_record.record_hash
    assert chain_record.artifacts
    assert provenance
    assert any(row.get("artifact_type") == "screen_recording" for row in provenance)
    assert any(row.get("artifact_type") == "screenshot" for row in provenance)
    assert any(row.get("artifact_type") == "arbitration_output" for row in provenance)

    finalize = service.finalize_run_evidence(
        run_id="run-evidence",
        actor="pytest",
        reason="finalized_for_hil",
    )
    assert finalize["finalized"] is True
    assert service.is_finalized("run-evidence") is True

    chain_file = tmp_path / "artifacts" / "evidence_chain" / "run-evidence" / "chain.jsonl"
    metadata_file = tmp_path / "artifacts" / "evidence_chain" / "run-evidence" / "metadata.jsonl"
    before_chain_count = _line_count(chain_file)

    chain_record_after, provenance_after = service.track_finding_evidence(
        run_id="run-evidence",
        finding_key="finding-1",
        finding=finding,
        workflow_log_path=str(wf_log),
    )
    assert chain_record_after.status == "immutable_rejected"
    assert chain_record_after.immutable is True
    assert provenance_after and provenance_after[0]["event"] == "mutation_rejected_after_finalize"
    assert _line_count(chain_file) == before_chain_count
    assert _line_count(metadata_file) >= 2

    status_file = tmp_path / "artifacts" / "evidence_chain" / "run-evidence" / "status.json"
    payload = json.loads(status_file.read_text(encoding="utf-8"))
    assert payload["finalized"] is True

