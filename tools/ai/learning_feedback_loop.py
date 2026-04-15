from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from tools.ai.pattern_recognition_engine import PatternRecognitionEngine


@dataclass(slots=True)
class OutcomeRecord:
    finding_id: str
    vulnerability_type: str
    estimated_severity_score: float
    estimated_payout_usd: int
    actual_payout_usd: int
    platform_decision: str
    analyst_feedback: str
    pattern_names: list[str]
    timestamp: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "vulnerability_type": self.vulnerability_type,
            "estimated_severity_score": self.estimated_severity_score,
            "estimated_payout_usd": self.estimated_payout_usd,
            "actual_payout_usd": self.actual_payout_usd,
            "platform_decision": self.platform_decision,
            "analyst_feedback": self.analyst_feedback,
            "pattern_names": self.pattern_names,
            "timestamp": self.timestamp,
        }


class LearningFeedbackLoop:
    """
    Detection intelligence learning loop.

    Tracks outcome data and computes correction factors for payout/severity
    guidance and pattern confidence calibration.
    """

    def __init__(
        self,
        *,
        db_path: str | Path = "tools/ai/data/learning_feedback_db.yaml",
        pattern_engine: PatternRecognitionEngine | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.pattern_engine = pattern_engine or PatternRecognitionEngine()
        self._db = self._load_db()

    def _load_db(self) -> dict[str, Any]:
        if not self.db_path.exists():
            return {
                "version": "1.0",
                "created_at": datetime.now(UTC).isoformat(),
                "records": [],
                "vuln_correction_factors": {},
                "pattern_confidence_overrides": {},
            }
        payload = yaml.safe_load(self.db_path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid learning DB payload: {self.db_path}")
        payload.setdefault("records", [])
        payload.setdefault("vuln_correction_factors", {})
        payload.setdefault("pattern_confidence_overrides", {})
        return payload

    def _save_db(self) -> None:
        self.db_path.write_text(yaml.safe_dump(self._db, sort_keys=False), encoding="utf-8")

    @staticmethod
    def _normalize(text: str | None) -> str:
        return (text or "").strip().lower()

    def record_finding_outcome(self, finding: dict[str, Any], outcome: dict[str, Any]) -> dict[str, Any]:
        record = OutcomeRecord(
            finding_id=str(finding.get("finding_id") or finding.get("evidence_id") or "unknown"),
            vulnerability_type=str(finding.get("vulnerability_type") or "unknown"),
            estimated_severity_score=float((finding.get("severity") or {}).get("severity_score", 5.0)),
            estimated_payout_usd=int((finding.get("payout") or {}).get("estimated_payout_usd", 0)),
            actual_payout_usd=int(outcome.get("payout_received", 0)),
            platform_decision=str(outcome.get("platform_decision", "unknown")),
            analyst_feedback=str(outcome.get("analyst_feedback", "")),
            pattern_names=list(outcome.get("pattern_names", [])),
            timestamp=str(outcome.get("resolution_date") or datetime.now(UTC).isoformat()),
        )

        self._db["records"].append(record.as_dict())
        self._save_db()
        return record.as_dict()

    def analyze_estimation_accuracy(self) -> dict[str, Any]:
        records = self._db.get("records", [])
        if not records:
            return {
                "record_count": 0,
                "mean_absolute_error_usd": 0.0,
                "bias_usd": 0.0,
                "acceptance_rate": 0.0,
            }

        errors = []
        signed = []
        accepted = 0
        for rec in records:
            est = float(rec.get("estimated_payout_usd", 0.0))
            act = float(rec.get("actual_payout_usd", 0.0))
            errors.append(abs(est - act))
            signed.append(act - est)
            decision = self._normalize(str(rec.get("platform_decision", "")))
            if decision in {"accepted", "duplicate-accepted", "informative-accepted"}:
                accepted += 1

        return {
            "record_count": len(records),
            "mean_absolute_error_usd": round(sum(errors) / len(errors), 2),
            "bias_usd": round(sum(signed) / len(signed), 2),
            "acceptance_rate": round((accepted / len(records)) * 100, 2),
        }

    def improve_severity_estimation(self) -> dict[str, Any]:
        records = self._db.get("records", [])
        grouped: dict[str, list[tuple[float, float]]] = {}
        for rec in records:
            vtype = self._normalize(str(rec.get("vulnerability_type", "unknown")))
            est = float(rec.get("estimated_payout_usd", 0.0))
            act = float(rec.get("actual_payout_usd", 0.0))
            grouped.setdefault(vtype, []).append((est, act))

        factors: dict[str, float] = {}
        for vtype, pairs in grouped.items():
            est_total = sum(p[0] for p in pairs)
            act_total = sum(p[1] for p in pairs)
            if est_total <= 0:
                factors[vtype] = 1.0
            else:
                raw = act_total / est_total
                factors[vtype] = round(min(1.5, max(0.6, raw)), 3)

        self._db["vuln_correction_factors"] = factors
        self._save_db()
        return factors

    def improve_pattern_confidence(self) -> dict[str, Any]:
        records = self._db.get("records", [])
        if not records:
            return self._db.get("pattern_confidence_overrides", {})

        total_by_pattern: dict[str, int] = {}
        accepted_by_pattern: dict[str, int] = {}

        for rec in records:
            decision = self._normalize(str(rec.get("platform_decision", "")))
            accepted = decision in {"accepted", "duplicate-accepted", "informative-accepted"}
            for pname in rec.get("pattern_names", []) or []:
                key = self._normalize(str(pname))
                total_by_pattern[key] = total_by_pattern.get(key, 0) + 1
                if accepted:
                    accepted_by_pattern[key] = accepted_by_pattern.get(key, 0) + 1

        overrides: dict[str, float] = {}
        for pattern in self.pattern_engine.patterns:
            key = self._normalize(pattern.name)
            base = float(pattern.confidence)
            total = total_by_pattern.get(key, 0)
            accepted = accepted_by_pattern.get(key, 0)
            if total == 0:
                overrides[key] = round(base, 2)
                continue

            accuracy = accepted / total
            if accuracy > 0.8:
                new_conf = min(0.99, base + 0.05)
            elif accuracy < 0.6:
                new_conf = max(0.50, base - 0.05)
            else:
                new_conf = base
            overrides[key] = round(new_conf, 2)

        self._db["pattern_confidence_overrides"] = overrides
        self._save_db()
        return overrides

    def get_learning_snapshot(self) -> dict[str, Any]:
        return {
            "db_path": str(self.db_path),
            "record_count": len(self._db.get("records", [])),
            "estimation_accuracy": self.analyze_estimation_accuracy(),
            "vuln_correction_factors": self._db.get("vuln_correction_factors", {}),
            "pattern_confidence_overrides": self._db.get("pattern_confidence_overrides", {}),
        }


__all__ = ["LearningFeedbackLoop", "OutcomeRecord"]
