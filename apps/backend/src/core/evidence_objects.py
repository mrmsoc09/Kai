from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional


def _artifacts_root() -> Path:
    return Path(os.getenv("K1_ARTIFACTS_ROOT", "artifacts")).resolve()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def create_evidence_object(
    *,
    tool: str,
    target: str,
    run_id: Optional[str],
    evidence_type: str,
    structured_data: Dict[str, Any],
    raw_payload: Dict[str, Any],
    confidence_score: float = 0.8,
    scope_status: str = "validated",
    description: str = "tool execution payload",
) -> Dict[str, Any]:
    """
    Create immutable evidence object and artifact metadata with SHA256 hash.
    Artifact policy: artifacts/<run_id>/<tool_id>/
    """
    effective_run_id = (run_id or "adhoc").strip() or "adhoc"
    tool_id = tool.strip()
    timestamp = datetime.now(timezone.utc).isoformat()
    evidence_id = f"ev-{uuid.uuid4()}"

    artifact_dir = _artifacts_root() / effective_run_id / tool_id
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{evidence_id}.json"
    artifact_bytes = json.dumps(raw_payload, sort_keys=True, ensure_ascii=False, indent=2).encode("utf-8")
    artifact_path.write_bytes(artifact_bytes)
    artifact_hash = _sha256_bytes(artifact_bytes)

    return {
        "evidence_id": evidence_id,
        "type": evidence_type,
        "tool": tool_id,
        "target": target,
        "timestamp": timestamp,
        "structured_data": structured_data,
        "confidence_score": confidence_score,
        "artifacts": [
            {
                "artifact_path": str(artifact_path),
                "sha256": artifact_hash,
                "mime_type": "application/json",
                "description": description,
            }
        ],
        "scope_status": scope_status,
    }
