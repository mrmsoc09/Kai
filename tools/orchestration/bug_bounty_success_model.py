from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

try:
    from apps.backend.src.core.scope_guardrails import evaluate_target_scope, load_scope_policy
except Exception:  # pragma: no cover - fallback for standalone execution
    evaluate_target_scope = None  # type: ignore[assignment]
    load_scope_policy = None  # type: ignore[assignment]


class ScopeViolationError(ValueError):
    pass


class PlatformPolicyViolation(ValueError):
    pass


@dataclass(slots=True)
class OpportunityScope:
    opportunity_id: str
    platform: str
    active: bool
    targets: list[str]
    authorization_verified: bool = False
    program_name: str | None = None
    scope_source: str | None = None
    exclusions: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)
    downloaded_at: str | None = None

    def is_valid(self) -> bool:
        if not self.opportunity_id.strip():
            return False
        if self.platform.lower() not in {"hackerone", "bugcrowd", "intigriti", "direct"}:
            return False
        if not self.targets:
            return False
        return True


@dataclass(slots=True)
class PredictionResult:
    target_type: str
    recommended_playbooks: list[dict[str, Any]]
    predicted_findings: float
    estimated_total_payout_usd: float
    effort_hours: tuple[float, float]
    generated_at: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "target_type": self.target_type,
            "recommended_playbooks": self.recommended_playbooks,
            "predicted_findings": self.predicted_findings,
            "estimated_total_payout_usd": self.estimated_total_payout_usd,
            "effort_hours": self.effort_hours,
            "generated_at": self.generated_at,
        }


