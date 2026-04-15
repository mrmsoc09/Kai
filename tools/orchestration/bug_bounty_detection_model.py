from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from tools.orchestration.bug_bounty_success_model import (
    BugBountySuccessPredictor,
    OpportunityScope,
    ScopeViolationError,
)


FORBIDDEN_OPERATION_KEYWORDS = {
    "exploitation",
    "exploit",
    "persistence",
    "destruction",
    "evasion",
    "lateral_movement",
}


@dataclass(slots=True)
class DetectionPrediction:
    target_type: str
    recommended_scanning_order: list[dict[str, Any]]
    predicted_finding_types: list[str]
    estimated_findings: float
    estimated_total_payout_usd: float
    estimated_effort_hours: float
    scanning_efficiency: str
    generated_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "target_type": self.target_type,
            "recommended_scanning_order": self.recommended_scanning_order,
            "predicted_finding_types": self.predicted_finding_types,
            "estimated_findings": self.estimated_findings,
            "estimated_total_payout_usd": self.estimated_total_payout_usd,
            "estimated_effort_hours": self.estimated_effort_hours,
            "scanning_efficiency": self.scanning_efficiency,
            "generated_at": self.generated_at,
        }


class BugBountyDetectionIntelligence:
    """
    Scope-validated, detection-only intelligence model.

    Safety rules:
    1) Scope validation is mandatory first step.
    2) Detection-only playbooks are allowed.
    3) Playbooks with forbidden operation markers are excluded.
    """

    def __init__(
        self,
        *,
        frequency_path: str | Path = "tools/knowledge/bug_bounty_detection_frequency.yaml",
        profile_path: str | Path = "tools/knowledge/bug_bounty_target_detection_profile.yaml",
        ranking_path: str | Path = "tools/playbooks/playbook_detection_ranking.yaml",
        scope_predictor: BugBountySuccessPredictor | None = None,
    ) -> None:
        self.frequency_path = Path(frequency_path)
        self.profile_path = Path(profile_path)
        self.ranking_path = Path(ranking_path)
        self.scope_predictor = scope_predictor or BugBountySuccessPredictor()

        self.frequency = self._read_yaml(self.frequency_path)
        self.profile = self._read_yaml(self.profile_path)
        self.ranking = self._read_yaml(self.ranking_path)

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Required artifact missing: {path}")
        payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            raise ValueError(f"Invalid YAML structure: {path}")
        return payload

    @staticmethod
    def _row_text(row: dict[str, Any]) -> str:
        return " ".join(
            [
                str(row.get("detection_playbook_id", "")),
                str(row.get("playbook_name", "")),
                str(row.get("playbook_type", "")),
            ]
        ).lower()

    def _is_detection_only(self, row: dict[str, Any]) -> bool:
        if str(row.get("playbook_type", "")).lower() != "detection_only":
            return False
        if bool(row.get("forbidden_operations_present", False)):
            return False
        # Enforcement uses explicit playbook typing/flags. String keyword scanning on IDs
        # can produce false positives for transformed legacy names.
        return True

    @staticmethod
    def _apply_scope_dampening(row: dict[str, Any], scope: OpportunityScope) -> float:
        base = float(row.get("detection_probability", 0.0))
        vuln = str(row.get("vulnerability_type", "")).lower()
        scope_blob = " ".join(scope.exclusions + scope.rules).lower()

        dampening = 1.0
        if vuln and vuln in scope_blob:
            dampening *= 0.40
        if "api" in scope_blob and vuln == "api_authz":
            dampening *= 0.35
        if "auth" in scope_blob and vuln == "weak_auth":
            dampening *= 0.35
        return round(base * dampening, 6)

    def classify_opportunity_for_detection(
        self,
        target_archetype: str | None,
        hints: dict[str, Any] | None = None,
    ) -> str:
        return self.scope_predictor.classify_opportunity(target_archetype, hints=hints)

    def _load_target_rows(self, target_type: str) -> list[dict[str, Any]]:
        rows = self.ranking.get("playbook_detection_rankings_by_target", {}).get(target_type, [])
        if not isinstance(rows, list):
            return []
        return [dict(r) for r in rows if isinstance(r, dict)]

    @staticmethod
    def estimate_findings(rows: list[dict[str, Any]], top_n: int) -> float:
        selected = rows[: max(1, top_n)]
        return round(sum(float(r.get("scope_adjusted_detection_probability", 0.0)) for r in selected), 3)

    @staticmethod
    def estimate_payout(rows: list[dict[str, Any]], top_n: int) -> float:
        selected = rows[: max(1, top_n)]
        return round(
            sum(
                float(r.get("expected_payout_if_found_usd", 0.0))
                * float(r.get("scope_adjusted_detection_probability", 0.0))
                for r in selected
            ),
            2,
        )

    @staticmethod
    def estimate_effort_hours(rows: list[dict[str, Any]], top_n: int) -> float:
        selected = rows[: max(1, top_n)]
        minutes = sum(float(r.get("execution_time_minutes", 0.0)) for r in selected)
        return round(minutes / 60.0, 2)

    def predict_findings_for_opportunity(
        self,
        *,
        opportunity_scope: OpportunityScope,
        target_archetype: str | None = None,
        target_hints: dict[str, Any] | None = None,
        top_n: int = 15,
    ) -> DetectionPrediction:
        # STEP 1: scope validation (mandatory first step)
        self.scope_predictor.verify_scope_authorized(opportunity_scope)

        # STEP 2: classify target for detection profile
        target_type = self.classify_opportunity_for_detection(target_archetype, hints=target_hints)

        # STEP 3: load and filter detection-only playbooks
        rows = self._load_target_rows(target_type)
        detection_rows = [r for r in rows if self._is_detection_only(r)]
        if not detection_rows:
            raise ScopeViolationError("No detection-only playbooks available after safety filtering.")

        # STEP 4: scope-adjusted probability and efficiency ranking
        for row in detection_rows:
            row["scope_adjusted_detection_probability"] = self._apply_scope_dampening(row, opportunity_scope)
            row["efficiency_score"] = round(
                float(row.get("expected_payout_if_found_usd", 0.0))
                / max(1.0, float(row.get("execution_time_minutes", 1.0))),
                2,
            )

        detection_rows.sort(
            key=lambda r: (
                float(r.get("efficiency_score", 0.0)),
                float(r.get("scope_adjusted_detection_probability", 0.0)),
            ),
            reverse=True,
        )
        for idx, row in enumerate(detection_rows, start=1):
            row["rank"] = idx

        # STEP 5: summary output
        selected = detection_rows[: max(1, top_n)]
        finding_types = sorted({str(r.get("vulnerability_type", "")) for r in selected if r.get("vulnerability_type")})
        est_findings = self.estimate_findings(selected, top_n)
        est_payout = self.estimate_payout(selected, top_n)
        est_effort = self.estimate_effort_hours(selected, top_n)

        return DetectionPrediction(
            target_type=target_type,
            recommended_scanning_order=selected,
            predicted_finding_types=finding_types,
            estimated_findings=est_findings,
            estimated_total_payout_usd=est_payout,
            estimated_effort_hours=est_effort,
            scanning_efficiency="High (scope-validated, detection-only prioritization)",
            generated_at=datetime.now(UTC).isoformat(),
        )
