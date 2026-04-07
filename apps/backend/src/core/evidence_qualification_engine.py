from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

from .audit_logger import write_audit_record
from .scope_guardrails import ScopePolicy, evaluate_target_scope, load_scope_policy


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _normalize_target(value: Any) -> str:
    raw = _normalize_text(value).lower()
    if not raw:
        return ""
    if "://" in raw:
        parsed = urlparse(raw)
        raw = parsed.hostname or parsed.path or raw
    if ":" in raw:
        raw = raw.split(":", 1)[0]
    return raw.strip(".")


def _normalize_endpoint_pattern(value: Any) -> str:
    raw = _normalize_text(value).lower()
    if not raw:
        return ""
    if "?" in raw:
        raw = raw.split("?", 1)[0]
    raw = re.sub(r"\b[0-9a-f]{8,}\b", "{id}", raw)
    raw = re.sub(r"\b\d+\b", "{n}", raw)
    raw = re.sub(r"/+", "/", raw)
    return raw.rstrip("/")


def _artifact_root() -> Path:
    configured = os.getenv("K1_EVIDENCE_QUALIFICATION_ARTIFACT_DIR")
    if configured:
        return Path(configured).resolve()
    artifacts_root = os.getenv("K1_ARTIFACTS_ROOT")
    if artifacts_root:
        return (Path(artifacts_root).expanduser().resolve() / "evidence_qualification")
    return Path("artifacts/evidence_qualification").resolve()


def _index_path() -> Path:
    configured = os.getenv("K1_EVIDENCE_QUALIFICATION_INDEX_PATH")
    if configured:
        return Path(configured).resolve()
    return _artifact_root() / "duplicate_index.json"


def _mission_log_path(mission_id: str) -> Path:
    safe_mission = _normalize_text(mission_id) or "unknown-mission"
    return _artifact_root() / safe_mission / "mission_log.jsonl"


def _events_log_path() -> Path:
    return _artifact_root() / "events.jsonl"


@dataclass(slots=True)
class EvidenceQualificationResult:
    qualification_id: str
    mission_id: str
    stage_id: str
    finding_key: str
    candidate_key: str
    reproducibility_score: float
    exploit_stability_score: float
    scope_validity: bool
    evidence_completeness_score: float
    duplicate_risk_score: float
    evidence_quality_score: float
    submission_candidate: bool
    rejection_reason: str | None
    guardrail_outcomes: dict[str, Any]
    additional_data_needed: list[str]
    created_at: str
    artifact_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["reproducibility_score"] = round(_clamp(self.reproducibility_score), 4)
        payload["exploit_stability_score"] = round(_clamp(self.exploit_stability_score), 4)
        payload["evidence_completeness_score"] = round(_clamp(self.evidence_completeness_score), 4)
        payload["duplicate_risk_score"] = round(_clamp(self.duplicate_risk_score), 4)
        payload["evidence_quality_score"] = round(_clamp(self.evidence_quality_score), 4)
        return payload


