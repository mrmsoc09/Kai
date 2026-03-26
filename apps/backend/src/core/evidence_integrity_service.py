from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .helpers import artifacts_root, workflow_output_root


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_json_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8", errors="replace")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_file(path: str | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None
    digest = hashlib.sha256()
    with p.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


class EvidenceArtifactRecord(BaseModel):
    artifact_type: str
    artifact_path: str | None = None
    exists: bool = False
    sha256: str | None = None
    payload_hash: str | None = None
    provenance: dict[str, Any] = Field(default_factory=dict)


class EvidenceChainRecord(BaseModel):
    finding_key: str
    immutable: bool
    status: str
    artifacts: list[EvidenceArtifactRecord] = Field(default_factory=list)
    record_hash: str
    prev_hash: str | None = None
    reason: str
    timestamp: str

    def persistence_record(self, *, run_id: str) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "finding_key": self.finding_key,
            "immutable": self.immutable,
            "status": self.status,
            "artifacts": [row.model_dump() for row in self.artifacts],
            "record_hash": self.record_hash,
            "prev_hash": self.prev_hash,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


@dataclass
class _LedgerPaths:
    root: Path
    chain_file: Path
    provenance_file: Path
    metadata_file: Path
    status_file: Path


class EvidenceIntegrityService:
    """
    Evidence hashing + provenance + immutability lock.
    Once finalized, evidence records become append-only metadata (no edits).
    """

    def _paths(self, run_id: str) -> _LedgerPaths:
        root = artifacts_root() / "evidence_chain" / (run_id or "unknown")
        root.mkdir(parents=True, exist_ok=True)
        return _LedgerPaths(
            root=root,
            chain_file=root / "chain.jsonl",
            provenance_file=root / "provenance.jsonl",
            metadata_file=root / "metadata.jsonl",
            status_file=root / "status.json",
        )

    def _read_status(self, run_id: str) -> dict[str, Any]:
        paths = self._paths(run_id)
        if not paths.status_file.exists():
            return {"finalized": False, "finalized_at": None, "actor": None}
        try:
            payload = json.loads(paths.status_file.read_text(encoding="utf-8"))
            return {
                "finalized": bool(payload.get("finalized")),
                "finalized_at": payload.get("finalized_at"),
                "actor": payload.get("actor"),
            }
        except Exception:
            return {"finalized": False, "finalized_at": None, "actor": None}

    def is_finalized(self, run_id: str) -> bool:
        return bool(self._read_status(run_id).get("finalized"))

    def _last_chain_hash(self, run_id: str) -> str | None:
        paths = self._paths(run_id)
        if not paths.chain_file.exists():
            return None
        try:
            last = None
            with paths.chain_file.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    last = json.loads(line)
            if isinstance(last, dict):
                return str(last.get("record_hash") or "") or None
        except Exception:
            return None
        return None

    def _append_jsonl(self, path: Path, payload: dict[str, Any]) -> None:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, default=str) + "\n")

    def _artifact_records(
        self,
        *,
        finding: dict[str, Any],
        workflow_log_path: str | None,
    ) -> list[EvidenceArtifactRecord]:
        records: list[EvidenceArtifactRecord] = []

        screenshots = finding.get("screenshots")
        if isinstance(screenshots, list):
            for shot in screenshots:
                shot_path = str(shot).strip()
                if not shot_path:
                    continue
                p = Path(shot_path)
                records.append(
                    EvidenceArtifactRecord(
                        artifact_type="screenshot",
                        artifact_path=shot_path,
                        exists=p.exists() and p.is_file(),
                        sha256=_sha256_file(shot_path),
                        provenance={"source": "vision_validation", "field": "screenshots"},
                    )
                )

        recording_path = str(finding.get("recording_path") or "").strip()
        if recording_path:
            p = Path(recording_path)
            records.append(
                EvidenceArtifactRecord(
                    artifact_type="screen_recording",
                    artifact_path=recording_path,
                    exists=p.exists() and p.is_file(),
                    sha256=_sha256_file(recording_path),
                    provenance={"source": "vision_validation", "field": "recording_path"},
                )
            )

        if workflow_log_path:
            p = Path(workflow_log_path)
            records.append(
                EvidenceArtifactRecord(
                    artifact_type="workflow_log",
                    artifact_path=str(p),
                    exists=p.exists() and p.is_file(),
                    sha256=_sha256_file(str(p)),
                    provenance={"source": "workflow_executor", "field": "workflow_log"},
                )
            )

        arbitration = finding.get("arbitration")
        if isinstance(arbitration, dict):
            records.append(
                EvidenceArtifactRecord(
                    artifact_type="arbitration_output",
                    artifact_path=None,
                    exists=True,
                    sha256=None,
                    payload_hash=_stable_json_hash(arbitration),
                    provenance={"source": "arbitration_service", "field": "arbitration"},
                )
            )

        return records

    def track_finding_evidence(
        self,
        *,
        run_id: str,
        finding_key: str,
        finding: dict[str, Any],
        reason: str = "evidence_tracking",
        workflow_log_path: str | None = None,
    ) -> tuple[EvidenceChainRecord, list[dict[str, Any]]]:
        paths = self._paths(run_id)
        if workflow_log_path is None:
            workflow_log_path = str(workflow_output_root() / "logs" / f"workflow_{run_id}.jsonl")
        artifacts = self._artifact_records(finding=finding, workflow_log_path=workflow_log_path)
        now = _utcnow_iso()

        if self.is_finalized(run_id):
            rejection_payload = {
                "event": "mutation_rejected_after_finalize",
                "run_id": run_id,
                "finding_key": finding_key,
                "timestamp": now,
                "reason": reason,
            }
            self._append_jsonl(paths.metadata_file, rejection_payload)
            record_payload = {
                "finding_key": finding_key,
                "immutable": True,
                "status": "immutable_rejected",
                "artifacts": [row.model_dump() for row in artifacts],
                "prev_hash": self._last_chain_hash(run_id),
                "reason": "run_finalized_append_only_metadata",
                "timestamp": now,
            }
            record_hash = _stable_json_hash(record_payload)
            record = EvidenceChainRecord(
                finding_key=finding_key,
                immutable=True,
                status="immutable_rejected",
                artifacts=artifacts,
                prev_hash=record_payload["prev_hash"],
                record_hash=record_hash,
                reason="run_finalized_append_only_metadata",
                timestamp=now,
            )
            return record, [rejection_payload]

        prev_hash = self._last_chain_hash(run_id)
        payload = {
            "finding_key": finding_key,
            "immutable": False,
            "status": "tracked",
            "artifacts": [row.model_dump() for row in artifacts],
            "prev_hash": prev_hash,
            "reason": reason,
            "timestamp": now,
        }
        record_hash = _stable_json_hash(payload)
        record = EvidenceChainRecord(
            finding_key=finding_key,
            immutable=False,
            status="tracked",
            artifacts=artifacts,
            prev_hash=prev_hash,
            record_hash=record_hash,
            reason=reason,
            timestamp=now,
        )
        self._append_jsonl(paths.chain_file, record.model_dump())

        provenance_rows: list[dict[str, Any]] = []
        for artifact in artifacts:
            row = {
                "event": "artifact_tracked",
                "run_id": run_id,
                "finding_key": finding_key,
                "artifact_type": artifact.artifact_type,
                "artifact_path": artifact.artifact_path,
                "sha256": artifact.sha256,
                "payload_hash": artifact.payload_hash,
                "exists": artifact.exists,
                "provenance": artifact.provenance,
                "record_hash": record_hash,
                "timestamp": now,
            }
            provenance_rows.append(row)
            self._append_jsonl(paths.provenance_file, row)
        return record, provenance_rows

    def finalize_run_evidence(
        self,
        *,
        run_id: str,
        actor: str = "system",
        reason: str = "finalized",
    ) -> dict[str, Any]:
        paths = self._paths(run_id)
        status = self._read_status(run_id)
        if status.get("finalized"):
            payload = {
                "run_id": run_id,
                "finalized": True,
                "finalized_at": status.get("finalized_at"),
                "actor": status.get("actor"),
                "reason": "already_finalized",
            }
            self._append_jsonl(paths.metadata_file, {**payload, "event": "finalize_noop", "timestamp": _utcnow_iso()})
            return payload

        finalized_at = _utcnow_iso()
        status_payload = {
            "run_id": run_id,
            "finalized": True,
            "finalized_at": finalized_at,
            "actor": actor,
            "reason": reason,
        }
        paths.status_file.write_text(json.dumps(status_payload, default=str, indent=2), encoding="utf-8")
        self._append_jsonl(
            paths.metadata_file,
            {
                "event": "finalize",
                "run_id": run_id,
                "finalized": True,
                "finalized_at": finalized_at,
                "actor": actor,
                "reason": reason,
                "timestamp": finalized_at,
            },
        )
        return status_payload

