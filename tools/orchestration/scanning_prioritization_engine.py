from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from tools.orchestration.bug_bounty_detection_model import BugBountyDetectionIntelligence
from tools.orchestration.bug_bounty_success_model import OpportunityScope


@dataclass(slots=True)
class ScanningPlan:
    target_type: str
    recommended_scanning_order: list[dict[str, Any]]
    total_estimated_scan_time_minutes: int
    estimated_findings: float
    estimated_total_payout_usd: float
    estimated_effort_hours: float
    scanning_efficiency: str
    generated_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "target_type": self.target_type,
            "recommended_scanning_order": self.recommended_scanning_order,
            "total_estimated_scan_time_minutes": self.total_estimated_scan_time_minutes,
            "estimated_findings": self.estimated_findings,
            "estimated_total_payout_usd": self.estimated_total_payout_usd,
            "estimated_effort_hours": self.estimated_effort_hours,
            "scanning_efficiency": self.scanning_efficiency,
            "generated_at": self.generated_at,
        }


class ScanningPrioritizationEngine:
    """
    Detection-only scanning prioritization.

    Design constraints:
    - Scope validation is mandatory before plan generation.
    - Detection-only playbooks are enforced through the detection model.
    - No exploitation/persistence/destruction/evasion workflow is generated.
    """

    def __init__(
        self,
        *,
        detection_model: BugBountyDetectionIntelligence | None = None,
        optimized_playbook_dir: str | Path = "tools/playbooks/optimized_detection_v2",
        batching_efficiency_factor: float = 0.70,
    ) -> None:
        self.detection_model = detection_model or BugBountyDetectionIntelligence()
        self.optimized_playbook_dir = Path(optimized_playbook_dir)
        self.batching_efficiency_factor = min(max(batching_efficiency_factor, 0.5), 1.0)
        self._optimized_index = self._load_optimized_playbook_index()

    def _load_optimized_playbook_index(self) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        if not self.optimized_playbook_dir.exists():
            return out
        for f in self.optimized_playbook_dir.glob("*_optimized_v2.yaml"):
            payload = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
            pb = payload.get("playbook", {})
            meta = pb.get("metadata", {})
            base = str(meta.get("base_detection_playbook_id", "")).strip()
            if not base:
                continue
            out[base] = {"file": str(f), "payload": payload}
        return out

    @staticmethod
    def _efficiency_score(row: dict[str, Any]) -> float:
        payout = float(row.get("expected_payout_if_found_usd", 0.0))
        minutes = max(1.0, float(row.get("execution_time_minutes", 1.0)))
        probability = float(row.get("scope_adjusted_detection_probability", 0.0))
        return round((probability * payout) / minutes, 6)

    def optimize_scanning_order(
        self,
        *,
        opportunity_scope: OpportunityScope,
        target_archetype: str | None = None,
        target_hints: dict[str, Any] | None = None,
        top_n: int = 10,
    ) -> ScanningPlan:
        pred = self.detection_model.predict_findings_for_opportunity(
            opportunity_scope=opportunity_scope,
            target_archetype=target_archetype,
            target_hints=target_hints,
            top_n=max(top_n, 20),
        )

        utility_ids = {
            "det_target_fingerprinter_v1",
            "det_archetype_classifier_v1",
            "det_vulnerability_predictor_v1",
        }
        ranked: list[dict[str, Any]] = []
        pre_scan_steps: list[dict[str, Any]] = []
        for row in pred.recommended_scanning_order:
            row_copy = dict(row)
            row_copy["efficiency_score"] = self._efficiency_score(row_copy)
            base_id = str(row_copy.get("detection_playbook_id", ""))
            if base_id in utility_ids:
                pre_scan_steps.append(row_copy)
                continue

            optimized = self._optimized_index.get(base_id)
            if optimized:
                row_copy["optimized_playbook_file"] = optimized["file"]
                pb = optimized["payload"].get("playbook", {})
                base = pb.get("optimization_baseline", {})
                row_copy["optimized_execution_time_minutes"] = base.get(
                    "optimized_execution_minutes",
                    row_copy.get("execution_time_minutes"),
                )
                row_copy["optimized_network_requests"] = base.get("optimized_network_requests")
                row_copy["has_optimized_mapping"] = True
            else:
                row_copy["has_optimized_mapping"] = False
            ranked.append(row_copy)

        ranked.sort(
            key=lambda r: (
                float(r.get("efficiency_score", 0.0)),
                float(r.get("scope_adjusted_detection_probability", 0.0)),
            ),
            reverse=True,
        )
        optimized_first = [r for r in ranked if r.get("has_optimized_mapping")]
        unoptimized = [r for r in ranked if not r.get("has_optimized_mapping")]
        merged = optimized_first + unoptimized
        selected = merged[: max(1, top_n)]
        for i, row in enumerate(selected, start=1):
            row["priority"] = i

        raw_detection_time = int(
            sum(
                int(
                    row.get(
                        "optimized_execution_time_minutes",
                        row.get("execution_time_minutes", 0),
                    )
                )
                for row in selected
            )
        )
        pre_scan_minutes = int(sum(int(x.get("execution_time_minutes", 0)) for x in pre_scan_steps))
        batched_detection_time = int(round(raw_detection_time * self.batching_efficiency_factor))
        total_scan_time = pre_scan_minutes + batched_detection_time

        return ScanningPlan(
            target_type=pred.target_type,
            recommended_scanning_order=[
                {
                    "phase": "pre_scan_profiling",
                    "steps": [
                        {
                            "detection_playbook_id": x.get("detection_playbook_id"),
                            "playbook_name": x.get("playbook_name"),
                            "execution_time_minutes": x.get("execution_time_minutes"),
                            "purpose": "target profiling and classification",
                        }
                        for x in pre_scan_steps
                    ],
                },
                {
                    "phase": "prioritized_detection_scans",
                    "batching_efficiency_factor": self.batching_efficiency_factor,
                    "steps": selected,
                },
            ],
            total_estimated_scan_time_minutes=total_scan_time,
            estimated_findings=pred.estimated_findings,
            estimated_total_payout_usd=pred.estimated_total_payout_usd,
            estimated_effort_hours=round(total_scan_time / 60.0, 2),
            scanning_efficiency="High (probability + payout per minute prioritized)",
            generated_at=datetime.now(UTC).isoformat(),
        )
