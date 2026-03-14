from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import Select, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .audit_events import record_transition_event
from ..models.bug_bounty import (
    AdaptiveScheduleActionRecord,
    AnalystCaseRecord,
    AnalystQueueItem,
    DuplicateRiskRecord,
    EvidenceCompletenessRecord,
    HuntReadinessRecord,
    NotificationAlertRecord,
    VulnerabilityPredictionRecord,
    WorkflowDeltaRecord,
    WorkflowRecommendationRecord,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _json_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _json_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


CASE_STATUSES_TERMINAL = {"dismissed", "duplicate", "submitted", "closed"}
ALERT_STATUS_OPENISH = {"OPEN", "ACKNOWLEDGED"}

CASE_ALLOWED_TRANSITIONS = {
    "new": {"acknowledged", "triaging", "needs_manual_validation", "dismissed", "duplicate", "closed"},
    "acknowledged": {"triaging", "needs_manual_validation", "ready_for_report", "dismissed", "duplicate", "closed"},
    "triaging": {"needs_manual_validation", "ready_for_report", "escalated", "dismissed", "duplicate", "closed"},
    "needs_manual_validation": {"triaging", "ready_for_report", "escalated", "dismissed", "duplicate", "closed"},
    "ready_for_report": {"triaging", "submitted", "dismissed", "duplicate", "closed"},
    "dismissed": set(),
    "duplicate": set(),
    "escalated": {"triaging", "needs_manual_validation", "ready_for_report", "submitted", "closed"},
    "submitted": {"closed"},
    "closed": set(),
}


def _case_priority_from_severity(severity: str | None) -> str:
    value = (severity or "").strip().upper()
    if value in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
        return value
    return "MEDIUM"


@dataclass
class _AlertSeed:
    program_id: UUID
    scope_target_id: UUID | None
    workflow_run_id: UUID | None
    analyst_queue_item_id: UUID | None
    prediction_record_id: UUID | None
    recommendation_record_id: UUID | None
    submission_draft_id: UUID | None
    alert_type: str
    severity: str
    urgency: str
    fingerprint: str
    summary: str
    reasoning_summary: str | None
    supporting_record_ids: list[str]
    supporting_signal_ids: list[str]
    details_json: dict[str, Any]


class Phase9AlertCaseService:
    """Phase 9 notification and case workflow service."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_alerts(
        self,
        *,
        program_id: UUID | None = None,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 500,
    ) -> list[NotificationAlertRecord]:
        stmt: Select[tuple[NotificationAlertRecord]] = select(NotificationAlertRecord).order_by(
            NotificationAlertRecord.severity.desc(),
            NotificationAlertRecord.urgency.desc(),
            NotificationAlertRecord.last_seen_at.desc(),
        )
        if program_id is not None:
            stmt = stmt.where(NotificationAlertRecord.program_id == program_id)
        if status:
            stmt = stmt.where(NotificationAlertRecord.status == status.upper())
        if severity:
            stmt = stmt.where(NotificationAlertRecord.severity == severity.upper())
        stmt = stmt.limit(max(1, min(limit, 2000)))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_alert(self, alert_id: UUID) -> NotificationAlertRecord | None:
        return await self.db.scalar(select(NotificationAlertRecord).where(NotificationAlertRecord.id == alert_id))

    async def acknowledge_alert(
        self,
        alert_id: UUID,
        *,
        actor: str,
        note: str | None = None,
    ) -> NotificationAlertRecord:
        alert = await self.get_alert(alert_id)
        if alert is None:
            raise ValueError("Alert not found")
        if alert.status == "RESOLVED":
            raise ValueError("Alert is already resolved")
        alert.status = "ACKNOWLEDGED"
        alert.acknowledged_at = _utcnow()
        alert.acknowledged_by = actor
        alert.last_seen_at = _utcnow()
        if note:
            details = _json_dict(alert.details_json)
            notes = _json_list(details.get("notes"))
            notes.append({"at": _utcnow().isoformat(), "actor": actor, "note": note, "type": "ack"})
            details["notes"] = notes
            alert.details_json = details
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="bugbounty.alert.acknowledged",
            actor=actor,
            message=f"Alert acknowledged: {alert.alert_type}",
            payload={
                "alert_id": str(alert.id),
                "program_id": str(alert.program_id),
                "status": alert.status,
            },
            dedupe_key=f"alert:ack:{alert.id}:{actor}",
        )
        return alert

    async def resolve_alert(
        self,
        alert_id: UUID,
        *,
        actor: str,
        note: str | None = None,
    ) -> NotificationAlertRecord:
        alert = await self.get_alert(alert_id)
        if alert is None:
            raise ValueError("Alert not found")
        if alert.status == "RESOLVED":
            return alert
        alert.status = "RESOLVED"
        alert.resolved_at = _utcnow()
        alert.resolved_by = actor
        alert.last_seen_at = _utcnow()
        if note:
            details = _json_dict(alert.details_json)
            notes = _json_list(details.get("notes"))
            notes.append({"at": _utcnow().isoformat(), "actor": actor, "note": note, "type": "resolve"})
            details["notes"] = notes
            alert.details_json = details
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="bugbounty.alert.resolved",
            actor=actor,
            message=f"Alert resolved: {alert.alert_type}",
            payload={
                "alert_id": str(alert.id),
                "program_id": str(alert.program_id),
                "status": alert.status,
            },
            dedupe_key=f"alert:resolve:{alert.id}:{actor}",
        )
        return alert

    async def list_cases(
        self,
        *,
        program_id: UUID | None = None,
        status: str | None = None,
        priority: str | None = None,
        owner: str | None = None,
        limit: int = 500,
    ) -> list[AnalystCaseRecord]:
        stmt: Select[tuple[AnalystCaseRecord]] = select(AnalystCaseRecord).order_by(
            AnalystCaseRecord.priority.desc(),
            AnalystCaseRecord.last_transition_at.desc().nullslast(),
            AnalystCaseRecord.created_at.desc(),
        )
        if program_id is not None:
            stmt = stmt.where(AnalystCaseRecord.program_id == program_id)
        if status:
            stmt = stmt.where(AnalystCaseRecord.status == status.lower())
        if priority:
            stmt = stmt.where(AnalystCaseRecord.priority == priority.upper())
        if owner:
            stmt = stmt.where(AnalystCaseRecord.owner == owner)
        stmt = stmt.limit(max(1, min(limit, 2000)))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_case(self, case_id: UUID) -> AnalystCaseRecord | None:
        return await self.db.scalar(select(AnalystCaseRecord).where(AnalystCaseRecord.id == case_id))

    async def create_case(
        self,
        *,
        program_id: UUID,
        title: str,
        summary: str,
        actor: str,
        scope_target_id: UUID | None = None,
        workflow_run_id: UUID | None = None,
        alert_id: UUID | None = None,
        analyst_queue_item_id: UUID | None = None,
        prediction_record_id: UUID | None = None,
        recommendation_record_id: UUID | None = None,
        submission_draft_id: UUID | None = None,
        reasoning_summary: str | None = None,
        priority: str = "MEDIUM",
        owner: str | None = None,
        evidence_refs: list[str] | None = None,
    ) -> AnalystCaseRecord:
        normalized_priority = _case_priority_from_severity(priority)
        now = _utcnow()
        details_json = {
            "assignment_history": [],
            "transition_history": [
                {
                    "at": now.isoformat(),
                    "actor": actor,
                    "from": None,
                    "to": "new",
                }
            ],
        }
        if owner:
            details_json["assignment_history"].append(
                {
                    "at": now.isoformat(),
                    "actor": actor,
                    "owner": owner,
                    "action": "assigned",
                }
            )
        case = AnalystCaseRecord(
            program_id=program_id,
            scope_target_id=scope_target_id,
            workflow_run_id=workflow_run_id,
            alert_id=alert_id,
            analyst_queue_item_id=analyst_queue_item_id,
            prediction_record_id=prediction_record_id,
            recommendation_record_id=recommendation_record_id,
            submission_draft_id=submission_draft_id,
            title=title.strip(),
            summary=summary.strip(),
            reasoning_summary=reasoning_summary,
            priority=normalized_priority,
            status="new",
            owner=owner,
            last_actor=actor,
            assigned_at=now if owner else None,
            last_transition_at=now,
            evidence_refs_json=list(evidence_refs or []),
            triage_notes_json=[],
            details_json=details_json,
        )
        self.db.add(case)
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="bugbounty.case.created",
            actor=actor,
            message=f"Case created: {case.title}",
            payload={
                "case_id": str(case.id),
                "program_id": str(case.program_id),
                "alert_id": str(case.alert_id) if case.alert_id else None,
            },
        )
        if alert_id:
            alert = await self.get_alert(alert_id)
            if alert and alert.status in ALERT_STATUS_OPENISH:
                await self.acknowledge_alert(alert.id, actor=actor, note="Linked to case")
        return case

    async def create_case_from_alert(
        self,
        alert_id: UUID,
        *,
        actor: str,
        owner: str | None = None,
    ) -> AnalystCaseRecord:
        alert = await self.get_alert(alert_id)
        if alert is None:
            raise ValueError("Alert not found")
        existing = await self.db.scalar(
            select(AnalystCaseRecord)
            .where(
                AnalystCaseRecord.alert_id == alert_id,
                AnalystCaseRecord.status.notin_(tuple(CASE_STATUSES_TERMINAL)),
            )
            .limit(1)
        )
        if existing is not None:
            return existing
        return await self.create_case(
            program_id=alert.program_id,
            scope_target_id=alert.scope_target_id,
            workflow_run_id=alert.workflow_run_id,
            alert_id=alert.id,
            analyst_queue_item_id=alert.analyst_queue_item_id,
            prediction_record_id=alert.prediction_record_id,
            recommendation_record_id=alert.recommendation_record_id,
            submission_draft_id=alert.submission_draft_id,
            title=f"[{alert.severity}] {alert.alert_type.replace('_', ' ')}",
            summary=alert.summary,
            reasoning_summary=alert.reasoning_summary,
            priority=_case_priority_from_severity(alert.severity),
            actor=actor,
            owner=owner,
            evidence_refs=list(_json_list(alert.supporting_record_ids_json)),
        )

    async def update_case(
        self,
        case_id: UUID,
        *,
        actor: str,
        status: str | None = None,
        priority: str | None = None,
        summary: str | None = None,
        reasoning_summary: str | None = None,
        closure_reason: str | None = None,
    ) -> AnalystCaseRecord:
        case = await self.get_case(case_id)
        if case is None:
            raise ValueError("Case not found")

        now = _utcnow()
        details = _json_dict(case.details_json)
        transitions = _json_list(details.get("transition_history"))
        changed = False

        if status is not None:
            next_status = status.strip().lower()
            if next_status not in CASE_ALLOWED_TRANSITIONS:
                raise ValueError(f"Invalid case status: {status}")
            current_status = str(case.status or "new").lower()
            if next_status != current_status:
                allowed = CASE_ALLOWED_TRANSITIONS.get(current_status, set())
                if next_status not in allowed:
                    raise ValueError(
                        f"Invalid case transition: {current_status} -> {next_status}"
                    )
                case.status = next_status
                case.last_transition_at = now
                transitions.append(
                    {
                        "at": now.isoformat(),
                        "actor": actor,
                        "from": current_status,
                        "to": next_status,
                    }
                )
                changed = True
                if next_status in CASE_STATUSES_TERMINAL:
                    case.closed_at = now
                elif case.closed_at is not None:
                    case.closed_at = None

        if priority is not None:
            case.priority = _case_priority_from_severity(priority)
            changed = True
        if summary is not None:
            case.summary = summary.strip()
            changed = True
        if reasoning_summary is not None:
            case.reasoning_summary = reasoning_summary.strip() if reasoning_summary else None
            changed = True
        if closure_reason is not None:
            case.closure_reason = closure_reason
            changed = True

        if not changed:
            return case

        details["transition_history"] = transitions
        case.details_json = details
        case.last_actor = actor
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="bugbounty.case.updated",
            actor=actor,
            message=f"Case updated: {case.title}",
            payload={
                "case_id": str(case.id),
                "status": case.status,
                "priority": case.priority,
            },
            dedupe_key=f"case:update:{case.id}:{case.status}:{case.priority}",
        )
        if case.alert_id and case.status in {"ready_for_report", "submitted", "closed", "dismissed", "duplicate"}:
            await self.resolve_alert(case.alert_id, actor=actor, note=f"Case moved to {case.status}")
        # Refresh to load server-side values (e.g. updated_at via onupdate) that
        # are marked expired after the UPDATE flush above.
        await self.db.refresh(case)
        return case

    async def assign_case(self, case_id: UUID, *, owner: str, actor: str) -> AnalystCaseRecord:
        case = await self.get_case(case_id)
        if case is None:
            raise ValueError("Case not found")
        now = _utcnow()
        details = _json_dict(case.details_json)
        history = _json_list(details.get("assignment_history"))
        history.append(
            {
                "at": now.isoformat(),
                "actor": actor,
                "owner": owner,
                "previous_owner": case.owner,
                "action": "reassigned" if case.owner else "assigned",
            }
        )
        details["assignment_history"] = history
        case.details_json = details
        case.owner = owner
        case.assigned_at = now
        case.last_actor = actor
        case.last_transition_at = now
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="bugbounty.case.assigned",
            actor=actor,
            message=f"Case assigned to {owner}",
            payload={"case_id": str(case.id), "owner": owner},
        )
        return case

    async def add_case_note(self, case_id: UUID, *, note: str, actor: str) -> AnalystCaseRecord:
        case = await self.get_case(case_id)
        if case is None:
            raise ValueError("Case not found")
        notes = _json_list(case.triage_notes_json)
        now = _utcnow()
        notes.append({"at": now.isoformat(), "actor": actor, "note": note.strip()})
        case.triage_notes_json = notes
        case.last_actor = actor
        case.last_transition_at = now
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="bugbounty.case.note_added",
            actor=actor,
            message="Case note added",
            payload={"case_id": str(case.id)},
        )
        return case

    async def get_alert_case_summary(self, *, program_id: UUID | None = None) -> dict[str, int]:
        alert_stmt = select(NotificationAlertRecord)
        case_stmt = select(AnalystCaseRecord)
        if program_id is not None:
            alert_stmt = alert_stmt.where(NotificationAlertRecord.program_id == program_id)
            case_stmt = case_stmt.where(AnalystCaseRecord.program_id == program_id)
        alerts = list((await self.db.execute(alert_stmt)).scalars().all())
        cases = list((await self.db.execute(case_stmt)).scalars().all())
        now = _utcnow()
        unresolved_alerts = [item for item in alerts if item.status in ALERT_STATUS_OPENISH]
        high_alerts = [
            item
            for item in unresolved_alerts
            if item.severity in {"HIGH", "CRITICAL"}
        ]
        open_cases = [item for item in cases if str(item.status or "").lower() not in CASE_STATUSES_TERMINAL]
        ready_cases = [item for item in open_cases if item.status == "ready_for_report"]
        stale_unowned = [
            item
            for item in open_cases
            if not item.owner and item.created_at <= now - timedelta(hours=24)
        ]
        return {
            "unresolved_alert_count": len(unresolved_alerts),
            "high_severity_alert_count": len(high_alerts),
            "open_case_count": len(open_cases),
            "ready_for_report_case_count": len(ready_cases),
            "stale_unowned_case_count": len(stale_unowned),
        }

    async def sync_alerts(
        self,
        *,
        actor: str,
        program_id: UUID | None = None,
        cooldown_minutes: int = 120,
    ) -> dict[str, int]:
        now = _utcnow()
        seeds = await self._collect_alert_seeds(program_id=program_id, now=now)

        created = 0
        updated = 0
        suppressed = 0
        cooldown = timedelta(minutes=max(1, cooldown_minutes))
        for seed in seeds:
            recent = await self.db.scalar(
                select(NotificationAlertRecord)
                .where(
                    NotificationAlertRecord.program_id == seed.program_id,
                    NotificationAlertRecord.alert_fingerprint == seed.fingerprint,
                )
                .order_by(NotificationAlertRecord.last_seen_at.desc())
                .limit(1)
            )
            if recent is not None:
                recent_age = now - (recent.last_seen_at or recent.created_at or now)
                if recent.status in ALERT_STATUS_OPENISH:
                    recent.occurrence_count = int(recent.occurrence_count or 1) + 1
                    recent.last_seen_at = now
                    if recent.severity != "CRITICAL":
                        recent.severity = seed.severity
                    recent.urgency = seed.urgency
                    recent.summary = seed.summary
                    recent.reasoning_summary = seed.reasoning_summary
                    recent.supporting_signal_ids_json = seed.supporting_signal_ids
                    recent.supporting_record_ids_json = seed.supporting_record_ids
                    recent.details_json = seed.details_json
                    updated += 1
                    continue
                if recent_age < cooldown:
                    recent.status = "SUPPRESSED"
                    recent.occurrence_count = int(recent.occurrence_count or 1) + 1
                    recent.last_seen_at = now
                    suppressed += 1
                    continue

            self.db.add(
                NotificationAlertRecord(
                    program_id=seed.program_id,
                    scope_target_id=seed.scope_target_id,
                    workflow_run_id=seed.workflow_run_id,
                    analyst_queue_item_id=seed.analyst_queue_item_id,
                    prediction_record_id=seed.prediction_record_id,
                    recommendation_record_id=seed.recommendation_record_id,
                    submission_draft_id=seed.submission_draft_id,
                    alert_type=seed.alert_type,
                    severity=seed.severity,
                    urgency=seed.urgency,
                    alert_fingerprint=seed.fingerprint,
                    summary=seed.summary,
                    reasoning_summary=seed.reasoning_summary,
                    supporting_signal_ids_json=seed.supporting_signal_ids,
                    supporting_record_ids_json=seed.supporting_record_ids,
                    status="OPEN",
                    occurrence_count=1,
                    first_seen_at=now,
                    last_seen_at=now,
                    details_json=seed.details_json,
                )
            )
            created += 1

        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="bugbounty.alert.sync",
            actor=actor,
            message="Phase 9 alert synchronization completed",
            payload={
                "program_id": str(program_id) if program_id else None,
                "scanned_sources": len(seeds),
                "created_alerts": created,
                "updated_alerts": updated,
                "suppressed_alerts": suppressed,
            },
            dedupe_key=f"alert-sync:{program_id or 'all'}:{now.strftime('%Y-%m-%dT%H:%M')}",
        )
        return {
            "scanned_sources": len(seeds),
            "created_alerts": created,
            "updated_alerts": updated,
            "suppressed_alerts": suppressed,
        }

    async def _collect_alert_seeds(
        self,
        *,
        program_id: UUID | None,
        now: datetime,
    ) -> list[_AlertSeed]:
        seeds: list[_AlertSeed] = []

        candidate_stmt: Select[tuple[AnalystQueueItem]] = select(AnalystQueueItem).where(
            or_(
                AnalystQueueItem.status == "ready_for_report",
                AnalystQueueItem.reportability_score >= 0.85,
            )
        )
        if program_id is not None:
            candidate_stmt = candidate_stmt.where(AnalystQueueItem.program_id == program_id)
        for item in (await self.db.execute(candidate_stmt.limit(300))).scalars().all():
            severity = "CRITICAL" if float(item.reportability_score or 0.0) >= 0.95 else "HIGH"
            seeds.append(
                _AlertSeed(
                    program_id=item.program_id,
                    scope_target_id=item.scope_target_id,
                    workflow_run_id=item.workflow_run_id,
                    analyst_queue_item_id=item.id,
                    prediction_record_id=None,
                    recommendation_record_id=None,
                    submission_draft_id=None,
                    alert_type="LIKELY_REPORTABLE_FINDING",
                    severity=severity,
                    urgency="HIGH",
                    fingerprint=f"candidate:reportable:{item.id}",
                    summary=f"Likely reportable candidate on {item.affected_asset}",
                    reasoning_summary=(
                        f"reportability={float(item.reportability_score or 0.0):.2f} "
                        f"confidence={float(item.confidence_score or 0.0):.2f}"
                    ),
                    supporting_record_ids=[str(item.id)],
                    supporting_signal_ids=[],
                    details_json={
                        "candidate_status": item.status,
                        "vulnerability_type": item.vulnerability_type,
                    },
                )
            )

        duplicate_stmt: Select[tuple[DuplicateRiskRecord]] = select(DuplicateRiskRecord).where(
            DuplicateRiskRecord.risk_band == "HIGH"
        )
        if program_id is not None:
            duplicate_stmt = duplicate_stmt.where(DuplicateRiskRecord.program_id == program_id)
        for item in (await self.db.execute(duplicate_stmt.limit(200))).scalars().all():
            seeds.append(
                _AlertSeed(
                    program_id=item.program_id,
                    scope_target_id=item.scope_target_id,
                    workflow_run_id=item.workflow_run_id,
                    analyst_queue_item_id=item.analyst_queue_item_id,
                    prediction_record_id=None,
                    recommendation_record_id=None,
                    submission_draft_id=None,
                    alert_type="DUPLICATE_RISK_ELEVATED",
                    severity="MEDIUM",
                    urgency="LOW",
                    fingerprint=f"duplicate:high:{item.id}",
                    summary="Duplicate risk increased for candidate finding",
                    reasoning_summary=item.reasoning_summary,
                    supporting_record_ids=[str(item.id)],
                    supporting_signal_ids=list(_json_list(item.supporting_signal_ids_json)),
                    details_json={"risk_band": item.risk_band},
                )
            )

        evidence_stmt: Select[tuple[EvidenceCompletenessRecord]] = select(EvidenceCompletenessRecord).where(
            EvidenceCompletenessRecord.readiness_state.in_(["INSUFFICIENT", "PARTIAL"])
        )
        if program_id is not None:
            evidence_stmt = evidence_stmt.where(EvidenceCompletenessRecord.program_id == program_id)
        for item in (await self.db.execute(evidence_stmt.limit(200))).scalars().all():
            seeds.append(
                _AlertSeed(
                    program_id=item.program_id,
                    scope_target_id=item.scope_target_id,
                    workflow_run_id=item.workflow_run_id,
                    analyst_queue_item_id=item.analyst_queue_item_id,
                    prediction_record_id=None,
                    recommendation_record_id=None,
                    submission_draft_id=None,
                    alert_type="EVIDENCE_COMPLETENESS_GAP",
                    severity="MEDIUM",
                    urgency="MEDIUM",
                    fingerprint=f"evidence:gap:{item.id}",
                    summary="Evidence completeness dropped below report threshold",
                    reasoning_summary=item.reasoning_summary,
                    supporting_record_ids=[str(item.id)],
                    supporting_signal_ids=[],
                    details_json={"missing_fields": list(_json_list(item.missing_fields_json))},
                )
            )

        recommendation_stmt: Select[tuple[WorkflowRecommendationRecord]] = select(WorkflowRecommendationRecord).where(
            WorkflowRecommendationRecord.recommendation_status.in_(["BLOCKED", "DEFERRED"])
        )
        if program_id is not None:
            recommendation_stmt = recommendation_stmt.where(WorkflowRecommendationRecord.program_id == program_id)
        for item in (await self.db.execute(recommendation_stmt.limit(200))).scalars().all():
            severity = "HIGH" if item.recommendation_status == "BLOCKED" else "MEDIUM"
            seeds.append(
                _AlertSeed(
                    program_id=item.program_id,
                    scope_target_id=item.scope_target_id,
                    workflow_run_id=item.workflow_run_id,
                    analyst_queue_item_id=item.analyst_queue_item_id,
                    prediction_record_id=item.prediction_record_id,
                    recommendation_record_id=item.id,
                    submission_draft_id=None,
                    alert_type="ADAPTIVE_RECOMMENDATION_BLOCKED",
                    severity=severity,
                    urgency="HIGH" if severity == "HIGH" else "MEDIUM",
                    fingerprint=f"recommendation:{item.recommendation_status.lower()}:{item.id}",
                    summary=f"Recommendation {item.recommendation_status.lower()}: {item.recommended_action}",
                    reasoning_summary=item.reasoning_summary,
                    supporting_record_ids=[str(item.id)],
                    supporting_signal_ids=[],
                    details_json={"recommended_workflow": item.recommended_workflow},
                )
            )

        delta_stmt: Select[tuple[WorkflowDeltaRecord]] = select(WorkflowDeltaRecord).where(
            WorkflowDeltaRecord.change_type == "NEW",
            WorkflowDeltaRecord.delta_type.in_(["secret", "vuln_candidate"]),
            WorkflowDeltaRecord.created_at >= now - timedelta(hours=24),
        )
        if program_id is not None:
            delta_stmt = delta_stmt.where(WorkflowDeltaRecord.program_id == program_id)
        for item in (await self.db.execute(delta_stmt.limit(300))).scalars().all():
            seeds.append(
                _AlertSeed(
                    program_id=item.program_id,
                    scope_target_id=item.scope_target_id,
                    workflow_run_id=item.workflow_run_id,
                    analyst_queue_item_id=None,
                    prediction_record_id=None,
                    recommendation_record_id=None,
                    submission_draft_id=None,
                    alert_type="SEVERE_DELTA_DETECTED",
                    severity="HIGH",
                    urgency="HIGH",
                    fingerprint=f"delta:new:{item.delta_type}:{item.delta_key}:{item.scope_target_id}",
                    summary=f"New {item.delta_type} delta detected: {item.delta_key}",
                    reasoning_summary=f"change_type={item.change_type}",
                    supporting_record_ids=[str(item.id)],
                    supporting_signal_ids=[],
                    details_json={"delta_type": item.delta_type},
                )
            )

        readiness_stmt: Select[tuple[HuntReadinessRecord]] = select(HuntReadinessRecord).where(
            HuntReadinessRecord.decision_status != "READY",
            HuntReadinessRecord.decided_at >= now - timedelta(hours=24),
        )
        if program_id is not None:
            readiness_stmt = readiness_stmt.where(HuntReadinessRecord.program_id == program_id)
        for item in (await self.db.execute(readiness_stmt.limit(300))).scalars().all():
            severity = "HIGH" if item.decision_status in {"BLOCKED_BY_SCOPE", "BLOCKED_BY_HEALTH"} else "MEDIUM"
            seeds.append(
                _AlertSeed(
                    program_id=item.program_id,
                    scope_target_id=item.scope_target_id,
                    workflow_run_id=item.workflow_run_id,
                    analyst_queue_item_id=None,
                    prediction_record_id=None,
                    recommendation_record_id=None,
                    submission_draft_id=None,
                    alert_type="READINESS_BLOCKED",
                    severity=severity,
                    urgency="MEDIUM",
                    fingerprint=f"readiness:{item.program_id}:{item.scope_target_id}:{item.workflow_template}:{item.decision_status}",
                    summary=f"Readiness blocked: {item.decision_status}",
                    reasoning_summary=item.reason,
                    supporting_record_ids=[str(item.id)],
                    supporting_signal_ids=[],
                    details_json={"workflow_template": item.workflow_template},
                )
            )

        adaptive_stmt: Select[tuple[AdaptiveScheduleActionRecord]] = select(AdaptiveScheduleActionRecord).where(
            AdaptiveScheduleActionRecord.action_status == "BLOCKED",
            AdaptiveScheduleActionRecord.executed_at >= now - timedelta(hours=24),
        )
        if program_id is not None:
            adaptive_stmt = adaptive_stmt.where(AdaptiveScheduleActionRecord.program_id == program_id)
        for item in (await self.db.execute(adaptive_stmt.limit(300))).scalars().all():
            seeds.append(
                _AlertSeed(
                    program_id=item.program_id,
                    scope_target_id=item.scope_target_id,
                    workflow_run_id=None,
                    analyst_queue_item_id=None,
                    prediction_record_id=None,
                    recommendation_record_id=None,
                    submission_draft_id=None,
                    alert_type="ADAPTIVE_ACTION_BLOCKED",
                    severity="MEDIUM",
                    urgency="MEDIUM",
                    fingerprint=f"adaptive:blocked:{item.id}",
                    summary=f"Adaptive action blocked: {item.action_type}",
                    reasoning_summary=item.reason,
                    supporting_record_ids=[str(item.id)],
                    supporting_signal_ids=[],
                    details_json={"action_type": item.action_type},
                )
            )

        prediction_stmt: Select[tuple[VulnerabilityPredictionRecord]] = select(VulnerabilityPredictionRecord).where(
            VulnerabilityPredictionRecord.reportability_score >= 0.9,
            VulnerabilityPredictionRecord.created_at >= now - timedelta(hours=48),
        )
        if program_id is not None:
            prediction_stmt = prediction_stmt.where(VulnerabilityPredictionRecord.program_id == program_id)
        for item in (await self.db.execute(prediction_stmt.limit(300))).scalars().all():
            seeds.append(
                _AlertSeed(
                    program_id=item.program_id,
                    scope_target_id=item.scope_target_id,
                    workflow_run_id=item.workflow_run_id,
                    analyst_queue_item_id=item.analyst_queue_item_id,
                    prediction_record_id=item.id,
                    recommendation_record_id=None,
                    submission_draft_id=None,
                    alert_type="HIGH_CONFIDENCE_PREDICTION",
                    severity="HIGH",
                    urgency="HIGH",
                    fingerprint=f"prediction:high:{item.id}",
                    summary=f"High-confidence vulnerability prediction: {item.predicted_vulnerability_type}",
                    reasoning_summary=item.reasoning_summary,
                    supporting_record_ids=[str(item.id)],
                    supporting_signal_ids=list(_json_list(item.supporting_signal_ids_json)),
                    details_json={
                        "reportability_score": item.reportability_score,
                        "opportunity_score": item.opportunity_score,
                    },
                )
            )

        return seeds
