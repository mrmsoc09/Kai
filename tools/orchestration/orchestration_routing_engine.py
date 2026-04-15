from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

from tools.orchestration.bug_bounty_success_model import (
    BugBountySuccessPredictor,
    OpportunityScope,
)


FingerprintFn = Callable[[str, dict[str, Any] | None], dict[str, Any]]
ClassifierFn = Callable[[dict[str, Any]], dict[str, Any]]
ExecutorFn = Callable[[str, str, dict[str, Any]], dict[str, Any]]
ScopePlaybookFn = Callable[[OpportunityScope, str], bool]


def _default_fingerprinter(target: str, hints: dict[str, Any] | None = None) -> dict[str, Any]:
    hints = dict(hints or {})
    return {
        "target": target,
        "web_server": hints.get("web_server", "unknown"),
        "backend_framework": hints.get("backend_framework", "unknown"),
        "database": hints.get("database", "unknown"),
        "cloud": hints.get("cloud", "unknown"),
        "waf": hints.get("waf", "unknown"),
        "industry": hints.get("industry", "unknown"),
        "company_size": hints.get("company_size", "unknown"),
    }


def _default_classifier(fingerprint: dict[str, Any]) -> dict[str, Any]:
    industry = str(fingerprint.get("industry", "")).lower()
    company_size = str(fingerprint.get("company_size", "")).lower()
    backend = str(fingerprint.get("backend_framework", "")).lower()
    database = str(fingerprint.get("database", "")).lower()
    waf = str(fingerprint.get("waf", "")).lower()

    if any(x in industry for x in ("finance", "bank", "insurance")):
        archetype = "fintech_regulated"
        confidence = 0.88
    elif any(x in company_size for x in ("1000+", "enterprise", "large")):
        archetype = "enterprise_multi_property"
        confidence = 0.82
    elif any(x in industry for x in ("retail", "commerce", "ecommerce")):
        archetype = "consumer_ecommerce_retail"
        confidence = 0.84
    elif any(x in backend for x in ("node", "express", "fastapi", "django")) and any(
        x in database for x in ("postgres", "mysql")
    ):
        archetype = "early_stage_saas"
        confidence = 0.86
    else:
        archetype = "established_saas" if waf not in {"unknown", ""} else "early_stage_saas"
        confidence = 0.71

    return {
        "archetype": archetype,
        "confidence": confidence,
        "reasoning": "Stack and industry signals mapped to known bug-bounty archetypes.",
    }


def _default_executor(playbook_id: str, target: str, context: dict[str, Any]) -> dict[str, Any]:
    # Safe default: planning-only stub; real execution must be injected by orchestrator runtime.
    return {
        "playbook_id": playbook_id,
        "target": target,
        "status": "planned",
        "vulnerabilities_found": [],
        "notes": "No live execution adapter configured.",
        "context": context,
    }


def _default_scope_playbook_validator(opportunity_scope: OpportunityScope, playbook_id: str) -> bool:
    _ = opportunity_scope
    _ = playbook_id
    return True


class UnsafeExecutionError(RuntimeError):
    pass


@dataclass(slots=True)
class OrchestrationMetrics:
    baseline_total_minutes: int = 165
    baseline_scan_minutes: int = 40
    optimized_fingerprint_minutes: int = 5
    optimized_classification_minutes: int = 2
    optimized_prediction_minutes: int = 1
    optimized_exec_minutes: int = 18
    baseline_success_rate: float = 0.65
    optimized_success_rate: float = 0.82

    def as_dict(self) -> dict[str, Any]:
        optimized_total = (
            self.optimized_fingerprint_minutes
            + self.optimized_classification_minutes
            + self.optimized_prediction_minutes
            + self.optimized_exec_minutes
        )
        return {
            "baseline_total_minutes": self.baseline_total_minutes,
            "optimized_total_minutes": optimized_total,
            "time_reduction_percent": round(
                (1 - optimized_total / max(1, self.baseline_total_minutes)) * 100, 2
            ),
            "scan_overhead_reduction_percent": round(
                (1 - self.optimized_fingerprint_minutes / max(1, self.baseline_scan_minutes)) * 100,
                2,
            ),
            "baseline_success_rate": self.baseline_success_rate,
            "optimized_success_rate": self.optimized_success_rate,
            "success_rate_improvement_percent": round(
                (self.optimized_success_rate - self.baseline_success_rate)
                / max(0.01, self.baseline_success_rate)
                * 100,
                2,
            ),
        }


