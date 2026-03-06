from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from apps.backend.src.schemas.evidence import ArtifactMetadata, EvidenceObject


def _coerce_artifact_list(payload: Mapping[str, Any]) -> list[ArtifactMetadata]:
    artifacts_raw = payload.get("artifacts")
    artifacts: list[ArtifactMetadata] = []

    if isinstance(artifacts_raw, list):
        for item in artifacts_raw:
            if not isinstance(item, Mapping):
                continue
            artifacts.append(
                ArtifactMetadata(
                    artifact_path=str(item.get("artifact_path", "")),
                    sha256=str(item.get("sha256", "")),
                    mime_type=str(item.get("mime_type", "application/octet-stream")),
                    description=str(item.get("description", "artifact")),
                )
            )
    elif isinstance(artifacts_raw, Mapping):
        for name, path in artifacts_raw.items():
            artifacts.append(
                ArtifactMetadata(
                    artifact_path=str(path),
                    sha256="",
                    mime_type="application/octet-stream",
                    description=str(name),
                )
            )

    # Legacy single-artifact fields
    if not artifacts and payload.get("path"):
        artifacts.append(
            ArtifactMetadata(
                artifact_path=str(payload.get("path")),
                sha256=str(payload.get("hash") or ""),
                mime_type="application/octet-stream",
                description=str(payload.get("name") or "artifact"),
            )
        )

    return artifacts


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def ensure_evidence_object(payload: Mapping[str, Any]) -> EvidenceObject:
    """
    Normalize legacy and canonical evidence payloads into a canonical EvidenceObject.
    """
    if "evidence" in payload and isinstance(payload["evidence"], Mapping):
        payload = payload["evidence"]

    artifacts = _coerce_artifact_list(payload)
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else {}

    canonical = {
        "evidence_id": str(payload.get("evidence_id") or payload.get("id") or "ev-unknown"),
        "type": str(payload.get("type") or metadata.get("type") or "generic"),
        "tool": str(payload.get("tool") or payload.get("source") or metadata.get("tool") or "unknown"),
        "target": str(payload.get("target") or metadata.get("target") or "unknown"),
        "timestamp": _parse_timestamp(payload.get("timestamp") or payload.get("created_at")),
        "structured_data": (
            payload.get("structured_data")
            if isinstance(payload.get("structured_data"), Mapping)
            else dict(metadata)
        ),
        "confidence_score": float(payload.get("confidence_score") or metadata.get("confidence_score") or 0.0),
        "artifacts": artifacts,
        "scope_status": str(payload.get("scope_status") or metadata.get("scope_status") or "unknown"),
    }
    return EvidenceObject(**canonical)


def normalize_report_evidence(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    """
    Report-facing evidence view with canonical fields and legacy compatibility.
    """
    source = payload or {}
    ev = ensure_evidence_object(source)

    artifacts_map: dict[str, str] = {}
    for idx, art in enumerate(ev.artifacts, start=1):
        key = art.description or f"artifact_{idx}"
        artifacts_map[key] = art.artifact_path

    # Preserve optional legacy report fields when present.
    repro = source.get("repro") if isinstance(source, Mapping) else ""
    screenshots = source.get("screenshots") if isinstance(source.get("screenshots"), list) else []
    network_captures = source.get("network_captures") if isinstance(source.get("network_captures"), list) else []

    return {
        "repro": repro or "",
        "artifacts": artifacts_map,
        "artifacts_list": [a.model_dump(mode="json") for a in ev.artifacts],
        "screenshots": screenshots,
        "network_captures": network_captures,
        "poc_code": source.get("poc_code") if isinstance(source, Mapping) else None,
        "evidence_object": ev.model_dump(mode="json"),
    }
