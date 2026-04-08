from __future__ import annotations

import json
import os
import re
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from .audit_logger import write_audit_record


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def _clamp(value: float, minimum: float = 0.0, maximum: float = 1.0) -> float:
    return max(minimum, min(maximum, float(value)))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_vuln_family(value: Any) -> str:
    raw = _normalize_text(value).lower().replace("-", "_").replace(" ", "_")
    if not raw:
        return "unknown"
    if "sql" in raw and "injection" in raw:
        return "sql_injection"
    if "xss" in raw:
        return "xss"
    if "idor" in raw:
        return "idor"
    if "ssrf" in raw:
        return "ssrf"
    if "rce" in raw:
        return "rce"
    if "csrf" in raw:
        return "csrf"
    if "open_redirect" in raw:
        return "open_redirect"
    if "xxe" in raw:
        return "xxe"
    if "injection" in raw:
        return "injection"
    return raw


def _normalize_endpoint_pattern(value: Any) -> str:
    raw = _normalize_text(value).lower()
    if not raw:
        return "/"
    if "://" in raw:
        parsed = urlparse(raw)
        raw = parsed.path or "/"
    if "?" in raw:
        raw = raw.split("?", 1)[0]
    raw = re.sub(r"\b[0-9a-f]{8,}\b", "{id}", raw)
    raw = re.sub(r"\b\d+\b", "{n}", raw)
    raw = re.sub(r"/+", "/", raw)
    return raw.rstrip("/") or "/"


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


def _to_set(value: Any) -> set[str]:
    if isinstance(value, list):
        return {_normalize_text(item).lower() for item in value if _normalize_text(item)}
    if isinstance(value, str):
        return {token for token in re.split(r"[^a-z0-9_]+", value.lower()) if token and len(token) >= 2}
    return set()


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    inter = len(left & right)
    union = len(left | right)
    if union == 0:
        return 0.0
    return inter / union


