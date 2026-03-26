from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _cap_extreme_certainty(value: float) -> float:
    # Keep confidence bounded away from absolute certainty.
    return max(0.02, min(0.98, value))


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "y", "on"}:
            return True
        if lowered in {"0", "false", "no", "n", "off"}:
            return False
    if value is None:
        return default
    return bool(value)


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if raw in {"1", "true", "yes", "y", "on"}:
        return True
    if raw in {"0", "false", "no", "n", "off"}:
        return False
    return default


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


class BayesianEventUpdate(BaseModel):
    event: str
    prior: float = Field(ge=0.0, le=1.0)
    likelihood_true: float = Field(ge=0.0, le=1.0)
    likelihood_false: float = Field(ge=0.0, le=1.0)
    posterior: float = Field(ge=0.0, le=1.0)
    explanation: str

    def persistence_record(self, *, run_id: str, finding_key: str, index: int) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "finding_key": finding_key,
            "event_index": index,
            "event": self.event,
            "prior": self.prior,
            "likelihood_true": self.likelihood_true,
            "likelihood_false": self.likelihood_false,
            "posterior": self.posterior,
            "explanation": self.explanation,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


class ArbitrationDecision(BaseModel):
    final_verdict: str
    final_confidence: float = Field(ge=0.0, le=1.0)
    arbitration_reason: str
    structured_verdict: str
    vision_verdict: str
    conflict_detected: bool = False
    source: str
    swarm_consensus_used: bool = False
    bayesian_posterior_true: float = Field(ge=0.0, le=1.0)
    bayesian_updates: list[BayesianEventUpdate] = Field(default_factory=list)

    def persistence_record(self, *, run_id: str, finding_key: str) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "finding_key": finding_key,
            "final_verdict": self.final_verdict,
            "final_confidence": self.final_confidence,
            "arbitration_reason": self.arbitration_reason,
            "structured_verdict": self.structured_verdict,
            "vision_verdict": self.vision_verdict,
            "conflict_detected": self.conflict_detected,
            "source": self.source,
            "swarm_consensus_used": self.swarm_consensus_used,
            "bayesian_posterior_true": self.bayesian_posterior_true,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }


@dataclass
class _SwarmConsensus:
    verdict: str
    confidence: float
    reason: str


