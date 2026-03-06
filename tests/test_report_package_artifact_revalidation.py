from __future__ import annotations

import hashlib

from apps.backend.src.core.packager import revalidate_evidence_artifacts


def test_revalidate_evidence_artifacts_passes_for_matching_hash(tmp_path):
    artifact = tmp_path / "artifact.json"
    payload = b'{"ok":true}'
    artifact.write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()

    result = revalidate_evidence_artifacts(
        [{"artifact_path": str(artifact), "sha256": digest}]
    )
    assert result["ok"] is True
    assert result["validated_hash_count"] == 1
    assert result["failures"] == []


def test_revalidate_evidence_artifacts_fails_for_missing_file(tmp_path):
    missing = tmp_path / "missing.json"
    result = revalidate_evidence_artifacts(
        [{"artifact_path": str(missing), "sha256": "abc"}]
    )
    assert result["ok"] is False
    assert result["failures"][0]["error"] == "artifact_missing"


def test_revalidate_evidence_artifacts_fails_for_hash_mismatch(tmp_path):
    artifact = tmp_path / "artifact.json"
    artifact.write_bytes(b"real-content")

    result = revalidate_evidence_artifacts(
        [{"artifact_path": str(artifact), "sha256": "0" * 64}]
    )
    assert result["ok"] is False
    assert result["failures"][0]["error"] == "artifact_hash_mismatch"
