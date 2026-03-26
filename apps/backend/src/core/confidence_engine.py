from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Mapping

from pydantic import BaseModel, Field

from .trigger_engine import TriggerDecision, decide_validation_trigger


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


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


class ConfidenceBreakdown(BaseModel):
    tool_reliability: float = Field(ge=0.0, le=1.0)
    reproducibility: float = Field(ge=0.0, le=1.0)
    evidence_completeness: float = Field(ge=0.0, le=1.0)
    exploit_confirmation: float = Field(ge=0.0, le=1.0)
    duplication_risk: float = Field(ge=0.0, le=1.0)
    scope_validity: float = Field(ge=0.0, le=1.0)
    parser_integrity: float = Field(ge=0.0, le=1.0)
    environment_stability: float = Field(ge=0.0, le=1.0)


class ConfidenceAssessment(BaseModel):
    confidence_score: float = Field(ge=0.0, le=1.0)
    confidence_breakdown: ConfidenceBreakdown
    confidence_explanation: str
    state_uncertain: bool = False
    trigger_decision: TriggerDecision

    def persistence_record(
        self,
        *,
        run_id: str,
        source_tool: str | None,
        finding_key: str,
    ) -> dict[str, Any]:
        return {
            "run_id": run_id,
            "source_tool": source_tool or "",
            "finding_key": finding_key,
            "confidence_score": self.confidence_score,
            "confidence_breakdown": self.confidence_breakdown.model_dump(),
            "confidence_explanation": self.confidence_explanation,
            "state_uncertain": self.state_uncertain,
            "trigger_decision": self.trigger_decision.model_dump(),
            "scored_at": datetime.now(timezone.utc).isoformat(),
        }


_WEIGHTS: dict[str, float] = {
    "tool_reliability": 0.16,
    "reproducibility": 0.14,
    "evidence_completeness": 0.14,
    "exploit_confirmation": 0.14,
    "duplication_inverse": 0.10,
    "scope_validity": 0.12,
    "parser_integrity": 0.10,
    "environment_stability": 0.10,
}


def _tool_reliability(finding: Mapping[str, Any], context: Mapping[str, Any]) -> float:
    status = str(context.get("tool_status") or "").lower()
    exit_code = context.get("exit_code")
    errored = _to_bool(context.get("tool_error"), default=False)
    if status in {"completed", "success", "ok"} and not errored and (exit_code in {None, 0, "0"}):
        return 0.9
    if status in {"completed", "success", "ok"} and not errored:
        return 0.75
    if status in {"failed", "error"} or errored:
        return 0.35
    return _clamp(_to_float(finding.get("confidence"), 0.6))


def _reproducibility(finding: Mapping[str, Any], context: Mapping[str, Any]) -> float:
    if _to_bool(finding.get("validated")) or _to_bool(finding.get("validated_vulnerability")):
        return 0.9
    if _to_bool(finding.get("reproducible")):
        return 0.85
    duplicate_count = int(_to_float(context.get("duplicate_count"), 1))
    if duplicate_count >= 2:
        return 0.75
    if finding.get("evidence_ref"):
        return 0.6
    return 0.45


def _evidence_completeness(finding: Mapping[str, Any]) -> float:
    keys = ("title", "target", "severity_hint", "source_tool", "evidence_ref")
    present = sum(1 for key in keys if str(finding.get(key) or "").strip())
    ratio = present / len(keys)
    return _clamp(0.25 + (0.75 * ratio))


def _exploit_confirmation(finding: Mapping[str, Any]) -> float:
    if _to_bool(finding.get("validated")) or _to_bool(finding.get("validated_vulnerability")):
        return 0.9
    if finding.get("proof_of_concept") or finding.get("poc") or finding.get("exploit_chain"):
        return 0.75
    return 0.2


def _duplication_risk(finding: Mapping[str, Any], context: Mapping[str, Any]) -> float:
    if context.get("duplication_risk") is not None:
        return _clamp(_to_float(context.get("duplication_risk"), 0.15))
    duplicate_count = int(_to_float(context.get("duplicate_count"), 1))
    if duplicate_count <= 1:
        return 0.15
    return _clamp(0.2 + ((duplicate_count - 1) * 0.2))


def _scope_validity(context: Mapping[str, Any]) -> float:
    if _to_bool(context.get("scope_valid"), default=True):
        return 1.0
    return 0.0


def _parser_integrity(context: Mapping[str, Any]) -> float:
    if _to_bool(context.get("parse_error"), default=False):
        return 0.2
    parsed_count = int(_to_float(context.get("parsed_items"), 0))
    if parsed_count > 0:
        return 0.9
    if _to_bool(context.get("parsed_ok"), default=False):
        return 0.75
    return 0.55


def _environment_stability(context: Mapping[str, Any]) -> float:
    if _to_bool(context.get("timeout"), default=False):
        return 0.2
    if _to_bool(context.get("tool_error"), default=False):
        return 0.45
    return _clamp(_to_float(context.get("environment_stability"), 0.85))