class ArbitrationService:
    """
    Non-destructive arbitration layer combining structured + vision signals,
    optional swarm voting, and Bayesian confidence updates.
    """

    _EVENT_LIKELIHOODS: dict[str, tuple[float, float]] = {
        "exploit_success": (0.85, 0.25),
        "exploit_failure": (0.20, 0.75),
        "duplicate": (0.35, 0.60),
        "accepted": (0.90, 0.40),
        "rejected": (0.25, 0.80),
    }

    def __init__(
        self,
        *,
        swarm_mode: bool | None = None,
        structured_confirm_threshold: float | None = None,
        structured_reject_threshold: float | None = None,
        unresolved_margin: float | None = None,
    ) -> None:
        self._swarm_mode = swarm_mode if swarm_mode is not None else _env_bool("K1_ARBITRATION_SWARM_MODE", False)
        self._structured_confirm_threshold = (
            structured_confirm_threshold
            if structured_confirm_threshold is not None
            else _env_float("K1_ARBITRATION_STRUCTURED_CONFIRM_THRESHOLD", 0.65)
        )
        self._structured_reject_threshold = (
            structured_reject_threshold
            if structured_reject_threshold is not None
            else _env_float("K1_ARBITRATION_STRUCTURED_REJECT_THRESHOLD", 0.35)
        )
        self._unresolved_margin = (
            unresolved_margin
            if unresolved_margin is not None
            else _env_float("K1_ARBITRATION_UNRESOLVED_MARGIN", 0.12)
        )
        self._swarm_consensus_threshold = _env_float("K1_ARBITRATION_SWARM_CONSENSUS_THRESHOLD", 0.60)
        self._prior_true_default = _env_float("K1_BAYES_PRIOR_TRUE", 0.50)

    @staticmethod
    def _finding_key(row: dict[str, Any], index: int) -> str:
        return f"{row.get('title','')}|{row.get('target','')}|{row.get('severity_hint','')}|{index}"

    def _structured_verdict(self, row: dict[str, Any]) -> tuple[str, float]:
        score = _clamp01(_to_float(row.get("confidence_score"), _to_float(row.get("confidence"), 0.5)))
        if score >= self._structured_confirm_threshold:
            return "confirmed", score
        if score <= self._structured_reject_threshold:
            return "rejected", 1.0 - score
        return "escalate", 0.50

    @staticmethod
    def _vision_verdict(row: dict[str, Any]) -> tuple[str, float]:
        vision = row.get("vision_validation")
        if not isinstance(vision, dict):
            return "not_available", 0.0
        status = str(vision.get("status") or "").lower()
        screenshots = vision.get("screenshots") if isinstance(vision.get("screenshots"), list) else []
        metadata = vision.get("metadata") if isinstance(vision.get("metadata"), dict) else {}
        has_recording = bool(metadata.get("recording_path"))
        if status == "completed" and screenshots and has_recording:
            return "confirmed", 0.88
        if status == "failed":
            return "rejected", 0.78
        return "escalate", 0.50

    @staticmethod
    def _reproducibility_strength(row: dict[str, Any]) -> float:
        breakdown = row.get("confidence_breakdown")
        if isinstance(breakdown, dict) and breakdown.get("reproducibility") is not None:
            return _clamp01(_to_float(breakdown.get("reproducibility"), 0.5))
        return 0.5

    @staticmethod
    def _structured_evidence_strength(row: dict[str, Any]) -> float:
        breakdown = row.get("confidence_breakdown")
        if isinstance(breakdown, dict):
            completeness = _clamp01(_to_float(breakdown.get("evidence_completeness"), 0.5))
            parser = _clamp01(_to_float(breakdown.get("parser_integrity"), 0.5))
            scope = _clamp01(_to_float(breakdown.get("scope_validity"), 0.5))
            return _cap_extreme_certainty((0.45 * completeness) + (0.35 * parser) + (0.20 * scope))
        return 0.55

    @staticmethod
    def _vision_evidence_strength(row: dict[str, Any]) -> float:
        vision = row.get("vision_validation")
        if not isinstance(vision, dict):
            return 0.0
        status = str(vision.get("status") or "").lower()
        screenshots = vision.get("screenshots") if isinstance(vision.get("screenshots"), list) else []
        metadata = vision.get("metadata") if isinstance(vision.get("metadata"), dict) else {}
        has_recording = bool(metadata.get("recording_path"))
        if status == "completed":
            base = 0.55
            if has_recording:
                base += 0.25
            if screenshots:
                base += min(0.20, 0.06 * len(screenshots))
            return _cap_extreme_certainty(base)
        if status == "failed":
            # Failure has weaker evidentiary confidence than successful reproduction.
            return 0.42
        return 0.30

    def _swarm_consensus(self, row: dict[str, Any]) -> _SwarmConsensus | None:
        if not self._swarm_mode:
            return None
        votes = row.get("swarm_votes")
        if not isinstance(votes, list) or not votes:
            return None

        scores: dict[str, float] = {"confirmed": 0.0, "rejected": 0.0, "escalate": 0.0}
        for vote in votes:
            if not isinstance(vote, dict):
                continue
            verdict = str(vote.get("verdict") or "").lower()
            if verdict not in scores:
                continue
            confidence = _clamp01(_to_float(vote.get("confidence"), 0.5))
            weight = max(0.0, _to_float(vote.get("weight"), 1.0))
            scores[verdict] += confidence * weight

        total = sum(scores.values())
        if total <= 0.0:
            return None
        verdict = max(scores, key=scores.get)
        confidence = _clamp01(scores[verdict] / total)
        if confidence < self._swarm_consensus_threshold:
            return None
        return _SwarmConsensus(
            verdict=verdict,
            confidence=_cap_extreme_certainty(confidence),
            reason=f"swarm_weighted_consensus:{verdict}:{confidence:.3f}",
        )

    @classmethod
    def _bayes_update(
        cls,
        *,
        prior_true: float,
        event: str,
    ) -> BayesianEventUpdate | None:
        likelihoods = cls._EVENT_LIKELIHOODS.get(event)
        if likelihoods is None:
            return None
        likelihood_true, likelihood_false = likelihoods
        prior = _cap_extreme_certainty(prior_true)
        numerator = likelihood_true * prior
        denominator = numerator + (likelihood_false * (1.0 - prior))
        if denominator <= 0.0:
            posterior = prior
        else:
            posterior = _cap_extreme_certainty(numerator / denominator)
        return BayesianEventUpdate(
            event=event,
            prior=round(prior, 4),
            likelihood_true=likelihood_true,
            likelihood_false=likelihood_false,
            posterior=round(posterior, 4),
            explanation=(
                f"posterior update for {event}: "
                f"prior={prior:.4f}, p(e|vuln)={likelihood_true:.2f}, p(e|not_vuln)={likelihood_false:.2f}"
            ),
        )

    def _bayesian_updates(self, row: dict[str, Any], *, prior_true: float) -> list[BayesianEventUpdate]:
        events: list[str] = []
        vision_status = str(row.get("vision_status") or "").lower()
        if vision_status == "completed":
            events.append("exploit_success")
        elif vision_status == "failed":
            events.append("exploit_failure")
        duplication = _to_float((row.get("confidence_breakdown") or {}).get("duplication_risk"), 0.0) if isinstance(row.get("confidence_breakdown"), dict) else 0.0
        if duplication >= 0.55:
            events.append("duplicate")
        if _to_bool(row.get("accepted"), default=False):
            events.append("accepted")
        if _to_bool(row.get("rejected"), default=False):
            events.append("rejected")

        posterior = _cap_extreme_certainty(prior_true)
        updates: list[BayesianEventUpdate] = []
        for event in events:
            update = self._bayes_update(prior_true=posterior, event=event)
            if update is None:
                continue
            posterior = update.posterior
            updates.append(update)
        if not updates:
            updates.append(
                BayesianEventUpdate(
                    event="prior_only",
                    prior=round(_cap_extreme_certainty(prior_true), 4),
                    likelihood_true=1.0,
                    likelihood_false=1.0,
                    posterior=round(_cap_extreme_certainty(prior_true), 4),
                    explanation="no bayesian events; posterior remains at prior",
                )
            )
        return updates

    def arbitrate_finding(self, row: dict[str, Any]) -> ArbitrationDecision:
        structured_verdict, structured_conf = self._structured_verdict(row)
        vision_verdict, vision_conf = self._vision_verdict(row)
        conflict_detected = (
            structured_verdict in {"confirmed", "rejected"}
            and vision_verdict in {"confirmed", "rejected"}
            and structured_verdict != vision_verdict
        )

        chosen_verdict = structured_verdict
        chosen_conf = structured_conf
        source = "structured_default"
        reason = "structured_default_precedence"

        if structured_verdict == "escalate" and vision_verdict in {"confirmed", "rejected"}:
            chosen_verdict = vision_verdict
            chosen_conf = vision_conf
            source = "vision_fallback"
            reason = "structured_uncertain_using_vision"

        if conflict_detected:
            structured_strength = (
                0.6 * self._structured_evidence_strength(row)
                + 0.4 * self._reproducibility_strength(row)
            )
            vision_strength = (
                0.6 * self._vision_evidence_strength(row)
                + 0.4 * self._reproducibility_strength(row)
            )
            diff = abs(structured_strength - vision_strength)
            if diff < self._unresolved_margin:
                chosen_verdict = "escalate"
                chosen_conf = 0.5
                source = "conflict_unresolved"
                reason = (
                    f"structured_vs_vision_conflict_unresolved;"
                    f"structured_strength={structured_strength:.3f};vision_strength={vision_strength:.3f}"
                )
            elif structured_strength > vision_strength:
                chosen_verdict = structured_verdict
                chosen_conf = _cap_extreme_certainty(structured_strength)
                source = "conflict_resolved_structured"
                reason = (
                    f"conflict_resolved_by_evidence_reproducibility;"
                    f"structured_strength={structured_strength:.3f};vision_strength={vision_strength:.3f}"
                )
            else:
                chosen_verdict = vision_verdict
                chosen_conf = _cap_extreme_certainty(vision_strength)
                source = "conflict_resolved_vision"
                reason = (
                    f"conflict_resolved_by_evidence_reproducibility;"
                    f"structured_strength={structured_strength:.3f};vision_strength={vision_strength:.3f}"
                )

        consensus = self._swarm_consensus(row)
        swarm_used = False
        if consensus is not None:
            # Weighted swarm can resolve escalation or override weak single-source verdicts.
            if chosen_verdict == "escalate" and consensus.verdict in {"confirmed", "rejected"}:
                chosen_verdict = consensus.verdict
                chosen_conf = consensus.confidence
                source = "swarm_consensus"
                reason = f"{reason};{consensus.reason}"
                swarm_used = True
            elif consensus.verdict != chosen_verdict and consensus.confidence > (chosen_conf + 0.12):
                chosen_verdict = consensus.verdict
                chosen_conf = consensus.confidence
                source = "swarm_override"
                reason = f"{reason};{consensus.reason}"
                swarm_used = True

        prior_true = _to_float(row.get("confidence_score"), _to_float(row.get("confidence"), self._prior_true_default))
        updates = self._bayesian_updates(row, prior_true=_cap_extreme_certainty(prior_true))
        posterior_true = updates[-1].posterior if updates else _cap_extreme_certainty(prior_true)

        if chosen_verdict == "confirmed":
            verdict_conf = posterior_true
        elif chosen_verdict == "rejected":
            verdict_conf = 1.0 - posterior_true
        else:
            verdict_conf = 0.50 + min(0.20, abs(posterior_true - 0.50) / 2.0)
        final_conf = _cap_extreme_certainty((0.55 * verdict_conf) + (0.45 * _clamp01(chosen_conf)))

        return ArbitrationDecision(
            final_verdict=chosen_verdict,
            final_confidence=round(final_conf, 4),
            arbitration_reason=reason,
            structured_verdict=structured_verdict,
            vision_verdict=vision_verdict,
            conflict_detected=conflict_detected,
            source=source,
            swarm_consensus_used=swarm_used,
            bayesian_posterior_true=round(_cap_extreme_certainty(posterior_true), 4),
            bayesian_updates=updates,
        )

    def arbitrate_findings(
        self,
        *,
        run_id: str,
        findings: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
        if not findings:
            return [], [], []

        enriched: list[dict[str, Any]] = []
        arbitration_records: list[dict[str, Any]] = []
        bayesian_records: list[dict[str, Any]] = []

        for index, raw in enumerate(findings, start=1):
            row = dict(raw)
            finding_key = self._finding_key(row, index)
            decision = self.arbitrate_finding(row)

            row["arbitration"] = decision.model_dump()
            row["final_verdict"] = decision.final_verdict
            row["final_confidence"] = decision.final_confidence
            row["arbitration_reason"] = decision.arbitration_reason
            row["bayesian_posterior_true"] = decision.bayesian_posterior_true

            if decision.final_verdict == "confirmed":
                row["requires_validation"] = False
                row["state_uncertain"] = False
                row["validation_reason"] = "arbitration_confirmed"
            else:
                row["requires_validation"] = True
                row["state_uncertain"] = True
                row["validation_reason"] = (
                    "arbitration_rejected" if decision.final_verdict == "rejected" else "arbitration_escalated"
                )

            enriched.append(row)
            arbitration_records.append(decision.persistence_record(run_id=run_id, finding_key=finding_key))
            for idx, update in enumerate(decision.bayesian_updates, start=1):
                bayesian_records.append(
                    update.persistence_record(
                        run_id=run_id,
                        finding_key=finding_key,
                        index=idx,
                    )
                )

        return enriched, arbitration_records, bayesian_records