class BugBountySuccessPredictor:
    """
    Scope-respecting prediction engine for bug-bounty playbook prioritization.

    Safety contract:
    1) Validate authorized opportunity scope first.
    2) Validate platform policy compatibility.
    3) Rank playbooks only within validated scope constraints.
    """

    def __init__(
        self,
        *,
        frequency_path: str | Path = "tools/knowledge/bug_bounty_vulnerability_frequency.yaml",
        profile_path: str | Path = "tools/knowledge/bug_bounty_target_profile_analysis.yaml",
        ranking_path: str | Path = "tools/playbooks/playbook_bug_bounty_ranking.yaml",
        max_scope_age_days: int = 30,
        allow_local_policy_override: bool = False,
    ) -> None:
        self.frequency_path = Path(frequency_path)
        self.profile_path = Path(profile_path)
        self.ranking_path = Path(ranking_path)
        self.max_scope_age_days = max(1, int(max_scope_age_days))
        self.allow_local_policy_override = bool(allow_local_policy_override)

        self._frequency = self._read_yaml(self.frequency_path)
        self._profiles = self._read_yaml(self.profile_path)
        self._rankings = self._read_yaml(self.ranking_path)
        self._scope_policy = load_scope_policy() if load_scope_policy else None

    @staticmethod
    def _read_yaml(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Required model artifact not found: {path}")
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise ValueError(f"Invalid YAML model structure for {path}")
        return data

    @staticmethod
    def _in_exclusion(playbook_row: dict[str, Any], exclusions: list[str]) -> bool:
        if not exclusions:
            return False
        text = " ".join(
            [
                str(playbook_row.get("playbook", "")),
                str(playbook_row.get("name", "")),
                str(playbook_row.get("category", "")),
                str(playbook_row.get("vulnerability_family", "")),
            ]
        ).lower()
        return any(ex.lower() in text for ex in exclusions if ex.strip())

    def verify_scope_authorized(self, opportunity_scope: OpportunityScope) -> None:
        # MANDATORY FIRST STEP
        if not opportunity_scope.is_valid():
            raise ScopeViolationError("Scope parameters missing, malformed, or unsupported platform.")
        if not opportunity_scope.authorization_verified:
            raise ScopeViolationError("Opportunity authorization is not verified.")
        if not opportunity_scope.active:
            raise ScopeViolationError("Opportunity is not active.")
        if not opportunity_scope.downloaded_at:
            raise ScopeViolationError("Scope metadata missing download timestamp.")
        if not self._is_scope_fresh(opportunity_scope.downloaded_at):
            raise ScopeViolationError("Scope metadata is stale; refresh opportunity scope before execution.")
        if not self.is_policy_compliant_with_platform(opportunity_scope):
            raise PlatformPolicyViolation("Opportunity rules violate platform policy constraints.")

        # Validate each target against global scope guardrails when available.
        if evaluate_target_scope and self._scope_policy:
            for target in opportunity_scope.targets:
                decision = evaluate_target_scope(target, self._scope_policy, safe_mode=True)
                if not decision.allowed and decision.reason == "strict_allowlist_without_entries":
                    if self.allow_local_policy_override and opportunity_scope.authorization_verified:
                        # Allow only when explicitly configured for local/offline operation and
                        # opportunity scope is already verified.
                        continue
                if not decision.allowed:
                    raise ScopeViolationError(
                        f"Target '{target}' rejected by scope guardrails: {decision.reason}"
                    )

    def _is_scope_fresh(self, downloaded_at: str) -> bool:
        try:
            dt = datetime.fromisoformat(downloaded_at.replace("Z", "+00:00"))
        except Exception:
            return False
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        age_days = (datetime.now(UTC) - dt).days
        return age_days <= self.max_scope_age_days

    @staticmethod
    def is_policy_compliant_with_platform(opportunity_scope: OpportunityScope) -> bool:
        # Lightweight policy assertions; deep policy stays in platform-specific enforcement.
        forbidden_markers = {"dos", "ddos", "social engineering", "physical intrusion"}
        rules_blob = " ".join(opportunity_scope.rules).lower()
        return not any(marker in rules_blob for marker in forbidden_markers)

    def classify_opportunity(self, target_archetype: str | None, hints: dict[str, Any] | None = None) -> str:
        if target_archetype:
            normalized = target_archetype.strip().lower()
            if normalized in self._rankings.get("playbook_rankings_by_target_type", {}):
                return normalized

        hints = hints or {}
        industry = str(hints.get("industry", "")).lower()
        company_size = str(hints.get("company_size", "")).lower()

        if any(x in industry for x in ["bank", "finance", "fintech", "insurance"]):
            return "fintech_regulated"
        if any(x in industry for x in ["retail", "commerce", "ecommerce", "consumer"]):
            return "consumer_ecommerce_retail"
        if any(x in company_size for x in ["enterprise", "1000+", "large"]):
            return "enterprise_multi_property"
        if any(x in company_size for x in ["100-1000", "mid", "growth"]):
            return "established_saas"
        return "early_stage_saas"

    @staticmethod
    def calculate_success_within_scope(
        playbook_row: dict[str, Any],
        opportunity_scope: OpportunityScope,
    ) -> float:
        base = float(playbook_row.get("success_probability", 0.0))
        family = str(playbook_row.get("vulnerability_family", "")).lower()
        name = str(playbook_row.get("name", "")).lower()

        # Scope-aware dampening: if exclusions mention family/class, lower probability.
        dampening = 1.0
        exclusion_blob = " ".join(opportunity_scope.exclusions).lower()
        if family and family in exclusion_blob:
            dampening *= 0.25
        if "admin" in exclusion_blob and "privilege" in name:
            dampening *= 0.50
        if "api" in exclusion_blob and family == "api":
            dampening *= 0.35
        return round(base * dampening, 6)

    @staticmethod
    def estimate_findings(rows: list[dict[str, Any]], *, execution_budget: int = 10) -> float:
        selected = rows[: max(1, execution_budget)]
        return round(sum(float(r.get("scope_adjusted_probability", 0.0)) for r in selected), 3)

    @staticmethod
    def estimate_effort(rows: list[dict[str, Any]], *, execution_budget: int = 10) -> tuple[float, float]:
        selected = rows[: max(1, execution_budget)]
        # Heuristic: 0.6h to 1.6h per selected playbook, scaled by confidence spread.
        min_h = round(0.6 * len(selected), 1)
        max_h = round(1.6 * len(selected), 1)
        return (min_h, max_h)

    def predict_findings_for_opportunity(
        self,
        *,
        opportunity_scope: OpportunityScope,
        target_archetype: str | None = None,
        target_hints: dict[str, Any] | None = None,
        top_n: int = 10,
    ) -> PredictionResult:
        # 1) Scope enforcement (non-negotiable)
        self.verify_scope_authorized(opportunity_scope)

        # 2) Opportunity classification
        target_type = self.classify_opportunity(target_archetype, hints=target_hints)
        ranked = list(
            self._rankings.get("playbook_rankings_by_target_type", {}).get(target_type, [])
        )
        if not ranked:
            raise ValueError(f"No ranking rows available for target type '{target_type}'.")

        # 3) Scope-aware scoring adjustment and exclusion filtering
        filtered: list[dict[str, Any]] = []
        for row in ranked:
            if self._in_exclusion(row, opportunity_scope.exclusions):
                continue
            score = self.calculate_success_within_scope(row, opportunity_scope)
            if score <= 0:
                continue
            row_copy = dict(row)
            row_copy["scope_adjusted_probability"] = score
            filtered.append(row_copy)

        filtered.sort(key=lambda r: float(r.get("scope_adjusted_probability", 0.0)), reverse=True)
        selected = filtered[: max(1, top_n)]

        # 4) Aggregate projected outcomes
        predicted_findings = self.estimate_findings(selected, execution_budget=top_n)
        estimated_total_payout = round(
            sum(
                float(r.get("expected_payout_per_finding_usd", 0))
                * float(r.get("scope_adjusted_probability", 0))
                for r in selected
            ),
            2,
        )
        effort_hours = self.estimate_effort(selected, execution_budget=top_n)

        return PredictionResult(
            target_type=target_type,
            recommended_playbooks=selected,
            predicted_findings=predicted_findings,
            estimated_total_payout_usd=estimated_total_payout,
            effort_hours=effort_hours,
            generated_at=datetime.now(UTC).isoformat(),
        )