def _artifact_root() -> Path:
    configured = os.getenv("K1_NOVELTY_DEDUPE_ARTIFACT_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    artifacts_root = os.getenv("K1_ARTIFACTS_ROOT")
    if artifacts_root:
        return (Path(artifacts_root).expanduser().resolve() / "novelty_dedupe")
    return Path("artifacts/novelty_dedupe").resolve()


def _state_path() -> Path:
    configured = os.getenv("K1_NOVELTY_DEDUPE_STATE_PATH")
    if configured:
        return Path(configured).expanduser().resolve()
    return _artifact_root() / "state.json"


def _events_log_path() -> Path:
    return _artifact_root() / "events.jsonl"


def _mission_log_path(mission_id: str) -> Path:
    mission = _normalize_text(mission_id) or "unknown-mission"
    return _artifact_root() / mission / "mission_log.jsonl"


@dataclass(slots=True)
class NoveltyDedupeResult:
    decision_id: str
    mission_id: str
    stage_id: str
    finding_key: str
    duplicate_likelihood_score: float
    duplicate_cluster_key: str
    suppression_recommendation: str
    novelty_score: float
    novelty_priority: str
    priority_reason: str
    novelty_reason: str
    impact_differentiation_score: float
    created_at: str
    artifact_path: str | None = None
    debug_factors: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["duplicate_likelihood_score"] = round(_clamp(self.duplicate_likelihood_score), 4)
        payload["novelty_score"] = round(_clamp(self.novelty_score), 4)
        payload["impact_differentiation_score"] = round(_clamp(self.impact_differentiation_score), 4)
        return payload


class NoveltyDedupeEngine:
    _state_lock = threading.Lock()

    def _load_state(self) -> dict[str, Any]:
        path = _state_path()
        if not path.exists():
            return {
                "clusters": {},
                "family_endpoint_stats": {},
                "finding_index": {},
                "updated_at": _utcnow_iso(),
            }
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("invalid_state")
            payload.setdefault("clusters", {})
            payload.setdefault("family_endpoint_stats", {})
            payload.setdefault("finding_index", {})
            payload.setdefault("updated_at", _utcnow_iso())
            return payload
        except Exception:
            return {
                "clusters": {},
                "family_endpoint_stats": {},
                "finding_index": {},
                "updated_at": _utcnow_iso(),
            }

    def _save_state(self, payload: dict[str, Any]) -> None:
        path = _state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload["updated_at"] = _utcnow_iso()
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def evaluate(
        self,
        finding: Mapping[str, Any],
        *,
        vulnerability_intelligence: Mapping[str, Any] | None = None,
        evidence_qualification: Mapping[str, Any] | None = None,
        impact_validation: Mapping[str, Any] | None = None,
        submission_decision: Mapping[str, Any] | None = None,
        mission_id: str | None = None,
        stage_id: str | None = None,
        report_id: str | None = None,
        persist: bool = True,
        update_history: bool = True,
    ) -> NoveltyDedupeResult:
        mission = _normalize_text(mission_id)
        stage = _normalize_text(stage_id) or "novelty_dedupe"

        vuln_family = _normalize_vuln_family(
            finding.get("vuln_family")
            or finding.get("vulnerability_type")
            or finding.get("vuln_type")
            or finding.get("type")
        )
        target = _normalize_target(finding.get("target") or finding.get("host") or finding.get("domain") or finding.get("url"))
        endpoint_pattern = _normalize_endpoint_pattern(finding.get("endpoint") or finding.get("path") or finding.get("url"))
        params = {
            _normalize_text(item).lower()
            for item in [
                finding.get("parameter"),
                finding.get("parameter_name"),
                finding.get("input_vector"),
            ]
            if _normalize_text(item)
        }
        if isinstance(finding.get("affected_parameters"), list):
            params |= {_normalize_text(item).lower() for item in finding.get("affected_parameters") if _normalize_text(item)}

        vi = dict(vulnerability_intelligence or {})
        matched_ids = _to_set(vi.get("matched_intelligence_ids"))
        matched_sources = _to_set(vi.get("matched_sources"))
        behavior = _to_set(finding.get("behavior_signatures")) | _to_set(vi.get("reference_sources")) | _to_set(finding.get("summary"))
        impact_score = _safe_float((impact_validation or {}).get("impact_score"), 0.0)

        param_signature = "|".join(sorted(params)) or "no_params"
        behavior_signature = "|".join(sorted(behavior)) or "no_behavior"
        intel_signature = "|".join(sorted(matched_ids or matched_sources)) or "no_intel"
        cluster_seed = f"{vuln_family}|{endpoint_pattern}|{param_signature}|{behavior_signature}|{intel_signature}"
        duplicate_cluster_key = f"cluster_{sha256(cluster_seed.encode('utf-8')).hexdigest()[:16]}"
        family_endpoint_key = f"{vuln_family}|{endpoint_pattern}"

        finding_key = "|".join(
            [
                _normalize_text(report_id),
                _normalize_text(finding.get("finding_id") or finding.get("id")),
                vuln_family,
                target,
                endpoint_pattern,
            ]
        ).strip("|")
        if not finding_key:
            finding_key = f"finding:{sha256(json.dumps(dict(finding), sort_keys=True, default=str).encode('utf-8')).hexdigest()[:12]}"

        write_audit_record(
            "novelty_dedupe_started",
            mission_id=mission,
            decision="started",
            reason="novelty_dedupe_requested",
            detail={"stage_id": stage, "vuln_family": vuln_family, "endpoint_pattern": endpoint_pattern},
        )

        with self._state_lock:
            state = self._load_state()
            clusters = state.get("clusters") if isinstance(state.get("clusters"), dict) else {}
            family_stats = (
                state.get("family_endpoint_stats")
                if isinstance(state.get("family_endpoint_stats"), dict)
                else {}
            )
            cluster = clusters.get(duplicate_cluster_key) if isinstance(clusters.get(duplicate_cluster_key), dict) else {}
            family_stat = family_stats.get(family_endpoint_key) if isinstance(family_stats.get(family_endpoint_key), dict) else {}

            cluster_count = int(cluster.get("count", 0) or 0)
            family_count = int(family_stat.get("count", 0) or 0)
            prior_param_sets = [_to_set(row) for row in family_stat.get("param_sets", []) if isinstance(row, list)]
            prior_behavior_sets = [_to_set(row) for row in family_stat.get("behavior_sets", []) if isinstance(row, list)]
            prior_intel_sets = [_to_set(row) for row in family_stat.get("intel_sets", []) if isinstance(row, list)]

            param_overlap = max((_jaccard(params, row) for row in prior_param_sets), default=0.0)
            behavior_overlap = max((_jaccard(behavior, row) for row in prior_behavior_sets), default=0.0)
            intel_overlap = max((_jaccard(matched_ids | matched_sources, row) for row in prior_intel_sets), default=0.0)

            known_pattern_overlap = _clamp(
                (_safe_float(vi.get("known_pattern_match_score"), 0.0) * 0.6)
                + (_safe_float(vi.get("exploit_similarity_score"), 0.0) * 0.4)
            )
            history_density = _clamp((min(cluster_count, 5) / 5.0 * 0.6) + (min(family_count, 8) / 8.0 * 0.4))
            duplicate_likelihood_score = _clamp(
                (history_density * 0.35)
                + (param_overlap * 0.2)
                + (behavior_overlap * 0.15)
                + (intel_overlap * 0.10)
                + (known_pattern_overlap * 0.20)
            )

            endpoint_rarity = _clamp(1.0 - min(family_count, 10) / 10.0)
            param_rarity = _clamp(1.0 - param_overlap)
            behavior_rarity = _clamp(1.0 - behavior_overlap)
            known_overlap_rarity = _clamp(1.0 - known_pattern_overlap)
            novelty_score = _clamp(
                (endpoint_rarity * 0.28)
                + (param_rarity * 0.24)
                + (behavior_rarity * 0.2)
                + (known_overlap_rarity * 0.28)
            )

            cluster_avg_impact = _safe_float(cluster.get("avg_impact_score"), impact_score)
            impact_differentiation_score = _clamp(abs(impact_score - cluster_avg_impact))

            if duplicate_likelihood_score >= 0.78 and novelty_score < 0.42 and impact_differentiation_score < 0.15:
                suppression_recommendation = "suppress_from_default_hil_view"
            elif duplicate_likelihood_score >= 0.55 and novelty_score < 0.6 and impact_differentiation_score < 0.25:
                suppression_recommendation = "deprioritize"
            else:
                suppression_recommendation = "none"

            if novelty_score >= 0.72:
                novelty_priority = "high"
            elif novelty_score >= 0.45:
                novelty_priority = "medium"
            else:
                novelty_priority = "low"

            novelty_reason = (
                "high rarity across endpoint, parameters, and behavior with low known-pattern overlap"
                if novelty_priority == "high"
                else (
                    "mixed novelty with partial overlap to known and recent findings"
                    if novelty_priority == "medium"
                    else "low novelty due to high overlap with recent or known finding patterns"
                )
            )

            if suppression_recommendation == "suppress_from_default_hil_view":
                priority_reason = "high duplicate overlap, low novelty, and low impact differentiation"
            elif suppression_recommendation == "deprioritize":
                priority_reason = "moderate overlap with limited novelty differentiation"
            elif novelty_priority == "high":
                priority_reason = "high novelty and low duplicate likelihood"
            else:
                priority_reason = "retain for review without suppression"

            decision_id = f"nd-{sha256(f'{finding_key}:{_utcnow_iso()}'.encode('utf-8')).hexdigest()[:16]}"
            result = NoveltyDedupeResult(
                decision_id=decision_id,
                mission_id=mission,
                stage_id=stage,
                finding_key=finding_key,
                duplicate_likelihood_score=duplicate_likelihood_score,
                duplicate_cluster_key=duplicate_cluster_key,
                suppression_recommendation=suppression_recommendation,
                novelty_score=novelty_score,
                novelty_priority=novelty_priority,
                priority_reason=priority_reason,
                novelty_reason=novelty_reason,
                impact_differentiation_score=impact_differentiation_score,
                created_at=_utcnow_iso(),
                artifact_path=None,
                debug_factors={
                    "cluster_count": cluster_count,
                    "family_count": family_count,
                    "param_overlap": round(param_overlap, 4),
                    "behavior_overlap": round(behavior_overlap, 4),
                    "intel_overlap": round(intel_overlap, 4),
                    "known_pattern_overlap": round(known_pattern_overlap, 4),
                    "history_density": round(history_density, 4),
                },
            )

            if update_history:
                clusters[duplicate_cluster_key] = {
                    "count": cluster_count + 1,
                    "last_seen": _utcnow_iso(),
                    "vuln_family": vuln_family,
                    "endpoint_pattern": endpoint_pattern,
                    "avg_impact_score": round(
                        (
                            (cluster_avg_impact * max(cluster_count, 0))
                            + impact_score
                        )
                        / max(1, cluster_count + 1),
                        4,
                    ),
                }
                family_stats[family_endpoint_key] = {
                    "count": family_count + 1,
                    "last_seen": _utcnow_iso(),
                    "param_sets": (family_stat.get("param_sets") or [])[-24:] + [sorted(params)],
                    "behavior_sets": (family_stat.get("behavior_sets") or [])[-24:] + [sorted(behavior)],
                    "intel_sets": (family_stat.get("intel_sets") or [])[-24:] + [sorted(matched_ids | matched_sources)],
                }
                finding_index = state.get("finding_index")
                if not isinstance(finding_index, dict):
                    finding_index = {}
                    state["finding_index"] = finding_index
                finding_index[finding_key] = {
                    "duplicate_cluster_key": duplicate_cluster_key,
                    "duplicate_likelihood_score": round(duplicate_likelihood_score, 4),
                    "novelty_score": round(novelty_score, 4),
                    "suppression_recommendation": suppression_recommendation,
                    "updated_at": _utcnow_iso(),
                }

            state["clusters"] = clusters
            state["family_endpoint_stats"] = family_stats

            if persist:
                artifact_path = self._persist_result(result, finding=finding)
                result.artifact_path = artifact_path
            self._save_state(state)

        write_audit_record(
            "novelty_dedupe_completed",
            mission_id=mission,
            decision="completed",
            reason=priority_reason,
            detail={
                "stage_id": stage,
                "duplicate_cluster_key": result.duplicate_cluster_key,
                "duplicate_likelihood_score": round(result.duplicate_likelihood_score, 4),
                "novelty_score": round(result.novelty_score, 4),
                "suppression_recommendation": result.suppression_recommendation,
            },
        )
        if result.suppression_recommendation == "deprioritize":
            write_audit_record(
                "finding_deprioritized",
                mission_id=mission,
                decision="deprioritized",
                reason=result.priority_reason,
                detail={
                    "duplicate_cluster_key": result.duplicate_cluster_key,
                    "duplicate_likelihood_score": round(result.duplicate_likelihood_score, 4),
                    "novelty_score": round(result.novelty_score, 4),
                },
            )
        if result.suppression_recommendation == "suppress_from_default_hil_view":
            write_audit_record(
                "finding_suppressed_from_default_hil_view",
                mission_id=mission,
                decision="suppressed",
                reason=result.priority_reason,
                detail={
                    "duplicate_cluster_key": result.duplicate_cluster_key,
                    "duplicate_likelihood_score": round(result.duplicate_likelihood_score, 4),
                    "novelty_score": round(result.novelty_score, 4),
                },
            )
        return result

    def _persist_result(self, result: NoveltyDedupeResult, *, finding: Mapping[str, Any]) -> str:
        root = _artifact_root()
        mission = _normalize_text(result.mission_id) or "unknown-mission"
        mission_dir = root / mission
        mission_dir.mkdir(parents=True, exist_ok=True)

        artifact_path = mission_dir / f"{result.decision_id}.json"
        payload = result.to_dict()
        payload["finding"] = dict(finding)
        artifact_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

        mission_log = _mission_log_path(result.mission_id)
        mission_log.parent.mkdir(parents=True, exist_ok=True)
        with mission_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")

        events_path = _events_log_path()
        events_path.parent.mkdir(parents=True, exist_ok=True)
        with events_path.open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "event_type": "novelty_dedupe_artifact_written",
                        "decision_id": result.decision_id,
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


_ENGINE: NoveltyDedupeEngine | None = None
_ENGINE_LOCK = threading.Lock()


def get_novelty_dedupe_engine() -> NoveltyDedupeEngine:
    global _ENGINE
    with _ENGINE_LOCK:
        if _ENGINE is None:
            _ENGINE = NoveltyDedupeEngine()
        return _ENGINE


def evaluate_novelty_dedupe(
    finding: Mapping[str, Any],
    *,
    vulnerability_intelligence: Mapping[str, Any] | None = None,
    evidence_qualification: Mapping[str, Any] | None = None,
    impact_validation: Mapping[str, Any] | None = None,
    submission_decision: Mapping[str, Any] | None = None,
    mission_id: str | None = None,
    stage_id: str | None = None,
    report_id: str | None = None,
    persist: bool = True,
    update_history: bool = True,
) -> NoveltyDedupeResult:
    return get_novelty_dedupe_engine().evaluate(
        finding,
        vulnerability_intelligence=vulnerability_intelligence,
        evidence_qualification=evidence_qualification,
        impact_validation=impact_validation,
        submission_decision=submission_decision,
        mission_id=mission_id,
        stage_id=stage_id,
        report_id=report_id,
        persist=persist,
        update_history=update_history,
    )