class EvidenceQualificationEngine:
    """Deterministic evidence qualification gate for report/HiL eligibility."""

    _lock = threading.Lock()

    def __init__(self, *, scope_policy: ScopePolicy | None = None) -> None:
        self._scope_policy = scope_policy or load_scope_policy()

    def qualify(
        self,
        finding: Mapping[str, Any],
        *,
        exploit_results: list[Mapping[str, Any]] | None = None,
        request_response_signatures: list[Any] | None = None,
        scope_metadata: Mapping[str, Any] | None = None,
        mission_id: str | None = None,
        stage_id: str | None = None,
        report_id: str | None = None,
        replay_callable: Callable[[], Mapping[str, Any]] | None = None,
        replay_attempts: int = 3,
        persist: bool = True,
        update_duplicate_history: bool = True,
    ) -> EvidenceQualificationResult:
        mission = _normalize_text(mission_id)
        stage = _normalize_text(stage_id)

        target = _normalize_target(
            finding.get("target")
            or finding.get("host")
            or finding.get("domain")
            or finding.get("url")
            or (scope_metadata or {}).get("target")
        )
        vuln_type = _normalize_text(finding.get("vuln_type") or finding.get("vulnerability_type") or finding.get("type")).lower() or "unknown"
        endpoint_pattern = _normalize_endpoint_pattern(
            finding.get("endpoint")
            or finding.get("path")
            or finding.get("url")
            or (scope_metadata or {}).get("endpoint")
        )
        parameter = _normalize_text(
            finding.get("parameter")
            or finding.get("parameter_name")
            or finding.get("input_vector")
        ).lower()
        payload_sig = _normalize_text(
            finding.get("payload")
            or finding.get("key_payload_signature")
            or finding.get("probe_payload")
            or finding.get("signature")
        )

        candidate_key = "|".join([vuln_type, target, endpoint_pattern, parameter])
        finding_key = "|".join(
            [
                _normalize_text(report_id),
                _normalize_text(finding.get("finding_id") or finding.get("id")),
                candidate_key,
                payload_sig,
            ]
        ).strip("|")
        if not finding_key:
            finding_key = candidate_key or f"finding:{sha256(json.dumps(dict(finding), sort_keys=True, default=str).encode('utf-8')).hexdigest()[:12]}"

        inputs = list(exploit_results or [])
        if replay_callable is not None:
            needed = max(0, min(max(2, replay_attempts), 3) - len(inputs))
            for _ in range(needed):
                try:
                    replay = replay_callable()
                except Exception:
                    break
                if isinstance(replay, Mapping):
                    inputs.append(dict(replay))

        signature_inputs = self._collect_signatures(inputs, request_response_signatures)
        reproducibility_score, reproducibility_detail = self._score_reproducibility(signature_inputs)
        stability_score, stability_detail = self._score_stability(inputs, signature_inputs)
        scope_valid, scope_detail = self._score_scope(target, scope_metadata)
        completeness_score, completeness_missing = self._score_evidence_completeness(finding)
        duplicate_risk, duplicate_detail = self._score_duplicate_risk(
            candidate_key=candidate_key,
            finding=finding,
            update_history=update_duplicate_history,
        )

        quality_score = _clamp(
            (reproducibility_score * 0.24)
            + (stability_score * 0.20)
            + (completeness_score * 0.24)
            + ((1.0 - duplicate_risk) * 0.14)
            + ((1.0 if scope_valid else 0.0) * 0.18)
        )

        guardrail_outcomes = {
            "reproducibility": reproducibility_detail,
            "stability": stability_detail,
            "scope": scope_detail,
            "duplicate": duplicate_detail,
            "minimum_signature_samples": len(signature_inputs) >= 2,
            "quality_threshold_met": quality_score >= 0.75,
        }

        rejection_reason: str | None = None
        if not scope_valid:
            rejection_reason = "out_of_scope"
        elif stability_score < 0.60:
            rejection_reason = "unstable_exploit_behavior"
        elif reproducibility_score < 0.60:
            rejection_reason = "insufficient_reproducibility"
        elif completeness_score < 0.55:
            rejection_reason = "insufficient_evidence_completeness"
        elif duplicate_risk >= 0.80:
            rejection_reason = "high_duplicate_risk"
        elif quality_score < 0.75:
            rejection_reason = "evidence_quality_below_threshold"

        submission_candidate = rejection_reason is None

        additional_needed: list[str] = []
        if len(signature_inputs) < 2:
            additional_needed.append("collect_additional_repro_runs")
        if completeness_missing:
            additional_needed.extend([f"missing_{item}" for item in completeness_missing])
        if duplicate_risk >= 0.6:
            additional_needed.append("collect_novelty_proof")
        if not scope_valid:
            additional_needed.append("scope_authorization")

        qualification_id = f"eq-{sha256(f'{finding_key}:{_utcnow_iso()}'.encode('utf-8')).hexdigest()[:16]}"
        result = EvidenceQualificationResult(
            qualification_id=qualification_id,
            mission_id=mission,
            stage_id=stage,
            finding_key=finding_key,
            candidate_key=candidate_key,
            reproducibility_score=reproducibility_score,
            exploit_stability_score=stability_score,
            scope_validity=scope_valid,
            evidence_completeness_score=completeness_score,
            duplicate_risk_score=duplicate_risk,
            evidence_quality_score=quality_score,
            submission_candidate=submission_candidate,
            rejection_reason=rejection_reason,
            guardrail_outcomes=guardrail_outcomes,
            additional_data_needed=sorted(set(additional_needed)),
            created_at=_utcnow_iso(),
            artifact_path=None,
        )

        self._emit_governance_event("evidence_qualification_started", result)
        if persist:
            artifact_path = self._persist_result(result, finding=finding)
            result.artifact_path = artifact_path
        if submission_candidate:
            self._emit_governance_event("evidence_qualification_passed", result)
        else:
            self._emit_governance_event("evidence_qualification_rejected", result)

        return result

    def _collect_signatures(
        self,
        exploit_results: list[Mapping[str, Any]],
        request_response_signatures: list[Any] | None,
    ) -> list[str]:
        signatures: list[str] = []

        for row in exploit_results:
            signatures.append(self._signature_from_mapping(row))

        for raw in list(request_response_signatures or []):
            if isinstance(raw, Mapping):
                signatures.append(self._signature_from_mapping(raw))
            else:
                text = _normalize_text(raw)
                if text:
                    signatures.append(text)

        compact = [sig for sig in signatures if sig]
        return compact

    @staticmethod
    def _signature_from_mapping(row: Mapping[str, Any]) -> str:
        request_sig = _normalize_text(
            row.get("request_signature")
            or row.get("request")
            or row.get("http_request")
            or row.get("request_hash")
        )
        response_sig = _normalize_text(
            row.get("response_signature")
            or row.get("response")
            or row.get("http_response")
            or row.get("response_hash")
        )
        status = _normalize_text(row.get("status") or row.get("status_code") or row.get("http_status"))
        body = _normalize_text(row.get("body") or row.get("response_body"))
        if body and len(body) > 512:
            body = body[:512]
        raw = "|".join(part for part in [request_sig, response_sig, status, body] if part)
        if not raw:
            raw = json.dumps(dict(row), sort_keys=True, default=str)
        return sha256(raw.encode("utf-8", errors="replace")).hexdigest()[:24]

    def _score_reproducibility(self, signatures: list[str]) -> tuple[float, dict[str, Any]]:
        count = len(signatures)
        if count == 0:
            return 0.0, {"sample_count": 0, "match_ratio": 0.0, "reason": "no_signatures"}
        if count == 1:
            return 0.35, {"sample_count": 1, "match_ratio": 0.0, "reason": "single_signature_only"}

        first = signatures[0]
        stable_count = sum(1 for sig in signatures[1:] if sig == first) + 1
        ratio = stable_count / max(1, count)
        score = _clamp((ratio * 0.85) + (min(count, 3) / 3.0 * 0.15))
        return score, {
            "sample_count": count,
            "stable_count": stable_count,
            "match_ratio": round(ratio, 4),
            "reason": "stable_signatures" if ratio >= 0.66 else "signature_drift_detected",
        }

    def _score_stability(
        self,
        exploit_results: list[Mapping[str, Any]],
        signatures: list[str],
    ) -> tuple[float, dict[str, Any]]:
        if not exploit_results:
            if len(signatures) >= 2:
                return 0.65, {
                    "consistency": "signature_only",
                    "success_ratio": None,
                    "reason": "using_signature_consistency",
                }
            return 0.35, {
                "consistency": "unknown",
                "success_ratio": None,
                "reason": "insufficient_runtime_signals",
            }

        statuses: list[bool] = []
        for row in exploit_results:
            status_raw = str(row.get("status") or row.get("result") or "").strip().lower()
            if status_raw in {"ok", "success", "completed", "pass", "validated"}:
                statuses.append(True)
            elif status_raw in {"fail", "failed", "error", "timeout", "blocked"}:
                statuses.append(False)
            else:
                statuses.append(bool(row.get("success") or row.get("validated")))

        success_ratio = sum(1 for status in statuses if status) / max(1, len(statuses))
        signature_penalty = 0.0
        if len(signatures) >= 2 and len(set(signatures)) > 1:
            signature_penalty = 0.2
        score = _clamp(success_ratio - signature_penalty)
        return score, {
            "attempts": len(statuses),
            "success_ratio": round(success_ratio, 4),
            "signature_penalty": signature_penalty,
            "reason": "stable" if score >= 0.6 else "inconsistent_behavior",
        }

    def _score_scope(
        self,
        target: str,
        scope_metadata: Mapping[str, Any] | None,
    ) -> tuple[bool, dict[str, Any]]:
        meta = dict(scope_metadata or {})

        if "scope_validity" in meta:
            valid = bool(meta.get("scope_validity"))
            return valid, {"source": "scope_metadata.scope_validity", "allowed": valid}
        if "in_scope" in meta:
            valid = bool(meta.get("in_scope"))
            return valid, {"source": "scope_metadata.in_scope", "allowed": valid}
        if "allowed" in meta:
            valid = bool(meta.get("allowed"))
            return valid, {"source": "scope_metadata.allowed", "allowed": valid}

        decision = evaluate_target_scope(target, self._scope_policy)
        return bool(decision.allowed), {
            "source": "scope_guardrails",
            "allowed": bool(decision.allowed),
            "reason": decision.reason,
            "matched_rule": decision.matched_rule,
            "target": target,
        }

    @staticmethod
    def _score_evidence_completeness(finding: Mapping[str, Any]) -> tuple[float, list[str]]:
        required = {
            "vulnerability_type": bool(_normalize_text(finding.get("vuln_type") or finding.get("vulnerability_type") or finding.get("type"))),
            "target": bool(_normalize_text(finding.get("target") or finding.get("host") or finding.get("domain") or finding.get("url"))),
            "summary": bool(_normalize_text(finding.get("summary") or finding.get("description") or finding.get("title"))),
            "evidence": bool(
                finding.get("validation_evidence")
                or finding.get("evidence")
                or finding.get("http_requests")
                or finding.get("http_responses")
            ),
            "severity": bool(_normalize_text(finding.get("severity") or finding.get("severity_hint"))),
            "confidence": finding.get("confidence") is not None or finding.get("confidence_score") is not None,
        }
        optional_boost = {
            "endpoint": bool(_normalize_text(finding.get("endpoint") or finding.get("path") or finding.get("url"))),
            "parameter": bool(_normalize_text(finding.get("parameter") or finding.get("parameter_name"))),
            "reproduction_steps": bool(finding.get("reproduction_steps") or finding.get("steps_to_reproduce")),
        }

        required_ratio = sum(1 for value in required.values() if value) / len(required)
        boost_ratio = sum(1 for value in optional_boost.values() if value) / len(optional_boost)
        score = _clamp((required_ratio * 0.82) + (boost_ratio * 0.18))
        missing = [name for name, present in required.items() if not present]
        return score, missing

    def _score_duplicate_risk(
        self,
        *,
        candidate_key: str,
        finding: Mapping[str, Any],
        update_history: bool,
    ) -> tuple[float, dict[str, Any]]:
        history_count = 0
        with self._lock:
            index_path = _index_path()
            index_path.parent.mkdir(parents=True, exist_ok=True)
            payload: dict[str, Any]
            if index_path.exists():
                try:
                    loaded = json.loads(index_path.read_text(encoding="utf-8"))
                    payload = loaded if isinstance(loaded, dict) else {"seen": {}}
                except Exception:
                    payload = {"seen": {}}
            else:
                payload = {"seen": {}}

            seen = payload.get("seen")
            if not isinstance(seen, dict):
                seen = {}
                payload["seen"] = seen

            history_entry = seen.get(candidate_key, {}) if candidate_key else {}
            if isinstance(history_entry, dict):
                history_count = int(history_entry.get("count", 0) or 0)

            if update_history and candidate_key:
                seen[candidate_key] = {
                    "count": history_count + 1,
                    "last_seen": _utcnow_iso(),
                    "vulnerability_type": _normalize_text(
                        finding.get("vuln_type") or finding.get("vulnerability_type") or finding.get("type")
                    ).lower(),
                    "target": _normalize_target(finding.get("target") or finding.get("host") or finding.get("url")),
                }
                index_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

        explicit = finding.get("duplicate_risk")
        explicit_score = _clamp(_safe_float(explicit, 0.0)) if explicit is not None else None

        density_score = _clamp(history_count / 6.0)
        heuristic = _clamp((density_score * 0.8) + (0.2 if history_count > 0 else 0.0))
        if explicit_score is None:
            score = heuristic
            source = "local_history"
        else:
            score = _clamp((explicit_score * 0.7) + (heuristic * 0.3))
            source = "explicit_plus_history"

        return score, {
            "source": source,
            "history_count": history_count,
            "candidate_key": candidate_key,
            "explicit_score": explicit_score,
            "computed_score": round(score, 4),
        }

    def _persist_result(self, result: EvidenceQualificationResult, *, finding: Mapping[str, Any]) -> str:
        root = _artifact_root()
        mission_dir = root / (_normalize_text(result.mission_id) or "unknown-mission")
        mission_dir.mkdir(parents=True, exist_ok=True)

        file_name = f"{result.qualification_id}.json"
        artifact_path = mission_dir / file_name
        payload = result.to_dict()
        payload["finding"] = dict(finding)
        artifact_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

        mission_log = _mission_log_path(result.mission_id)
        mission_log.parent.mkdir(parents=True, exist_ok=True)
        with mission_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")

        events_log = _events_log_path()
        events_log.parent.mkdir(parents=True, exist_ok=True)
        with events_log.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "event_type": "evidence_qualification_artifact_written",
                        "qualification_id": result.qualification_id,
                        "mission_id": result.mission_id,
                        "stage_id": result.stage_id,
                        "artifact_path": str(artifact_path),
                        "timestamp": _utcnow_iso(),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        return str(artifact_path)

    @staticmethod
    def _emit_governance_event(event_type: str, result: EvidenceQualificationResult) -> None:
        write_audit_record(
            event_type,
            mission_id=result.mission_id,
            decision="passed" if result.submission_candidate else "rejected",
            reason=result.rejection_reason or "qualified",
            detail={
                "qualification_id": result.qualification_id,
                "finding_key": result.finding_key,
                "candidate_key": result.candidate_key,
                "evidence_quality_score": round(result.evidence_quality_score, 4),
                "reproducibility_score": round(result.reproducibility_score, 4),
                "exploit_stability_score": round(result.exploit_stability_score, 4),
                "scope_validity": result.scope_validity,
                "duplicate_risk_score": round(result.duplicate_risk_score, 4),
                "stage_id": result.stage_id,
            },
        )


_ENGINE: EvidenceQualificationEngine | None = None
_ENGINE_LOCK = threading.Lock()


def get_evidence_qualification_engine() -> EvidenceQualificationEngine:
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            _ENGINE = EvidenceQualificationEngine()
        return _ENGINE


def qualify_evidence(
    finding: Mapping[str, Any],
    *,
    exploit_results: list[Mapping[str, Any]] | None = None,
    request_response_signatures: list[Any] | None = None,
    scope_metadata: Mapping[str, Any] | None = None,
    mission_id: str | None = None,
    stage_id: str | None = None,
    report_id: str | None = None,
    replay_callable: Callable[[], Mapping[str, Any]] | None = None,
    replay_attempts: int = 3,
    persist: bool = True,
    update_duplicate_history: bool = True,
) -> EvidenceQualificationResult:
    return get_evidence_qualification_engine().qualify(
        finding,
        exploit_results=exploit_results,
        request_response_signatures=request_response_signatures,
        scope_metadata=scope_metadata,
        mission_id=mission_id,
        stage_id=stage_id,
        report_id=report_id,
        replay_callable=replay_callable,
        replay_attempts=replay_attempts,
        persist=persist,
        update_duplicate_history=update_duplicate_history,
    )
