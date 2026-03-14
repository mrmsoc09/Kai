from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from .audit_events import record_transition_event
from ..models.bug_bounty import (
    AlertOutcomeRecord,
    AnalystCaseRecord,
    AnalystQueueItem,
    DecisionOutcomeRecord,
    EvidenceCompletenessRecord,
    FeedbackSignalRecord,
    NotificationAlertRecord,
    RecommendationOutcomeRecord,
    SignalIntelligenceRecord,
    TargetPerformanceRecord,
    WorkflowPerformanceRecord,
    WorkflowRecommendationRecord,
)
from ..models.workflow import WorkflowRun


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _clamp(value: float, *, low: float, high: float) -> float:
    return max(low, min(high, value))


def _ratio(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return numerator / denominator


class Phase10RetrospectiveService:
    """Retrospective learning service built on canonical Phase 5-9 records."""

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def _classify_case_outcome(case: AnalystCaseRecord) -> tuple[str, float]:
        status = str(case.status or "").strip().lower()
        closure = str(case.closure_reason or "").strip().lower()
        if status in {"submitted"}:
            return "reportable_vulnerability", 1.0
        if status in {"ready_for_report"}:
            return "reportable_vulnerability", 0.85
        if status == "duplicate" or "duplicate" in closure:
            return "duplicate_vulnerability", 0.25
        if status == "dismissed" or "false positive" in closure:
            return "dismissed_false_positive", 0.10
        if "informational" in closure:
            return "informational_finding", 0.35
        if "insufficient" in closure or "inconclusive" in closure:
            return "insufficient_evidence", 0.2
        if status == "closed":
            return "insufficient_evidence", 0.25
        return "unresolved_stale", 0.3

    @staticmethod
    def _recommendation_outcome(
        recommendation_status: str,
        *,
        linked_case_outcome: str | None,
    ) -> tuple[str, float]:
        status = str(recommendation_status or "").strip().upper()
        if status == "BLOCKED":
            return "BLOCKED", 0.10
        if status == "DEFERRED":
            return "ABANDONED", 0.20
        if status == "APPLIED":
            if linked_case_outcome == "reportable_vulnerability":
                return "SUCCEEDED", 1.0
            if linked_case_outcome in {"duplicate_vulnerability", "dismissed_false_positive"}:
                return "FAILED", 0.10
            return "USED", 0.70
        return "ABANDONED", 0.15

    @staticmethod
    def _alert_outcome(
        alert: NotificationAlertRecord,
        *,
        linked_case_outcome: str | None,
        now: datetime,
    ) -> tuple[str, bool, bool]:
        status = str(alert.status or "").strip().upper()
        age = now - (alert.last_seen_at or alert.created_at or now)
        if linked_case_outcome == "reportable_vulnerability":
            return "RESOLVED_ACTIONABLE", True, True
        if linked_case_outcome in {"duplicate_vulnerability", "dismissed_false_positive"}:
            return "RESOLVED_NOISE", True, False
        if status == "ACKNOWLEDGED":
            return "ACKNOWLEDGED", False, False
        if status == "RESOLVED":
            return "RESOLVED_NOISE", False, False
        if linked_case_outcome is not None:
            return "ESCALATED", True, False
        if age > timedelta(hours=36):
            return "IGNORED", False, False
        return "OPEN_TRACKING", False, False

    @staticmethod
    def _derive_scoring_modifiers(
        *,
        workflow_reportability_rate: float,
        workflow_noise_rate: float,
        target_reportability_rate: float,
        target_duplicate_rate: float,
        target_yield_score: float,
        recommendation_success_rate: float,
        alert_noise_rate: float,
    ) -> dict[str, float | str]:
        opportunity_multiplier = _clamp(
            1.0
            + ((workflow_reportability_rate - workflow_noise_rate) * 0.35)
            + ((target_reportability_rate - target_duplicate_rate) * 0.30)
            + ((recommendation_success_rate - 0.50) * 0.20)
            - ((alert_noise_rate - 0.30) * 0.15),
            low=0.75,
            high=1.35,
        )
        yield_multiplier = _clamp(
            1.0
            + (((target_yield_score / 100.0) - 0.5) * 0.40)
            + (workflow_reportability_rate * 0.20)
            - (workflow_noise_rate * 0.25),
            low=0.70,
            high=1.40,
        )
        duplicate_risk_multiplier = _clamp(
            1.0
            + (target_duplicate_rate * 0.50)
            + (workflow_noise_rate * 0.35)
            + (alert_noise_rate * 0.25)
            - (recommendation_success_rate * 0.20),
            low=0.75,
            high=1.65,
        )
        evidence_multiplier = _clamp(
            1.0 + ((recommendation_success_rate - 0.50) * 0.35) - (alert_noise_rate * 0.15),
            low=0.80,
            high=1.30,
        )
        confidence_adjustment = _clamp(
            (recommendation_success_rate - workflow_noise_rate - (alert_noise_rate * 0.5)) * 0.18,
            low=-0.20,
            high=0.20,
        )
        return {
            "opportunity_multiplier": round(opportunity_multiplier, 4),
            "yield_multiplier": round(yield_multiplier, 4),
            "duplicate_risk_multiplier": round(duplicate_risk_multiplier, 4),
            "evidence_multiplier": round(evidence_multiplier, 4),
            "confidence_adjustment": round(confidence_adjustment, 4),
            "reasoning_summary": (
                "workflow_reportability="
                f"{workflow_reportability_rate:.3f} workflow_noise={workflow_noise_rate:.3f} "
                f"target_reportability={target_reportability_rate:.3f} target_duplicate={target_duplicate_rate:.3f} "
                f"target_yield={target_yield_score:.2f} recommendation_success={recommendation_success_rate:.3f} "
                f"alert_noise={alert_noise_rate:.3f}"
            ),
        }

    async def _record_exists(
        self,
        model: Any,
        predicate: Any,
    ) -> bool:
        return (
            await self.db.scalar(select(model.id).where(predicate).limit(1)) is not None
        )

    async def run_retrospective(
        self,
        *,
        actor: str,
        program_id: UUID | None,
        window_days: int,
    ) -> dict[str, int]:
        now = _utcnow()
        window_end = now
        window_start = now - timedelta(days=max(1, window_days))

        case_stmt: Select[tuple[AnalystCaseRecord]] = select(AnalystCaseRecord).where(
            AnalystCaseRecord.updated_at >= window_start
        )
        alert_stmt: Select[tuple[NotificationAlertRecord]] = select(
            NotificationAlertRecord
        ).where(NotificationAlertRecord.last_seen_at >= window_start)
        recommendation_stmt: Select[tuple[WorkflowRecommendationRecord]] = select(
            WorkflowRecommendationRecord
        ).where(WorkflowRecommendationRecord.recommended_at >= window_start)
        queue_stmt: Select[tuple[AnalystQueueItem]] = select(AnalystQueueItem).where(
            AnalystQueueItem.updated_at >= window_start
        )
        signal_stmt: Select[tuple[SignalIntelligenceRecord]] = select(
            SignalIntelligenceRecord
        ).where(SignalIntelligenceRecord.observed_at >= window_start)
        evidence_stmt: Select[tuple[EvidenceCompletenessRecord]] = select(
            EvidenceCompletenessRecord
        ).where(EvidenceCompletenessRecord.assessed_at >= window_start)
        workflow_stmt: Select[tuple[WorkflowRun]] = select(WorkflowRun).where(
            WorkflowRun.created_at >= window_start
        )

        if program_id is not None:
            case_stmt = case_stmt.where(AnalystCaseRecord.program_id == program_id)
            alert_stmt = alert_stmt.where(NotificationAlertRecord.program_id == program_id)
            recommendation_stmt = recommendation_stmt.where(
                WorkflowRecommendationRecord.program_id == program_id
            )
            queue_stmt = queue_stmt.where(AnalystQueueItem.program_id == program_id)
            evidence_stmt = evidence_stmt.where(EvidenceCompletenessRecord.program_id == program_id)
            signal_stmt = signal_stmt.where(SignalIntelligenceRecord.program_id == program_id)

        cases = list((await self.db.execute(case_stmt)).scalars().all())
        alerts = list((await self.db.execute(alert_stmt)).scalars().all())
        recommendations = list((await self.db.execute(recommendation_stmt)).scalars().all())
        queue_items = list((await self.db.execute(queue_stmt)).scalars().all())
        evidence_records = list((await self.db.execute(evidence_stmt)).scalars().all())
        workflow_runs = list((await self.db.execute(workflow_stmt)).scalars().all())
        signals = list((await self.db.execute(signal_stmt)).scalars().all())

        queue_by_id = {item.id: item for item in queue_items}
        workflow_by_id = {item.id: item for item in workflow_runs}
        evidence_by_queue: dict[UUID, EvidenceCompletenessRecord] = {}
        for record in evidence_records:
            if record.analyst_queue_item_id is None:
                continue
            prior = evidence_by_queue.get(record.analyst_queue_item_id)
            if prior is None or (record.assessed_at or now) > (prior.assessed_at or now):
                evidence_by_queue[record.analyst_queue_item_id] = record

        case_outcome_by_case_id: dict[UUID, str] = {}
        case_by_alert_id: dict[UUID, AnalystCaseRecord] = {}
        case_by_recommendation_id: dict[UUID, AnalystCaseRecord] = {}

        feedback_signals_recorded = 0
        decision_outcomes_recorded = 0
        recommendation_outcomes_recorded = 0
        alert_outcomes_recorded = 0
        workflow_performance_records_created = 0
        target_performance_records_created = 0

        for case in cases:
            classification, confidence = self._classify_case_outcome(case)
            case_outcome_by_case_id[case.id] = classification
            if case.alert_id:
                case_by_alert_id[case.alert_id] = case
            if case.recommendation_record_id:
                case_by_recommendation_id[case.recommendation_record_id] = case

            decision_fp = f"case:{case.id}:{case.status}:{case.updated_at.isoformat()}"
            if not await self._record_exists(
                DecisionOutcomeRecord,
                DecisionOutcomeRecord.outcome_fingerprint == decision_fp,
            ):
                self.db.add(
                    DecisionOutcomeRecord(
                        program_id=case.program_id,
                        scope_target_id=case.scope_target_id,
                        workflow_run_id=case.workflow_run_id,
                        analyst_case_id=case.id,
                        alert_id=case.alert_id,
                        recommendation_record_id=case.recommendation_record_id,
                        decision_type="CASE",
                        decision_status=str(case.status or ""),
                        outcome_classification=classification,
                        decided_by=case.last_actor,
                        reasoning_summary=case.reasoning_summary,
                        outcome_fingerprint=decision_fp,
                        details_json={
                            "priority": case.priority,
                            "closure_reason": case.closure_reason,
                        },
                        decided_at=case.updated_at or now,
                    )
                )
                decision_outcomes_recorded += 1

            signal_fp = f"feedback:case:{case.id}:{classification}:{case.updated_at.isoformat()}"
            if not await self._record_exists(
                FeedbackSignalRecord,
                FeedbackSignalRecord.signal_fingerprint == signal_fp,
            ):
                evidence_record = (
                    evidence_by_queue.get(case.analyst_queue_item_id)
                    if case.analyst_queue_item_id
                    else None
                )
                self.db.add(
                    FeedbackSignalRecord(
                        program_id=case.program_id,
                        scope_target_id=case.scope_target_id,
                        workflow_run_id=case.workflow_run_id,
                        analyst_case_id=case.id,
                        alert_id=case.alert_id,
                        analyst_queue_item_id=case.analyst_queue_item_id,
                        recommendation_record_id=case.recommendation_record_id,
                        source_entity_type="CASE",
                        source_entity_id=str(case.id),
                        outcome_classification=classification,
                        confidence_score=confidence,
                        reasoning_summary=case.reasoning_summary,
                        signal_fingerprint=signal_fp,
                        details_json={
                            "status": case.status,
                            "priority": case.priority,
                            "evidence_completeness_at_closure": (
                                float(evidence_record.evidence_completeness_score)
                                if evidence_record
                                else None
                            ),
                        },
                        observed_at=case.updated_at or now,
                    )
                )
                feedback_signals_recorded += 1

        for recommendation in recommendations:
            linked_case = case_by_recommendation_id.get(recommendation.id)
            linked_outcome = (
                case_outcome_by_case_id.get(linked_case.id)
                if linked_case is not None
                else None
            )
            outcome_status, success_score = self._recommendation_outcome(
                recommendation.recommendation_status,
                linked_case_outcome=linked_outcome,
            )
            fp = (
                "recommendation:"
                f"{recommendation.id}:{recommendation.recommendation_status}:{outcome_status}:"
                f"{linked_case.id if linked_case else 'none'}"
            )
            if not await self._record_exists(
                RecommendationOutcomeRecord,
                RecommendationOutcomeRecord.outcome_fingerprint == fp,
            ):
                self.db.add(
                    RecommendationOutcomeRecord(
                        program_id=recommendation.program_id,
                        recommendation_record_id=recommendation.id,
                        scope_target_id=recommendation.scope_target_id,
                        workflow_run_id=recommendation.workflow_run_id,
                        analyst_case_id=linked_case.id if linked_case else None,
                        outcome_status=outcome_status,
                        success_score=success_score,
                        reasoning_summary=recommendation.reasoning_summary,
                        outcome_fingerprint=fp,
                        details_json={
                            "recommendation_status": recommendation.recommendation_status,
                            "recommended_workflow": recommendation.recommended_workflow,
                            "recommended_action": recommendation.recommended_action,
                        },
                        decided_at=recommendation.updated_at or now,
                    )
                )
                recommendation_outcomes_recorded += 1

            decision_fp = f"decision:recommendation:{recommendation.id}:{outcome_status}:{recommendation.updated_at.isoformat()}"
            if not await self._record_exists(
                DecisionOutcomeRecord,
                DecisionOutcomeRecord.outcome_fingerprint == decision_fp,
            ):
                self.db.add(
                    DecisionOutcomeRecord(
                        program_id=recommendation.program_id,
                        scope_target_id=recommendation.scope_target_id,
                        workflow_run_id=recommendation.workflow_run_id,
                        analyst_case_id=linked_case.id if linked_case else None,
                        alert_id=linked_case.alert_id if linked_case else None,
                        recommendation_record_id=recommendation.id,
                        decision_type="RECOMMENDATION",
                        decision_status=recommendation.recommendation_status,
                        outcome_classification=outcome_status.lower(),
                        decided_by=linked_case.last_actor if linked_case else None,
                        reasoning_summary=recommendation.reasoning_summary,
                        outcome_fingerprint=decision_fp,
                        details_json={},
                        decided_at=recommendation.updated_at or now,
                    )
                )
                decision_outcomes_recorded += 1

        for alert in alerts:
            linked_case = case_by_alert_id.get(alert.id)
            linked_outcome = (
                case_outcome_by_case_id.get(linked_case.id)
                if linked_case is not None
                else None
            )
            outcome_status, led_to_case, led_to_reportable = self._alert_outcome(
                alert,
                linked_case_outcome=linked_outcome,
                now=now,
            )
            if alert.acknowledged_at and alert.first_seen_at:
                latency = int((alert.acknowledged_at - alert.first_seen_at).total_seconds())
                ack_latency = max(latency, 0)
            else:
                ack_latency = None

            fp = (
                f"alert:{alert.id}:{alert.status}:{outcome_status}:"
                f"{linked_case.id if linked_case else 'none'}"
            )
            if not await self._record_exists(
                AlertOutcomeRecord,
                AlertOutcomeRecord.outcome_fingerprint == fp,
            ):
                self.db.add(
                    AlertOutcomeRecord(
                        program_id=alert.program_id,
                        alert_id=alert.id,
                        scope_target_id=alert.scope_target_id,
                        analyst_case_id=linked_case.id if linked_case else None,
                        outcome_status=outcome_status,
                        acknowledgement_latency_seconds=ack_latency,
                        led_to_case=led_to_case,
                        led_to_reportable=led_to_reportable,
                        reasoning_summary=alert.reasoning_summary,
                        outcome_fingerprint=fp,
                        details_json={"alert_status": alert.status},
                        evaluated_at=alert.updated_at or now,
                    )
                )
                alert_outcomes_recorded += 1

            decision_fp = f"decision:alert:{alert.id}:{outcome_status}:{alert.updated_at.isoformat()}"
            if not await self._record_exists(
                DecisionOutcomeRecord,
                DecisionOutcomeRecord.outcome_fingerprint == decision_fp,
            ):
                self.db.add(
                    DecisionOutcomeRecord(
                        program_id=alert.program_id,
                        scope_target_id=alert.scope_target_id,
                        workflow_run_id=alert.workflow_run_id,
                        analyst_case_id=linked_case.id if linked_case else None,
                        alert_id=alert.id,
                        recommendation_record_id=alert.recommendation_record_id,
                        decision_type="ALERT",
                        decision_status=alert.status,
                        outcome_classification=outcome_status.lower(),
                        decided_by=alert.acknowledged_by or alert.resolved_by,
                        reasoning_summary=alert.reasoning_summary,
                        outcome_fingerprint=decision_fp,
                        details_json={"urgency": alert.urgency, "severity": alert.severity},
                        decided_at=alert.updated_at or now,
                    )
                )
                decision_outcomes_recorded += 1

            signal_fp = f"feedback:alert:{alert.id}:{outcome_status}:{alert.updated_at.isoformat()}"
            if not await self._record_exists(
                FeedbackSignalRecord,
                FeedbackSignalRecord.signal_fingerprint == signal_fp,
            ):
                self.db.add(
                    FeedbackSignalRecord(
                        program_id=alert.program_id,
                        scope_target_id=alert.scope_target_id,
                        workflow_run_id=alert.workflow_run_id,
                        analyst_case_id=linked_case.id if linked_case else None,
                        alert_id=alert.id,
                        analyst_queue_item_id=alert.analyst_queue_item_id,
                        recommendation_record_id=alert.recommendation_record_id,
                        source_entity_type="ALERT",
                        source_entity_id=str(alert.id),
                        outcome_classification=outcome_status.lower(),
                        confidence_score=1.0 if led_to_reportable else 0.4,
                        reasoning_summary=alert.reasoning_summary,
                        signal_fingerprint=signal_fp,
                        details_json={"status": alert.status},
                        observed_at=alert.updated_at or now,
                    )
                )
                feedback_signals_recorded += 1

        case_classification_counts: dict[UUID, dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        cases_by_template: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        template_program_sources: dict[str, UUID] = {}

        for case in cases:
            classification = case_outcome_by_case_id.get(case.id, "unresolved_stale")
            key_program = case.program_id
            case_classification_counts[key_program][classification] += 1

            template_name = "unknown"
            if case.analyst_queue_item_id and case.analyst_queue_item_id in queue_by_id:
                template_name = str(queue_by_id[case.analyst_queue_item_id].workflow_template or "unknown")
            elif case.workflow_run_id and case.workflow_run_id in workflow_by_id:
                template_name = str(workflow_by_id[case.workflow_run_id].template_name or "unknown")
            template_program_sources.setdefault(template_name, case.program_id)
            cases_by_template[template_name]["cases"] += 1
            if classification == "reportable_vulnerability":
                cases_by_template[template_name]["reportable"] += 1
            elif classification == "duplicate_vulnerability":
                cases_by_template[template_name]["duplicate"] += 1
            elif classification == "dismissed_false_positive":
                cases_by_template[template_name]["dismissed"] += 1

        signals_by_template: dict[str, int] = defaultdict(int)
        signals_by_target: dict[tuple[UUID, UUID | None], int] = defaultdict(int)
        for signal in signals:
            template_name = (
                str(workflow_by_id[signal.workflow_run_id].template_name)
                if signal.workflow_run_id and signal.workflow_run_id in workflow_by_id
                else "unknown"
            )
            signals_by_template[template_name] += 1
            signals_by_target[(signal.program_id, signal.scope_target_id)] += 1

        queue_counts_by_template: dict[str, int] = defaultdict(int)
        for queue_item in queue_items:
            template_name = str(queue_item.workflow_template or "unknown")
            queue_counts_by_template[template_name] += 1
            template_program_sources.setdefault(template_name, queue_item.program_id)

        all_templates = set(cases_by_template.keys()) | set(signals_by_template.keys()) | set(queue_counts_by_template.keys())
        program_for_template: dict[str, UUID | None] = {
            template_name: template_program_sources.get(template_name, program_id)
            for template_name in all_templates
        }

        for template_name in sorted(all_templates):
            program_for_record = program_for_template.get(template_name)
            if program_for_record is None:
                continue
            cases_created = int(cases_by_template[template_name].get("cases", 0))
            reportable = int(cases_by_template[template_name].get("reportable", 0))
            duplicate = int(cases_by_template[template_name].get("duplicate", 0))
            dismissed = int(cases_by_template[template_name].get("dismissed", 0))
            candidates = int(queue_counts_by_template.get(template_name, 0))
            signals_generated = int(signals_by_template.get(template_name, 0))

            reportability_rate = _clamp(_ratio(reportable, cases_created), low=0.0, high=1.0)
            noise_rate = _clamp(_ratio(duplicate + dismissed, cases_created), low=0.0, high=1.0)
            signal_value = _clamp(
                (
                    (signals_generated * 0.2)
                    + (candidates * 0.6)
                    + (reportable * 1.5)
                    - (duplicate * 0.8)
                    - (dismissed * 0.6)
                )
                * 5.0,
                low=0.0,
                high=100.0,
            )

            self.db.add(
                WorkflowPerformanceRecord(
                    program_id=program_for_record,
                    workflow_template=template_name,
                    window_start=window_start,
                    window_end=window_end,
                    signals_generated=signals_generated,
                    candidates_produced=candidates,
                    cases_created=cases_created,
                    reportable_outcomes=reportable,
                    duplicate_outcomes=duplicate,
                    dismissed_outcomes=dismissed,
                    workflow_signal_value=round(signal_value, 4),
                    workflow_reportability_rate=round(reportability_rate, 4),
                    workflow_noise_rate=round(noise_rate, 4),
                    details_json={"window_days": window_days},
                    computed_at=now,
                )
            )
            workflow_performance_records_created += 1

        target_cases: dict[tuple[UUID, UUID | None], list[AnalystCaseRecord]] = defaultdict(list)
        for case in cases:
            target_cases[(case.program_id, case.scope_target_id)].append(case)
        target_queue: dict[tuple[UUID, UUID | None], list[AnalystQueueItem]] = defaultdict(list)
        for queue_item in queue_items:
            target_queue[(queue_item.program_id, queue_item.scope_target_id)].append(queue_item)
        target_keys = set(target_cases.keys()) | set(target_queue.keys())

        for program_target_key in sorted(target_keys, key=lambda item: (str(item[0]), str(item[1]))):
            pid, scope_id = program_target_key
            scoped_cases = target_cases.get(program_target_key, [])
            scoped_queue = target_queue.get(program_target_key, [])
            signal_count = int(signals_by_target.get(program_target_key, 0))
            candidate_count = len(scoped_queue)
            case_count = len(scoped_cases)
            reportable_count = 0
            duplicate_count = 0
            dismissed_count = 0
            for case in scoped_cases:
                classification = case_outcome_by_case_id.get(case.id, "unresolved_stale")
                if classification == "reportable_vulnerability":
                    reportable_count += 1
                elif classification == "duplicate_vulnerability":
                    duplicate_count += 1
                elif classification == "dismissed_false_positive":
                    dismissed_count += 1

            target_signal_rate = _clamp(signal_count / 50.0, low=0.0, high=1.0)
            target_duplicate_rate = _clamp(
                _ratio(duplicate_count, case_count),
                low=0.0,
                high=1.0,
            )
            target_reportability_rate = _clamp(
                _ratio(reportable_count, case_count),
                low=0.0,
                high=1.0,
            )
            target_yield_score = _clamp(
                (
                    (target_reportability_rate * 70.0)
                    + (target_signal_rate * 20.0)
                    + min(candidate_count, 10)
                    - (target_duplicate_rate * 30.0)
                ),
                low=0.0,
                high=100.0,
            )
            self.db.add(
                TargetPerformanceRecord(
                    program_id=pid,
                    scope_target_id=scope_id,
                    window_start=window_start,
                    window_end=window_end,
                    signal_count=signal_count,
                    candidate_count=candidate_count,
                    case_count=case_count,
                    reportable_count=reportable_count,
                    duplicate_count=duplicate_count,
                    dismissed_count=dismissed_count,
                    target_signal_rate=round(target_signal_rate, 4),
                    target_duplicate_rate=round(target_duplicate_rate, 4),
                    target_reportability_rate=round(target_reportability_rate, 4),
                    target_yield_score=round(target_yield_score, 4),
                    details_json={"window_days": window_days},
                    computed_at=now,
                )
            )
            target_performance_records_created += 1

        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="phase10.retrospective.completed",
            actor=actor,
            message="Phase 10 retrospective feedback computation completed",
            payload={
                "program_id": str(program_id) if program_id else None,
                "window_days": window_days,
                "feedback_signals_recorded": feedback_signals_recorded,
                "decision_outcomes_recorded": decision_outcomes_recorded,
                "workflow_performance_records_created": workflow_performance_records_created,
                "target_performance_records_created": target_performance_records_created,
                "recommendation_outcomes_recorded": recommendation_outcomes_recorded,
                "alert_outcomes_recorded": alert_outcomes_recorded,
            },
        )
        return {
            "feedback_signals_recorded": feedback_signals_recorded,
            "decision_outcomes_recorded": decision_outcomes_recorded,
            "workflow_performance_records_created": workflow_performance_records_created,
            "target_performance_records_created": target_performance_records_created,
            "recommendation_outcomes_recorded": recommendation_outcomes_recorded,
            "alert_outcomes_recorded": alert_outcomes_recorded,
        }

    async def list_workflow_performance(
        self,
        *,
        program_id: UUID | None,
        limit: int,
    ) -> list[WorkflowPerformanceRecord]:
        stmt: Select[tuple[WorkflowPerformanceRecord]] = select(
            WorkflowPerformanceRecord
        ).order_by(WorkflowPerformanceRecord.computed_at.desc())
        if program_id is not None:
            stmt = stmt.where(WorkflowPerformanceRecord.program_id == program_id)
        stmt = stmt.limit(max(1, min(limit, 2000)))
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_target_performance(
        self,
        *,
        program_id: UUID | None,
        scope_target_id: UUID | None,
        limit: int,
    ) -> list[TargetPerformanceRecord]:
        stmt: Select[tuple[TargetPerformanceRecord]] = select(
            TargetPerformanceRecord
        ).order_by(TargetPerformanceRecord.computed_at.desc())
        if program_id is not None:
            stmt = stmt.where(TargetPerformanceRecord.program_id == program_id)
        if scope_target_id is not None:
            stmt = stmt.where(TargetPerformanceRecord.scope_target_id == scope_target_id)
        stmt = stmt.limit(max(1, min(limit, 2000)))
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_recommendation_outcomes(
        self,
        *,
        program_id: UUID | None,
        outcome_status: str | None,
        limit: int,
    ) -> list[RecommendationOutcomeRecord]:
        stmt: Select[tuple[RecommendationOutcomeRecord]] = select(
            RecommendationOutcomeRecord
        ).order_by(RecommendationOutcomeRecord.decided_at.desc())
        if program_id is not None:
            stmt = stmt.where(RecommendationOutcomeRecord.program_id == program_id)
        if outcome_status:
            stmt = stmt.where(
                RecommendationOutcomeRecord.outcome_status == outcome_status.upper()
            )
        stmt = stmt.limit(max(1, min(limit, 2000)))
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_alert_outcomes(
        self,
        *,
        program_id: UUID | None,
        outcome_status: str | None,
        limit: int,
    ) -> list[AlertOutcomeRecord]:
        stmt: Select[tuple[AlertOutcomeRecord]] = select(AlertOutcomeRecord).order_by(
            AlertOutcomeRecord.evaluated_at.desc()
        )
        if program_id is not None:
            stmt = stmt.where(AlertOutcomeRecord.program_id == program_id)
        if outcome_status:
            stmt = stmt.where(AlertOutcomeRecord.outcome_status == outcome_status.upper())
        stmt = stmt.limit(max(1, min(limit, 2000)))
        return list((await self.db.execute(stmt)).scalars().all())

    async def summary(
        self,
        *,
        program_id: UUID | None,
        window_days: int,
    ) -> dict[str, Any]:
        now = _utcnow()
        window_start = now - timedelta(days=max(1, window_days))
        workflow_stmt: Select[tuple[WorkflowPerformanceRecord]] = select(
            WorkflowPerformanceRecord
        ).where(WorkflowPerformanceRecord.window_end >= window_start)
        target_stmt: Select[tuple[TargetPerformanceRecord]] = select(TargetPerformanceRecord).where(
            TargetPerformanceRecord.window_end >= window_start
        )
        rec_stmt: Select[tuple[RecommendationOutcomeRecord]] = select(
            RecommendationOutcomeRecord
        ).where(RecommendationOutcomeRecord.decided_at >= window_start)
        alert_stmt: Select[tuple[AlertOutcomeRecord]] = select(AlertOutcomeRecord).where(
            AlertOutcomeRecord.evaluated_at >= window_start
        )
        if program_id is not None:
            workflow_stmt = workflow_stmt.where(WorkflowPerformanceRecord.program_id == program_id)
            target_stmt = target_stmt.where(TargetPerformanceRecord.program_id == program_id)
            rec_stmt = rec_stmt.where(RecommendationOutcomeRecord.program_id == program_id)
            alert_stmt = alert_stmt.where(AlertOutcomeRecord.program_id == program_id)

        workflow_rows = list((await self.db.execute(workflow_stmt)).scalars().all())
        target_rows = list((await self.db.execute(target_stmt)).scalars().all())
        recommendation_rows = list((await self.db.execute(rec_stmt)).scalars().all())
        alert_rows = list((await self.db.execute(alert_stmt)).scalars().all())

        by_program: dict[UUID, list[float]] = defaultdict(list)
        for row in target_rows:
            by_program[row.program_id].append(float(row.target_yield_score or 0.0))
        top_programs = sorted(
            (
                {
                    "program_id": str(program),
                    "avg_target_yield_score": round(sum(scores) / max(1, len(scores)), 4),
                    "target_records": len(scores),
                }
                for program, scores in by_program.items()
            ),
            key=lambda item: item["avg_target_yield_score"],
            reverse=True,
        )[:20]

        top_targets = [
            {
                "target_performance_id": str(row.id),
                "program_id": str(row.program_id),
                "scope_target_id": str(row.scope_target_id) if row.scope_target_id else None,
                "target_yield_score": float(row.target_yield_score or 0.0),
                "target_reportability_rate": float(row.target_reportability_rate or 0.0),
                "target_duplicate_rate": float(row.target_duplicate_rate or 0.0),
            }
            for row in sorted(
                target_rows,
                key=lambda item: float(item.target_yield_score or 0.0),
                reverse=True,
            )[:30]
        ]

        workflow_value_leaders = [
            {
                "workflow_performance_id": str(row.id),
                "program_id": str(row.program_id),
                "workflow_template": row.workflow_template,
                "workflow_signal_value": float(row.workflow_signal_value or 0.0),
                "workflow_reportability_rate": float(row.workflow_reportability_rate or 0.0),
                "workflow_noise_rate": float(row.workflow_noise_rate or 0.0),
            }
            for row in sorted(
                workflow_rows,
                key=lambda item: float(item.workflow_signal_value or 0.0),
                reverse=True,
            )[:30]
        ]

        alert_total = len(alert_rows)
        ignored_count = sum(1 for row in alert_rows if row.outcome_status == "IGNORED")
        resolved_noise_count = sum(
            1 for row in alert_rows if row.outcome_status == "RESOLVED_NOISE"
        )
        actionable_count = sum(
            1 for row in alert_rows if row.outcome_status == "RESOLVED_ACTIONABLE"
        )

        recommendation_total = len(recommendation_rows)
        success_weight = 0.0
        status_counts: dict[str, int] = defaultdict(int)
        for row in recommendation_rows:
            status = str(row.outcome_status or "UNKNOWN").upper()
            status_counts[status] += 1
            if status == "SUCCEEDED":
                success_weight += 1.0
            elif status == "USED":
                success_weight += 0.75
            elif status == "ABANDONED":
                success_weight += 0.2
            elif status == "BLOCKED":
                success_weight += 0.1
            elif status == "FAILED":
                success_weight += 0.05

        return {
            "generated_at": now.isoformat(),
            "window_days": window_days,
            "top_programs": top_programs,
            "top_targets": top_targets,
            "workflow_value_leaders": workflow_value_leaders,
            "alert_noise_summary": {
                "total_alert_outcomes": alert_total,
                "ignored_alerts": ignored_count,
                "resolved_noise_alerts": resolved_noise_count,
                "actionable_alerts": actionable_count,
                "noise_rate": round(
                    _ratio(ignored_count + resolved_noise_count, alert_total),
                    4,
                ),
            },
            "recommendation_success_summary": {
                "total_recommendation_outcomes": recommendation_total,
                "status_counts": dict(status_counts),
                "weighted_success_rate": round(
                    _ratio(int(success_weight * 1000), recommendation_total * 1000),
                    4,
                ),
            },
        }

    async def get_scoring_modifiers(
        self,
        *,
        program_id: UUID,
        scope_target_id: UUID | None,
        workflow_template: str | None,
        window_days: int = 120,
    ) -> dict[str, float | str]:
        now = _utcnow()
        window_start = now - timedelta(days=max(1, window_days))
        workflow_row: WorkflowPerformanceRecord | None = None
        if workflow_template:
            workflow_row = await self.db.scalar(
                select(WorkflowPerformanceRecord)
                .where(
                    WorkflowPerformanceRecord.program_id == program_id,
                    WorkflowPerformanceRecord.workflow_template == workflow_template,
                    WorkflowPerformanceRecord.window_end >= window_start,
                )
                .order_by(WorkflowPerformanceRecord.computed_at.desc())
                .limit(1)
            )

        target_row: TargetPerformanceRecord | None = None
        if scope_target_id is not None:
            target_row = await self.db.scalar(
                select(TargetPerformanceRecord)
                .where(
                    TargetPerformanceRecord.program_id == program_id,
                    TargetPerformanceRecord.scope_target_id == scope_target_id,
                    TargetPerformanceRecord.window_end >= window_start,
                )
                .order_by(TargetPerformanceRecord.computed_at.desc())
                .limit(1)
            )

        rec_stmt: Select[tuple[RecommendationOutcomeRecord]] = select(
            RecommendationOutcomeRecord
        ).where(
            RecommendationOutcomeRecord.program_id == program_id,
            RecommendationOutcomeRecord.decided_at >= window_start,
        )
        alert_stmt: Select[tuple[AlertOutcomeRecord]] = select(AlertOutcomeRecord).where(
            AlertOutcomeRecord.program_id == program_id,
            AlertOutcomeRecord.evaluated_at >= window_start,
        )
        if scope_target_id is not None:
            rec_stmt = rec_stmt.where(RecommendationOutcomeRecord.scope_target_id == scope_target_id)
            alert_stmt = alert_stmt.where(AlertOutcomeRecord.scope_target_id == scope_target_id)

        recommendation_rows = list((await self.db.execute(rec_stmt.limit(200))).scalars().all())
        alert_rows = list((await self.db.execute(alert_stmt.limit(200))).scalars().all())

        recommendation_success_weight = 0.0
        for row in recommendation_rows:
            status = str(row.outcome_status or "").upper()
            if status == "SUCCEEDED":
                recommendation_success_weight += 1.0
            elif status == "USED":
                recommendation_success_weight += 0.75
            elif status == "ABANDONED":
                recommendation_success_weight += 0.2
            elif status == "BLOCKED":
                recommendation_success_weight += 0.1
            elif status == "FAILED":
                recommendation_success_weight += 0.05

        recommendation_success_rate = _ratio(
            int(recommendation_success_weight * 1000),
            len(recommendation_rows) * 1000,
        )
        alert_noise_rate = _ratio(
            sum(
                1
                for row in alert_rows
                if row.outcome_status in {"IGNORED", "RESOLVED_NOISE"}
            ),
            len(alert_rows),
        )

        return self._derive_scoring_modifiers(
            workflow_reportability_rate=float(
                workflow_row.workflow_reportability_rate if workflow_row else 0.0
            ),
            workflow_noise_rate=float(workflow_row.workflow_noise_rate if workflow_row else 0.0),
            target_reportability_rate=float(
                target_row.target_reportability_rate if target_row else 0.0
            ),
            target_duplicate_rate=float(target_row.target_duplicate_rate if target_row else 0.0),
            target_yield_score=float(target_row.target_yield_score if target_row else 50.0),
            recommendation_success_rate=float(recommendation_success_rate),
            alert_noise_rate=float(alert_noise_rate),
        )