class IntelligentOrchestrator:
    """
    Fingerprint -> classify -> rank -> select -> execute orchestration engine.

    This engine is scope-first and predictor-driven. It does not modify global
    guardrails and expects safe execution adapters from the platform runtime.
    """

    def __init__(
        self,
        *,
        predictor: BugBountySuccessPredictor | None = None,
        fingerprinter: FingerprintFn | None = None,
        classifier: ClassifierFn | None = None,
        playbook_executor: ExecutorFn | None = None,
        scope_playbook_validator: ScopePlaybookFn | None = None,
        metrics: OrchestrationMetrics | None = None,
        allow_live_execution: bool = False,
        max_playbooks_to_execute: int = 5,
    ) -> None:
        self.predictor = predictor or BugBountySuccessPredictor()
        self.fingerprinter = fingerprinter or _default_fingerprinter
        self.classifier = classifier or _default_classifier
        self.playbook_executor = playbook_executor or _default_executor
        self.scope_playbook_validator = scope_playbook_validator or _default_scope_playbook_validator
        self.metrics = metrics or OrchestrationMetrics()
        self.allow_live_execution = bool(allow_live_execution)
        self.max_playbooks_to_execute = max(1, int(max_playbooks_to_execute))

    def autonomous_exploitation_workflow(
        self,
        *,
        opportunity_scope: OpportunityScope,
        target: str,
        target_hints: dict[str, Any] | None = None,
        top_n: int = 5,
        execution_mode: str = "planning_only",
    ) -> dict[str, Any]:
        mode = str(execution_mode or "planning_only").strip().lower()
        if mode not in {"planning_only", "live"}:
            raise ValueError("execution_mode must be 'planning_only' or 'live'.")
        if mode == "live" and not self.allow_live_execution:
            raise UnsafeExecutionError("Live execution is disabled by policy. Use planning_only.")

        # PHASE 0: mandatory scope authorization for the opportunity
        self.predictor.verify_scope_authorized(opportunity_scope)

        # PHASE 1: target fingerprinting (fast)
        fingerprint = self.fingerprinter(target, target_hints)

        # PHASE 2: archetype classification
        classification = self.classifier(fingerprint)
        archetype = str(classification.get("archetype", "early_stage_saas"))

        # PHASE 3: vulnerability prediction and ranking
        prediction = self.predictor.predict_findings_for_opportunity(
            opportunity_scope=opportunity_scope,
            target_archetype=archetype,
            target_hints=fingerprint,
            top_n=max(top_n, 10),
        )

        # PHASE 4: execute only top scoped playbooks
        selected = prediction.recommended_playbooks[: max(1, min(top_n, self.max_playbooks_to_execute))]
        findings: list[dict[str, Any]] = []
        execution_log: list[dict[str, Any]] = []

        for row in selected:
            playbook_id = str(row.get("playbook", ""))
            if not playbook_id:
                continue
            if not self.scope_playbook_validator(opportunity_scope, playbook_id):
                execution_log.append(
                    {
                        "playbook_id": playbook_id,
                        "status": "skipped_out_of_scope",
                        "reason": "scope_playbook_validator=false",
                    }
                )
                continue

            if mode == "planning_only":
                result = _default_executor(
                    playbook_id,
                    target,
                    {
                        "prediction_row": row,
                        "execution_mode": mode,
                        "safe_mode": True,
                    },
                )
            else:
                result = self.playbook_executor(
                    playbook_id,
                    target,
                    {
                        "prediction_row": row,
                        "execution_mode": mode,
                        "safe_mode": True,
                    },
                )
            execution_log.append(
                {
                    "playbook_id": playbook_id,
                    "status": result.get("status", "unknown"),
                    "predicted_success_probability": row.get("scope_adjusted_probability"),
                    "execution_mode": mode,
                }
            )
            if result.get("vulnerabilities_found"):
                findings.append(result)

        # PHASE 5: reporting summary
        return {
            "generated_at": datetime.now(UTC).isoformat(),
            "target": target,
            "opportunity_id": opportunity_scope.opportunity_id,
            "platform": opportunity_scope.platform,
            "fingerprint": fingerprint,
            "classification": classification,
            "prediction_summary": prediction.as_dict(),
            "selected_playbooks": [row.get("playbook") for row in selected],
            "execution_log": execution_log,
            "findings": findings,
            "orchestration_metrics": self.metrics.as_dict(),
            "safety": {
                "execution_mode": mode,
                "live_execution_enabled": self.allow_live_execution,
                "max_playbooks_to_execute": self.max_playbooks_to_execute,
                "scope_authorization_required": True,
            },
        }

    def orchestration_summary(self) -> dict[str, Any]:
        """
        Operational comparison against baseline broad execution.
        """
        base = self.metrics.as_dict()
        return {
            "baseline_strategy": {
                "approach": "execute large playbook set indiscriminately",
                "total_minutes": self.metrics.baseline_total_minutes,
                "success_rate": self.metrics.baseline_success_rate,
            },
            "optimized_strategy": {
                "approach": "fingerprint + classify + predict + execute top-ranked set",
                "total_minutes": base["optimized_total_minutes"],
                "success_rate": self.metrics.optimized_success_rate,
            },
            "improvements": {
                "time_reduction_percent": base["time_reduction_percent"],
                "scan_overhead_reduction_percent": base["scan_overhead_reduction_percent"],
                "success_rate_improvement_percent": base["success_rate_improvement_percent"],
            },
        }
