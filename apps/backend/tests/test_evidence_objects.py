from __future__ import annotations

import json
from pathlib import Path

from apps.backend.src.core.evidence_objects import create_evidence_object


def test_create_evidence_object_writes_hashed_artifact(
    monkeypatch,
    tmp_path: Path,
):
    monkeypatch.setenv("K1_ARTIFACTS_ROOT", str(tmp_path))

    evidence = create_evidence_object(
        tool="dnsx",
        target="example.com",
        run_id="run-123",
        evidence_type="dns",
        structured_data={"records": ["a.example.com"]},
        raw_payload={"stdout": "a.example.com A 1.1.1.1"},
        confidence_score=0.9,
    )

    artifact = evidence["artifacts"][0]
    artifact_path = Path(artifact["artifact_path"])
    assert artifact_path.exists()
    assert artifact_path.parent == tmp_path / "run-123" / "dnsx"

    content = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert content["stdout"] == "a.example.com A 1.1.1.1"
    assert len(artifact["sha256"]) == 64
