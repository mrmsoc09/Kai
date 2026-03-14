from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .audit_events import record_transition_event
from .phase9_alert_case_service import Phase9AlertCaseService
from .phase10_retrospective_service import Phase10RetrospectiveService
from ..models.bug_bounty import (
    AdaptiveScheduleActionRecord,
    AnalystQueueItem,
    DuplicateRiskRecord,
    EvidenceCompletenessRecord,
    HuntScheduleJob,
    OpportunitySelectionRecord,
    SignalIntelligenceRecord,
    TargetYieldScoreRecord,
    VulnerabilityPredictionRecord,
    WorkflowRecommendationRecord,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _clamp(value: float, *, low: float, high: float) -> float:
    return max(low, min(high, value))


def _severity_weight(severity_hint: str | None) -> float:
    value = (severity_hint or "").strip().lower()
    return {
        "critical": 1.0,
        "high": 0.85,
        "medium": 0.6,
        "low": 0.35,
        "info": 0.15,
    }.get(value, 0.4)


def _duplicate_risk_band(score: float) -> str:
    if score >= 0.7:
        return "HIGH"
    if score >= 0.4:
        return "MEDIUM"
    return "LOW"


def _evidence_readiness(score: float) -> str:
    if score >= 0.8:
        return "READY_FOR_REPORT"
    if score >= 0.6:
        return "READY_FOR_REVIEW"
    if score >= 0.4:
        return "PARTIAL"
    return "INSUFFICIENT"


class Phase7PredictionService:
    """Deterministic vulnerability prediction and opportunity selection engine."""

    def __init__(self, db: AsyncSession):
        self.db = db

    def _score_evidence_completeness(
        self,
        queue_item: AnalystQueueItem,
    ) -> dict[str, Any]:
        score = 0.0
        missing: list[str] = []
        details = queue_item.details_json if isinstance(queue_item.details_json, dict) else {}

        if queue_item.evidence_summary:
            score += 0.30
        else:
            missing.append("evidence_summary")
        if queue_item.artifact_ref:
            score += 0.15
        else:
            missing.append("artifact_reference")
        if queue_item.affected_endpoint:
            score += 0.15
        else:
            missing.append("affected_endpoint")
        if queue_item.parameter:
            score += 0.10
        if details.get("reproduction"):
            score += 0.20
        else:
            missing.append("reproduction_notes")
        confidence = float(queue_item.confidence_score or 0.0)
        if confidence >= 0.75:
            score += 0.10
        elif confidence >= 0.5:
            score += 0.05
        else:
            missing.append("high_confidence_validation")

        score = _clamp(score, low=0.0, high=1.0)
        if score >= 0.8:
            readiness = "READY_FOR_REPORT"
        elif score >= 0.6:
            readiness = "READY_FOR_REVIEW"
        elif score >= 0.4:
            readiness = "PARTIAL"
        else:
            readiness = "INSUFFICIENT"
        return {
            "score": round(score, 4),
            "readiness_state": readiness,
            "missing_fields": missing,
            "reasoning_summary": (
                f"artifact={bool(queue_item.artifact_ref)} "
                f"endpoint={bool(queue_item.affected_endpoint)} "
                f"reproduction={bool(details.get('reproduction'))} "
                f"confidence={confidence:.2f}"
            ),
        }

    def _score_duplicate_risk(
        self,
        queue_item: AnalystQueueItem,
        *,
        prior_occurrences: int,
    ) -> dict[str, Any]:
        score = min(0.5, prior_occurrences * 0.14)
        hint = (queue_item.duplicate_risk_hint or "").strip().upper()
        if hint in {"HIGH", "ELEVATED"}:
            score += 0.30
        elif hint == "MEDIUM":
            score += 0.15

        novelty = float(queue_item.novelty_score or 0.5)
        score += (1.0 - _clamp(novelty, low=0.0, high=1.0)) * 0.25

        generic_types = {"missing_headers", "clickjacking", "banner_disclosure", "info_leak"}
        vuln = (queue_item.vulnerability_type or "").strip().lower()
        if vuln in generic_types:
            score += 0.10

        score = _clamp(score, low=0.0, high=1.0)
        if score >= 0.7:
            band = "HIGH"
        elif score >= 0.4:
            band = "MEDIUM"
        else:
            band = "LOW"
        return {
            "score": round(score, 4),
            "risk_band": band,
            "reasoning_summary": (
                f"prior_occurrences={prior_occurrences} hint={hint or 'none'} "
                f"novelty={novelty:.2f} vulnerability_type={vuln or 'unknown'}"
            ),
        }

    def _derive_target_yield(
        self,
        signals: list[SignalIntelligenceRecord],
        queue_items: list[AnalystQueueItem],
    ) -> dict[str, Any]:
        signal_density = _clamp(len(signals) / 40.0, low=0.0, high=1.0)
        novelty = _clamp(
            (
                sum(float(item.novelty_score or 0.0) for item in queue_items) / len(queue_items)
                if queue_items
                else 0.35
            ),
            low=0.0,
            high=1.0,
        )
        signal_types = {str(item.signal_type) for item in signals}
        coverage_quality = _clamp(len(signal_types) / 8.0, low=0.0, high=1.0)
        candidate_quality = _clamp(
            (
                sum(float(item.reportability_score or 0.0) for item in queue_items) / len(queue_items)
                if queue_items
                else 0.0
            ),
            low=0.0,
            high=1.0,
        )
        duplicate_penalty = _clamp(
            (
                sum(
                    1
                    for item in queue_items
                    if str(item.duplicate_risk_hint or "").strip().upper() in {"HIGH", "ELEVATED"}
                )
                / len(queue_items)
                if queue_items
                else 0.0
            ),
            low=0.0,
            high=1.0,
        )
        confidence = _clamp(
            (
                sum(float(item.confidence_score or 0.0) for item in signals) / len(signals)
                if signals
                else 0.0
            ),
            low=0.0,
            high=1.0,
        )
        composite = (
            (signal_density * 0.20)
            + (novelty * 0.15)
            + (coverage_quality * 0.20)
            + (candidate_quality * 0.25)
            + (confidence * 0.20)
            - (duplicate_penalty * 0.20)
        )
        yield_score = _clamp(composite * 100.0, low=0.0, high=100.0)
        return {
            "signal_density_score": round(signal_density, 4),
            "novelty_score": round(novelty, 4),
            "coverage_quality_score": round(coverage_quality, 4),
            "candidate_quality_score": round(candidate_quality, 4),
            "duplicate_penalty_score": round(duplicate_penalty, 4),
            "confidence_score": round(confidence, 4),
            "yield_score": round(yield_score, 3),
        }

    def _prediction_recommendation(
        self,
        *,
        vulnerability_type: str,
        duplicate_risk_score: float,
        evidence_completeness_score: float,
        reportability_score: float,
    ) -> tuple[str, str]:
        vuln = vulnerability_type.lower()
        if duplicate_risk_score >= 0.75:
            return "workflow_recon_surface_map", "deescalate_likely_duplicate"
        if evidence_completeness_score < 0.5:
            return "workflow_web_attack_surface", "collect_missing_evidence"
        if "secret" in vuln:
            return "workflow_secret_exposure_scan", "escalate_secret_validation"
        if reportability_score >= 0.8:
            return "workflow_quick_vuln_sweep", "route_to_manual_validation"
        return "workflow_priority_target_ranking", "monitor_and_triage"

    async def _apply_adaptive_effort_control(
        self,
        *,
        recommendation: WorkflowRecommendationRecord,
        actor: str,
    ) -> str:
        if recommendation.scope_target_id is None:
            recommendation.recommendation_status = "BLOCKED"
            self.db.add(
                AdaptiveScheduleActionRecord(
                    program_id=recommendation.program_id,
                    scope_target_id=None,
                    schedule_job_id=None,
                    opportunity_inference_id=None,
                    action_type="phase7_effort_control",
                    action_status="BLOCKED",
                    reason="scope_target_id missing for adaptive effort control",
                    details_json={"recommendation_id": str(recommendation.id)},
                    executed_at=_utcnow(),
                )
            )
            return "BLOCKED"

        schedule = await self.db.scalar(
            select(HuntScheduleJob).where(
                HuntScheduleJob.program_id == recommendation.program_id,
                HuntScheduleJob.scope_target_id == recommendation.scope_target_id,
                HuntScheduleJob.status == "ACTIVE",
            )
        )
        if schedule is None:
            recommendation.recommendation_status = "BLOCKED"
            self.db.add(
                AdaptiveScheduleActionRecord(
                    program_id=recommendation.program_id,
                    scope_target_id=recommendation.scope_target_id,
                    schedule_job_id=None,
                    opportunity_inference_id=None,
                    action_type="phase7_effort_control",
                    action_status="BLOCKED",
                    reason="no active schedule available for recommended target",
                    details_json={"recommendation_id": str(recommendation.id)},
                    executed_at=_utcnow(),
                )
            )
            return "BLOCKED"

        action = recommendation.recommended_action
        details: dict[str, Any] = {"recommendation_id": str(recommendation.id)}
        if action == "escalate_autonomous_effort":
            schedule.priority_tier = 1
            schedule.next_scheduled_run_at = _utcnow()
            details["priority_tier"] = 1
            recommendation.recommendation_status = "APPLIED"
            status = "APPLIED"
        elif action == "deescalate_autonomous_effort":
            schedule.priority_tier = max(int(schedule.priority_tier or 1), 4)
            schedule.next_scheduled_run_at = _utcnow().replace(microsecond=0)
            details["priority_tier"] = schedule.priority_tier
            recommendation.recommendation_status = "APPLIED"
            status = "APPLIED"
        else:
            recommendation.recommendation_status = "DEFERRED"
            status = "SKIPPED"

        schedule.updated_by = actor
        self.db.add(
            AdaptiveScheduleActionRecord(
                program_id=recommendation.program_id,
                scope_target_id=recommendation.scope_target_id,
                schedule_job_id=schedule.id,
                opportunity_inference_id=None,
                action_type="phase7_effort_control",
                action_status="APPLIED" if status == "APPLIED" else "SKIPPED",
                reason=f"phase7 recommendation: {action}",
                details_json=details,
                executed_at=_utcnow(),
            )
        )
        return status

    async def run_prediction_cycle(
        self,
        *,
        program_id: UUID | None,
        actor: str,
        apply_adaptive: bool,
    ) -> dict[str, int]:
        retrospective_service = Phase10RetrospectiveService(self.db)
        signal_stmt: Select[tuple[SignalIntelligenceRecord]] = select(SignalIntelligenceRecord)
        queue_stmt: Select[tuple[AnalystQueueItem]] = select(AnalystQueueItem)
        if program_id is not None:
            signal_stmt = signal_stmt.where(SignalIntelligenceRecord.program_id == program_id)
            queue_stmt = queue_stmt.where(AnalystQueueItem.program_id == program_id)
        signals = list((await self.db.execute(signal_stmt)).scalars().all())
        queue_items = list((await self.db.execute(queue_stmt)).scalars().all())

        signals_by_target: dict[tuple[UUID, UUID | None], list[SignalIntelligenceRecord]] = defaultdict(list)
        queue_by_target: dict[tuple[UUID, UUID | None], list[AnalystQueueItem]] = defaultdict(list)
        for signal in signals:
            signals_by_target[(signal.program_id, signal.scope_target_id)].append(signal)
        for item in queue_items:
            queue_by_target[(item.program_id, item.scope_target_id)].append(item)

        all_target_keys = set(signals_by_target.keys()) | set(queue_by_target.keys())

        target_yield_records: dict[tuple[UUID, UUID | None], TargetYieldScoreRecord] = {}
        selection_records: list[OpportunitySelectionRecord] = []
        recommendation_records: list[WorkflowRecommendationRecord] = []
        predictions_created = 0
        rankings_created = 0
        recommendations_created = 0
        yield_scores_created = 0
        duplicate_records_created = 0
        evidence_records_created = 0
        adaptive_actions_applied = 0
        modifier_cache: dict[tuple[UUID, UUID | None, str | None], dict[str, float | str]] = {}

        for key in all_target_keys:
            pid, scope_id = key
            target_signals = signals_by_target.get(key, [])
            target_queue = queue_by_target.get(key, [])
            target_workflow_template = (
                str(target_queue[0].workflow_template)
                if target_queue
                else None
            )
            target_modifier_key = (pid, scope_id, target_workflow_template)
            target_modifiers = modifier_cache.get(target_modifier_key)
            if target_modifiers is None:
                target_modifiers = await retrospective_service.get_scoring_modifiers(
                    program_id=pid,
                    scope_target_id=scope_id,
                    workflow_template=target_workflow_template,
                )
                modifier_cache[target_modifier_key] = target_modifiers
            yield_score = self._derive_target_yield(target_signals, target_queue)
            yield_score["yield_score"] = round(
                _clamp(
                    float(yield_score["yield_score"])
                    * float(target_modifiers["yield_multiplier"]),
                    low=0.0,
                    high=100.0,
                ),
                3,
            )
            yield_score["confidence_score"] = round(
                _clamp(
                    float(yield_score["confidence_score"])
                    + float(target_modifiers["confidence_adjustment"]),
                    low=0.0,
                    high=1.0,
                ),
                4,
            )
            workflow_run_id = (
                target_signals[0].workflow_run_id
                if target_signals
                else (target_queue[0].workflow_run_id if target_queue else None)
            )
            yield_record = TargetYieldScoreRecord(
                program_id=pid,
                scope_target_id=scope_id,
                workflow_run_id=workflow_run_id,
                signal_density_score=yield_score["signal_density_score"],
                novelty_score=yield_score["novelty_score"],
                coverage_quality_score=yield_score["coverage_quality_score"],
                candidate_quality_score=yield_score["candidate_quality_score"],
                duplicate_penalty_score=yield_score["duplicate_penalty_score"],
                confidence_score=yield_score["confidence_score"],
                yield_score=yield_score["yield_score"],
                details_json={
                    "signal_count": len(target_signals),
                    "candidate_count": len(target_queue),
                    "retrospective_modifiers": target_modifiers,
                },
                scored_at=_utcnow(),
            )
            self.db.add(yield_record)
            target_yield_records[key] = yield_record
            yield_scores_created += 1

            target_selection = OpportunitySelectionRecord(
                program_id=pid,
                scope_target_id=scope_id,
                workflow_run_id=workflow_run_id,
                analyst_queue_item_id=None,
                subject_type="TARGET",
                subject_key=str(scope_id) if scope_id else f"program:{pid}",
                selection_score=yield_score["yield_score"],
                confidence_score=yield_score["confidence_score"],
                duplicate_risk_score=yield_score["duplicate_penalty_score"],
                evidence_completeness_score=yield_score["candidate_quality_score"],
                reasoning_summary=(
                    f"yield={yield_score['yield_score']:.2f} "
                    f"signal_density={yield_score['signal_density_score']:.2f} "
                    f"candidate_quality={yield_score['candidate_quality_score']:.2f}"
                ),
                details_json=yield_score,
                scored_at=_utcnow(),
            )
            self.db.add(target_selection)
            selection_records.append(target_selection)
            rankings_created += 1

            action = (
                "escalate_autonomous_effort"
                if yield_score["yield_score"] >= 75
                else "deescalate_autonomous_effort"
                if yield_score["yield_score"] <= 25
                else "maintain_autonomous_effort"
            )
            workflow = (
                "workflow_quick_vuln_sweep"
                if yield_score["yield_score"] >= 75
                else "workflow_recon_surface_map"
            )
            target_reco = WorkflowRecommendationRecord(
                program_id=pid,
                scope_target_id=scope_id,
                workflow_run_id=workflow_run_id,
                analyst_queue_item_id=None,
                prediction_record_id=None,
                selection_record=target_selection,
                target_yield_score=yield_record,
                recommended_workflow=workflow,
                recommended_action=action,
                action_priority=1 if yield_score["yield_score"] >= 75 else 4,
                recommendation_status="PROPOSED",
                reasoning_summary=(
                    f"target_yield={yield_score['yield_score']:.2f} "
                    f"duplicate_penalty={yield_score['duplicate_penalty_score']:.2f}"
                ),
                supporting_record_ids_json=[],
                details_json={"phase": "phase7_target_effort_control"},
                recommended_at=_utcnow(),
            )
            self.db.add(target_reco)
            recommendation_records.append(target_reco)
            recommendations_created += 1

        for item in queue_items:
            prior_occurrences = int(
                (
                    await self.db.execute(
                        select(func.count(AnalystQueueItem.id)).where(
                            AnalystQueueItem.id != item.id,
                            AnalystQueueItem.program_id == item.program_id,
                            AnalystQueueItem.vulnerability_type == item.vulnerability_type,
                            AnalystQueueItem.affected_asset == item.affected_asset,
                        )
                    )
                ).scalar()
                or 0
            )
            duplicate = self._score_duplicate_risk(item, prior_occurrences=prior_occurrences)
            evidence = self._score_evidence_completeness(item)
            item_modifier_key = (
                item.program_id,
                item.scope_target_id,
                str(item.workflow_template),
            )
            item_modifiers = modifier_cache.get(item_modifier_key)
            if item_modifiers is None:
                item_modifiers = await retrospective_service.get_scoring_modifiers(
                    program_id=item.program_id,
                    scope_target_id=item.scope_target_id,
                    workflow_template=str(item.workflow_template),
                )
                modifier_cache[item_modifier_key] = item_modifiers

            adjusted_duplicate = _clamp(
                float(duplicate["score"]) * float(item_modifiers["duplicate_risk_multiplier"]),
                low=0.0,
                high=1.0,
            )
            duplicate["score"] = round(adjusted_duplicate, 4)
            duplicate["risk_band"] = _duplicate_risk_band(adjusted_duplicate)

            adjusted_evidence = _clamp(
                float(evidence["score"]) * float(item_modifiers["evidence_multiplier"]),
                low=0.0,
                high=1.0,
            )
            evidence["score"] = round(adjusted_evidence, 4)
            evidence["readiness_state"] = _evidence_readiness(adjusted_evidence)
            if adjusted_evidence >= 0.5:
                evidence["missing_fields"] = [
                    field
                    for field in evidence["missing_fields"]
                    if field not in {"artifact_reference", "affected_endpoint"}
                ]

            duplicate_record = DuplicateRiskRecord(
                program_id=item.program_id,
                scope_target_id=item.scope_target_id,
                workflow_run_id=item.workflow_run_id,
                analyst_queue_item_id=item.id,
                candidate_key=f"{item.affected_asset}:{item.vulnerability_type}",
                duplicate_risk_score=duplicate["score"],
                risk_band=duplicate["risk_band"],
                reasoning_summary=duplicate["reasoning_summary"],
                supporting_signal_ids_json=[],
                details_json={"prior_occurrences": prior_occurrences},
                assessed_at=_utcnow(),
            )
            self.db.add(duplicate_record)
            duplicate_records_created += 1

            evidence_record = EvidenceCompletenessRecord(
                program_id=item.program_id,
                scope_target_id=item.scope_target_id,
                workflow_run_id=item.workflow_run_id,
                analyst_queue_item_id=item.id,
                candidate_key=f"{item.affected_asset}:{item.vulnerability_type}",
                evidence_completeness_score=evidence["score"],
                readiness_state=evidence["readiness_state"],
                missing_fields_json=evidence["missing_fields"],
                reasoning_summary=evidence["reasoning_summary"],
                details_json={},
                assessed_at=_utcnow(),
            )
            self.db.add(evidence_record)
            evidence_records_created += 1

            confidence = _clamp(float(item.confidence_score or 0.0), low=0.0, high=1.0)
            novelty = _clamp(float(item.novelty_score or 0.4), low=0.0, high=1.0)
            base_reportability = _clamp(float(item.reportability_score or 0.0), low=0.0, high=1.0)
            severity = _severity_weight(item.severity_hint)
            reportability = _clamp(
                (
                    (base_reportability * 0.35)
                    + (confidence * 0.30)
                    + (severity * 0.20)
                    + (evidence["score"] * 0.15)
                    - (duplicate["score"] * 0.25)
                ),
                low=0.0,
                high=1.0,
            )
            reportability = _clamp(
                (
                    reportability * float(item_modifiers["opportunity_multiplier"])
                    + float(item_modifiers["confidence_adjustment"])
                ),
                low=0.0,
                high=1.0,
            )
            target_yield = target_yield_records.get((item.program_id, item.scope_target_id))
            target_boost = float(target_yield.yield_score if target_yield is not None else 0.0) / 100.0
            opportunity_score = _clamp(
                ((reportability * 0.75) + (target_boost * 0.25)) * 100.0,
                low=0.0,
                high=100.0,
            )
            recommended_workflow, action = self._prediction_recommendation(
                vulnerability_type=item.vulnerability_type,
                duplicate_risk_score=duplicate["score"],
                evidence_completeness_score=evidence["score"],
                reportability_score=reportability,
            )

            target_signals = signals_by_target.get((item.program_id, item.scope_target_id), [])
            prediction = VulnerabilityPredictionRecord(
                program_id=item.program_id,
                scope_target_id=item.scope_target_id,
                workflow_run_id=item.workflow_run_id,
                analyst_queue_item_id=item.id,
                predicted_vulnerability_type=item.vulnerability_type,
                confidence_score=round(confidence, 4),
                novelty_score=round(novelty, 4),
                duplicate_risk_score=duplicate["score"],
                reportability_score=round(reportability, 4),
                evidence_completeness_score=evidence["score"],
                opportunity_score=round(opportunity_score, 3),
                recommended_next_workflow=recommended_workflow,
                recommended_follow_up_action=action,
                reasoning_summary=(
                    f"confidence={confidence:.2f} novelty={novelty:.2f} "
                    f"duplicate={duplicate['score']:.2f} evidence={evidence['score']:.2f}"
                ),
                supporting_signal_ids_json=[str(signal.id) for signal in target_signals[:25]],
                details_json={
                    "severity_weight": severity,
                    "base_reportability": base_reportability,
                    "target_yield_score": float(target_boost * 100.0),
                    "retrospective_modifiers": item_modifiers,
                },
                predicted_at=_utcnow(),
            )
            self.db.add(prediction)
            predictions_created += 1

            candidate_selection_score = _clamp(
                reportability * (1.0 - (duplicate["score"] * 0.45)) * 100.0,
                low=0.0,
                high=100.0,
            )
            candidate_selection = OpportunitySelectionRecord(
                program_id=item.program_id,
                scope_target_id=item.scope_target_id,
                workflow_run_id=item.workflow_run_id,
                analyst_queue_item_id=item.id,
                subject_type="CANDIDATE",
                subject_key=str(item.id),
                selection_score=round(candidate_selection_score, 3),
                confidence_score=round(confidence, 4),
                duplicate_risk_score=duplicate["score"],
                evidence_completeness_score=evidence["score"],
                reasoning_summary=(
                    f"reportability={reportability:.2f} duplicate={duplicate['score']:.2f} "
                    f"evidence={evidence['score']:.2f}"
                ),
                details_json={"workflow_template": item.workflow_template},
                scored_at=_utcnow(),
            )
            self.db.add(candidate_selection)
            selection_records.append(candidate_selection)
            rankings_created += 1

            recommendation = WorkflowRecommendationRecord(
                program_id=item.program_id,
                scope_target_id=item.scope_target_id,
                workflow_run_id=item.workflow_run_id,
                analyst_queue_item_id=item.id,
                prediction_record=prediction,
                selection_record=candidate_selection,
                target_yield_score=target_yield,
                recommended_workflow=recommended_workflow,
                recommended_action=action,
                action_priority=1 if reportability >= 0.8 else 3,
                recommendation_status="PROPOSED",
                reasoning_summary=prediction.reasoning_summary,
                supporting_record_ids_json=[
                    f"duplicate:{item.id}",
                    f"evidence:{item.id}",
                ],
                details_json={"readiness_state": evidence["readiness_state"]},
                recommended_at=_utcnow(),
            )
            self.db.add(recommendation)
            recommendation_records.append(recommendation)
            recommendations_created += 1

        sorted_selections = sorted(
            selection_records,
            key=lambda record: float(record.selection_score or 0.0),
            reverse=True,
        )
        for index, record in enumerate(sorted_selections, start=1):
            record.priority_rank = index

        if apply_adaptive:
            await self.db.flush()
            for recommendation in recommendation_records:
                if recommendation.analyst_queue_item_id is not None:
                    continue
                if recommendation.recommended_action not in {
                    "escalate_autonomous_effort",
                    "deescalate_autonomous_effort",
                }:
                    continue
                outcome = await self._apply_adaptive_effort_control(
                    recommendation=recommendation,
                    actor=actor,
                )
                if outcome == "APPLIED":
                    adaptive_actions_applied += 1

        await self.db.flush()
        await Phase9AlertCaseService(self.db).sync_alerts(
            actor=actor,
            program_id=program_id,
            cooldown_minutes=120,
        )
        await record_transition_event(
            self.db,
            event_type="phase7.prediction.completed",
            actor=actor,
            message="Phase 7 prediction and opportunity selection completed",
            payload={
                "program_id": str(program_id) if program_id else None,
                "predictions_created": predictions_created,
                "rankings_created": rankings_created,
                "recommendations_created": recommendations_created,
                "yield_scores_created": yield_scores_created,
                "duplicate_records_created": duplicate_records_created,
                "evidence_records_created": evidence_records_created,
                "adaptive_actions_applied": adaptive_actions_applied,
            },
        )
        return {
            "predictions_created": predictions_created,
            "rankings_created": rankings_created,
            "recommendations_created": recommendations_created,
            "yield_scores_created": yield_scores_created,
            "duplicate_records_created": duplicate_records_created,
            "evidence_records_created": evidence_records_created,
            "adaptive_actions_applied": adaptive_actions_applied,
        }

    async def list_predictions(
        self,
        *,
        program_id: UUID | None,
        scope_target_id: UUID | None,
        limit: int,
    ) -> list[VulnerabilityPredictionRecord]:
        stmt: Select[tuple[VulnerabilityPredictionRecord]] = select(
            VulnerabilityPredictionRecord
        ).order_by(VulnerabilityPredictionRecord.predicted_at.desc())
        if program_id is not None:
            stmt = stmt.where(VulnerabilityPredictionRecord.program_id == program_id)
        if scope_target_id is not None:
            stmt = stmt.where(VulnerabilityPredictionRecord.scope_target_id == scope_target_id)
        stmt = stmt.limit(max(1, min(limit, 2000)))
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_opportunity_rankings(
        self,
        *,
        program_id: UUID | None,
        subject_type: str | None,
        limit: int,
    ) -> list[OpportunitySelectionRecord]:
        stmt: Select[tuple[OpportunitySelectionRecord]] = select(
            OpportunitySelectionRecord
        ).order_by(
            OpportunitySelectionRecord.priority_rank.asc().nullslast(),
            OpportunitySelectionRecord.selection_score.desc(),
        )
        if program_id is not None:
            stmt = stmt.where(OpportunitySelectionRecord.program_id == program_id)
        if subject_type:
            stmt = stmt.where(OpportunitySelectionRecord.subject_type == subject_type.upper())
        stmt = stmt.limit(max(1, min(limit, 2000)))
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_duplicate_risk(
        self,
        *,
        program_id: UUID | None,
        risk_band: str | None,
        limit: int,
    ) -> list[DuplicateRiskRecord]:
        stmt: Select[tuple[DuplicateRiskRecord]] = select(DuplicateRiskRecord).order_by(
            DuplicateRiskRecord.assessed_at.desc()
        )
        if program_id is not None:
            stmt = stmt.where(DuplicateRiskRecord.program_id == program_id)
        if risk_band:
            stmt = stmt.where(DuplicateRiskRecord.risk_band == risk_band.upper())
        stmt = stmt.limit(max(1, min(limit, 2000)))
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_evidence_completeness(
        self,
        *,
        program_id: UUID | None,
        readiness_state: str | None,
        limit: int,
    ) -> list[EvidenceCompletenessRecord]:
        stmt: Select[tuple[EvidenceCompletenessRecord]] = select(
            EvidenceCompletenessRecord
        ).order_by(EvidenceCompletenessRecord.assessed_at.desc())
        if program_id is not None:
            stmt = stmt.where(EvidenceCompletenessRecord.program_id == program_id)
        if readiness_state:
            stmt = stmt.where(
                EvidenceCompletenessRecord.readiness_state == readiness_state.upper()
            )
        stmt = stmt.limit(max(1, min(limit, 2000)))
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_recommendations(
        self,
        *,
        program_id: UUID | None,
        recommendation_status: str | None,
        limit: int,
    ) -> list[WorkflowRecommendationRecord]:
        stmt: Select[tuple[WorkflowRecommendationRecord]] = select(
            WorkflowRecommendationRecord
        ).order_by(WorkflowRecommendationRecord.recommended_at.desc())
        if program_id is not None:
            stmt = stmt.where(WorkflowRecommendationRecord.program_id == program_id)
        if recommendation_status:
            stmt = stmt.where(
                WorkflowRecommendationRecord.recommendation_status
                == recommendation_status.upper()
            )
        stmt = stmt.limit(max(1, min(limit, 2000)))
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_target_yields(
        self,
        *,
        program_id: UUID | None,
        scope_target_id: UUID | None,
        limit: int,
    ) -> list[TargetYieldScoreRecord]:
        stmt: Select[tuple[TargetYieldScoreRecord]] = select(TargetYieldScoreRecord).order_by(
            TargetYieldScoreRecord.scored_at.desc()
        )
        if program_id is not None:
            stmt = stmt.where(TargetYieldScoreRecord.program_id == program_id)
        if scope_target_id is not None:
            stmt = stmt.where(TargetYieldScoreRecord.scope_target_id == scope_target_id)
        stmt = stmt.limit(max(1, min(limit, 2000)))
        return list((await self.db.execute(stmt)).scalars().all())

    async def analyst_decision_support(
        self,
        *,
        program_id: UUID | None,
        limit: int,
    ) -> dict[str, Any]:
        predictions = await self.list_predictions(
            program_id=program_id,
            scope_target_id=None,
            limit=max(1, limit),
        )
        yields = await self.list_target_yields(
            program_id=program_id,
            scope_target_id=None,
            limit=max(1, limit),
        )
        recommendations = await self.list_recommendations(
            program_id=program_id,
            recommendation_status=None,
            limit=max(1, limit),
        )
        return {
            "generated_at": _utcnow().isoformat(),
            "top_predictions": [
                {
                    "prediction_id": str(item.id),
                    "program_id": str(item.program_id),
                    "scope_target_id": str(item.scope_target_id) if item.scope_target_id else None,
                    "predicted_vulnerability_type": item.predicted_vulnerability_type,
                    "reportability_score": item.reportability_score,
                    "duplicate_risk_score": item.duplicate_risk_score,
                    "evidence_completeness_score": item.evidence_completeness_score,
                    "recommended_next_workflow": item.recommended_next_workflow,
                    "recommended_follow_up_action": item.recommended_follow_up_action,
                }
                for item in predictions[:limit]
            ],
            "top_target_yields": [
                {
                    "yield_record_id": str(item.id),
                    "program_id": str(item.program_id),
                    "scope_target_id": str(item.scope_target_id) if item.scope_target_id else None,
                    "yield_score": item.yield_score,
                    "confidence_score": item.confidence_score,
                }
                for item in yields[:limit]
            ],
            "top_recommendations": [
                {
                    "recommendation_id": str(item.id),
                    "recommended_workflow": item.recommended_workflow,
                    "recommended_action": item.recommended_action,
                    "recommendation_status": item.recommendation_status,
                    "action_priority": item.action_priority,
                }
                for item in recommendations[:limit]
            ],
        }