def assess_finding_confidence(
    *,
    finding: Mapping[str, Any],
    context: Mapping[str, Any] | None = None,
    threshold: float | None = None,
) -> ConfidenceAssessment:
    ctx = context or {}
    breakdown = ConfidenceBreakdown(
        tool_reliability=_tool_reliability(finding, ctx),
        reproducibility=_reproducibility(finding, ctx),
        evidence_completeness=_evidence_completeness(finding),
        exploit_confirmation=_exploit_confirmation(finding),
        duplication_risk=_duplication_risk(finding, ctx),
        scope_validity=_scope_validity(ctx),
        parser_integrity=_parser_integrity(ctx),
        environment_stability=_environment_stability(ctx),
    )

    weighted_sum = 0.0
    weighted_sum += breakdown.tool_reliability * _WEIGHTS["tool_reliability"]
    weighted_sum += breakdown.reproducibility * _WEIGHTS["reproducibility"]
    weighted_sum += breakdown.evidence_completeness * _WEIGHTS["evidence_completeness"]
    weighted_sum += breakdown.exploit_confirmation * _WEIGHTS["exploit_confirmation"]
    weighted_sum += (1.0 - breakdown.duplication_risk) * _WEIGHTS["duplication_inverse"]
    weighted_sum += breakdown.scope_validity * _WEIGHTS["scope_validity"]
    weighted_sum += breakdown.parser_integrity * _WEIGHTS["parser_integrity"]
    weighted_sum += breakdown.environment_stability * _WEIGHTS["environment_stability"]
    score = _clamp(weighted_sum)

    # If caller supplied explicit uncertain state, keep it authoritative.
    inferred_uncertain = (
        breakdown.evidence_completeness < 0.45
        or breakdown.parser_integrity < 0.5
        or breakdown.environment_stability < 0.5
        or breakdown.scope_validity <= 0.0
    )
    state_uncertain = _to_bool(ctx.get("state_uncertain"), default=inferred_uncertain)
    trigger = decide_validation_trigger(score, state_uncertain=state_uncertain, threshold=threshold)

    strengths = []
    if breakdown.tool_reliability >= 0.8:
        strengths.append("tool_reliability")
    if breakdown.parser_integrity >= 0.8:
        strengths.append("parser_integrity")
    if breakdown.scope_validity >= 1.0:
        strengths.append("scope_validity")
    weaknesses = []
    if breakdown.exploit_confirmation < 0.4:
        weaknesses.append("exploit_confirmation")
    if breakdown.duplication_risk > 0.5:
        weaknesses.append("duplication_risk")
    if breakdown.evidence_completeness < 0.5:
        weaknesses.append("evidence_completeness")
    explanation = (
        f"strengths={','.join(strengths) or 'none'}; "
        f"weaknesses={','.join(weaknesses) or 'none'}; "
        f"duplication_risk={breakdown.duplication_risk:.2f}"
    )

    return ConfidenceAssessment(
        confidence_score=round(score, 4),
        confidence_breakdown=breakdown,
        confidence_explanation=explanation,
        state_uncertain=state_uncertain,
        trigger_decision=trigger,
    )


def enrich_findings_with_confidence(
    *,
    run_id: str,
    findings: list[dict[str, Any]],
    context: Mapping[str, Any] | None = None,
    threshold: float | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not findings:
        return [], []

    key_counter: Counter[str] = Counter()
    for row in findings:
        key = f"{row.get('title','')}|{row.get('target','')}|{row.get('severity_hint','')}"
        key_counter[key] += 1

    enriched: list[dict[str, Any]] = []
    score_records: list[dict[str, Any]] = []
    for row in findings:
        mutable_row = dict(row)
        key = f"{mutable_row.get('title','')}|{mutable_row.get('target','')}|{mutable_row.get('severity_hint','')}"
        merged_context = dict(context or {})
        merged_context["duplicate_count"] = key_counter.get(key, 1)
        assessment = assess_finding_confidence(
            finding=mutable_row,
            context=merged_context,
            threshold=threshold,
        )

        mutable_row["confidence_score"] = assessment.confidence_score
        mutable_row["confidence_breakdown"] = assessment.confidence_breakdown.model_dump()
        mutable_row["confidence_explanation"] = assessment.confidence_explanation
        mutable_row["state_uncertain"] = assessment.state_uncertain
        mutable_row["trigger_decision"] = assessment.trigger_decision.model_dump()
        mutable_row["requires_validation"] = assessment.trigger_decision.requires_validation
        mutable_row["validation_reason"] = assessment.trigger_decision.reason
        enriched.append(mutable_row)

        source_tool = mutable_row.get("source_tool")
        score_records.append(
            assessment.persistence_record(
                run_id=run_id,
                source_tool=str(source_tool) if source_tool is not None else None,
                finding_key=key,
            )
        )
    return enriched, score_records

