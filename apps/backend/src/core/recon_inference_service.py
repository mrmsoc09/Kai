from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from .audit_events import record_transition_event
from ..models.bug_bounty import (
    AdaptiveScheduleActionRecord,
    AnalystQueueItem,
    HuntScheduleJob,
    OpportunityInferenceRecord,
    SignalIntelligenceRecord,
    SwarmReasoningRecord,
    WorkflowDeltaRecord,
)
from ..models.campaign import CampaignRun, Program
from ..models.workflow import CorrelationRecord, WorkflowFinding, WorkflowRun

SCHEDULE_ACTIVE = "ACTIVE"

SWARM_ROLES = (
    "opportunity_intake_agent",
    "recon_planning_agent",
    "signal_correlation_agent",
    "anomaly_detection_agent",
    "reportability_scoring_agent",
    "duplicate_risk_agent",
    "analyst_briefing_agent",
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _fingerprint(*parts: str) -> str:
    digest = hashlib.sha256()
    for part in parts:
        digest.update(str(part).encode("utf-8"))
        digest.update(b"\x1f")
    return digest.hexdigest()


def _severity_weight(severity_hint: str | None) -> float:
    value = (severity_hint or "").strip().lower()
    return {
        "critical": 1.0,
        "high": 0.8,
        "medium": 0.55,
        "low": 0.3,
        "info": 0.1,
    }.get(value, 0.25)


def _clamp(value: float, *, low: float, high: float) -> float:
    return max(low, min(high, value))


class ReconInferenceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _save_signal(
        self,
        *,
        program_id: UUID,
        scope_target_id: UUID | None,
        workflow_run_id: UUID | None,
        source: str,
        source_record_id: str,
        signal_type: str,
        signal_key: str,
        confidence_score: float | None,
        severity_hint: str | None = None,
        evidence_refs: list[str] | None = None,
        correlation_refs: list[str] | None = None,
        details: dict[str, Any] | None = None,
    ) -> bool:
        fingerprint = _fingerprint(
            str(program_id),
            str(scope_target_id or ""),
            source,
            source_record_id,
            signal_type,
            signal_key,
        )
        existing = await self.db.scalar(
            select(SignalIntelligenceRecord).where(
                SignalIntelligenceRecord.signal_fingerprint == fingerprint
            )
        )
        if existing is not None:
            return False
        self.db.add(
            SignalIntelligenceRecord(
                program_id=program_id,
                scope_target_id=scope_target_id,
                workflow_run_id=workflow_run_id,
                source=source,
                source_record_id=source_record_id,
                signal_type=signal_type,
                signal_key=signal_key,
                confidence_score=confidence_score,
                severity_hint=severity_hint,
                signal_fingerprint=fingerprint,
                evidence_refs_json=evidence_refs or [],
                correlation_refs_json=correlation_refs or [],
                details_json=details or {},
                observed_at=_utcnow(),
            )
        )
        return True

    async def aggregate_signals(
        self,
        *,
        program_id: UUID | None = None,
        actor: str,
    ) -> dict[str, int]:
        created = 0
        considered = 0

        delta_stmt: Select[tuple[WorkflowDeltaRecord]] = select(WorkflowDeltaRecord).order_by(
            WorkflowDeltaRecord.created_at.desc()
        )
        if program_id is not None:
            delta_stmt = delta_stmt.where(WorkflowDeltaRecord.program_id == program_id)
        delta_rows = (await self.db.execute(delta_stmt.limit(5000))).scalars().all()
        for row in delta_rows:
            considered += 1
            if await self._save_signal(
                program_id=row.program_id,
                scope_target_id=row.scope_target_id,
                workflow_run_id=row.workflow_run_id,
                source="workflow_delta",
                source_record_id=str(row.id),
                signal_type=f"delta_{row.delta_type}",
                signal_key=f"{row.change_type}:{row.delta_key}",
                confidence_score=0.6 if row.change_type == "NEW" else 0.3,
                severity_hint=row.severity_hint,
                details=row.details_json if isinstance(row.details_json, dict) else {},
            ):
                created += 1

        finding_stmt: Select[tuple[WorkflowFinding]] = select(WorkflowFinding).order_by(
            WorkflowFinding.created_at.desc()
        )
        if program_id is not None:
            finding_stmt = finding_stmt.where(WorkflowFinding.campaign_id.is_not(None))
        finding_rows = (await self.db.execute(finding_stmt.limit(5000))).scalars().all()
        for row in finding_rows:
            if row.campaign_id is None:
                continue
            workflow_run = await self.db.scalar(
                select(WorkflowRun).where(WorkflowRun.id == row.workflow_run_id)
            )
            if workflow_run is None:
                continue
            campaign = await self.db.scalar(
                select(CampaignRun).where(CampaignRun.id == workflow_run.campaign_run_id)
            )
            if campaign is None:
                continue
            if program_id is not None and campaign.program_id != program_id:
                continue
            considered += 1
            if await self._save_signal(
                program_id=campaign.program_id,
                scope_target_id=workflow_run.scope_target_id,
                workflow_run_id=row.workflow_run_id,
                source="workflow_finding",
                source_record_id=str(row.id),
                signal_type="vulnerability_candidate",
                signal_key=f"{row.asset_identifier}:{row.vulnerability_type}",
                confidence_score=row.confidence_score,
                severity_hint=row.severity_hint,
                evidence_refs=[row.evidence_artifact_path] if row.evidence_artifact_path else [],
                details=row.details_json if isinstance(row.details_json, dict) else {},
            ):
                created += 1

        corr_stmt: Select[tuple[CorrelationRecord]] = select(CorrelationRecord).order_by(
            CorrelationRecord.created_at.desc()
        )
        if program_id is not None:
            corr_stmt = corr_stmt.where(CorrelationRecord.campaign_id.is_not(None))
        corr_rows = (await self.db.execute(corr_stmt.limit(5000))).scalars().all()
        for row in corr_rows:
            if row.campaign_id is None:
                continue
            workflow_run = await self.db.scalar(
                select(WorkflowRun).where(WorkflowRun.id == row.workflow_run_id)
            )
            if workflow_run is None:
                continue
            campaign = await self.db.scalar(
                select(CampaignRun).where(CampaignRun.id == workflow_run.campaign_run_id)
            )
            if campaign is None:
                continue
            if program_id is not None and campaign.program_id != program_id:
                continue
            considered += 1
            signal_sources = row.signal_sources_json if isinstance(row.signal_sources_json, list) else []
            if await self._save_signal(
                program_id=campaign.program_id,
                scope_target_id=workflow_run.scope_target_id,
                workflow_run_id=row.workflow_run_id,
                source="correlation_record",
                source_record_id=str(row.id),
                signal_type="correlation_strength",
                signal_key=row.asset_identifier,
                confidence_score=row.confidence,
                evidence_refs=[str(item) for item in signal_sources],
                correlation_refs=[str(row.id)],
                details={"priority_rank": row.priority_rank, "rule": row.correlation_rule},
            ):
                created += 1

        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="phase6.signals.aggregated",
            actor=actor,
            message="Signal aggregation completed",
            payload={"created_signals": created, "considered_records": considered},
        )
        return {"created_signals": created, "considered_records": considered}

    def _score_target_signals(
        self,
        signals: list[SignalIntelligenceRecord],
        *,
        queue_items: list[AnalystQueueItem],
        program_config: dict[str, Any] | None,
    ) -> dict[str, Any]:
        total = len(signals)
        delta_growth = sum(1 for s in signals if str(s.signal_type).startswith("delta_"))
        vuln = [s for s in signals if s.signal_type == "vulnerability_candidate"]
        secrets = [s for s in signals if "secret" in str(s.signal_type)]
        correlation = [s for s in signals if s.signal_type == "correlation_strength"]
        avg_confidence = (
            sum(float(s.confidence_score or 0.0) for s in signals) / total if total else 0.0
        )
        severity_boost = (
            sum(_severity_weight(s.severity_hint) for s in vuln) / max(len(vuln), 1)
        )
        queue_reportability = (
            sum(float(item.reportability_score or 0.0) for item in queue_items) / len(queue_items)
            if queue_items
            else 0.0
        )
        duplicate_risk = (
            sum(
                1
                for item in queue_items
                if str(item.duplicate_risk_hint or "").strip().upper() in {"HIGH", "ELEVATED"}
            )
            / max(len(queue_items), 1)
            if queue_items
            else 0.0
        )
        reward_metadata = (program_config or {}).get("reward_metadata")
        reward_boost = 0.0
        if isinstance(reward_metadata, dict):
            max_reward = float(reward_metadata.get("max_reward_usd") or 0.0)
            reward_boost = _clamp(max_reward / 20000.0, low=0.0, high=1.0)

        opportunity_score = _clamp(
            (
                (delta_growth * 1.2)
                + (len(vuln) * 7.0)
                + (len(secrets) * 10.0)
                + (len(correlation) * 2.0)
                + (avg_confidence * 25.0)
                + (severity_boost * 18.0)
                + (queue_reportability * 20.0)
                + (reward_boost * 8.0)
                - (duplicate_risk * 10.0)
            ),
            low=0.0,
            high=100.0,
        )
        target_priority_score = _clamp(
            opportunity_score * 0.7 + (avg_confidence * 30.0),
            low=0.0,
            high=100.0,
        )
        if len(secrets) > 0:
            recommended_workflow = "workflow_secret_exposure_scan"
            next_best_action = "schedule_secret_followup"
        elif len(vuln) >= 3 and avg_confidence >= 0.55:
            recommended_workflow = "workflow_quick_vuln_sweep"
            next_best_action = "schedule_vuln_validation"
        elif delta_growth >= 5:
            recommended_workflow = "workflow_web_attack_surface"
            next_best_action = "expand_attack_surface_recon"
        else:
            recommended_workflow = "workflow_recon_surface_map"
            next_best_action = "continue_baseline_recon"

        reasoning = (
            f"signals={total} delta_growth={delta_growth} vuln={len(vuln)} "
            f"secrets={len(secrets)} avg_confidence={avg_confidence:.2f} "
            f"duplicate_risk={duplicate_risk:.2f}"
        )
        return {
            "opportunity_score": round(opportunity_score, 3),
            "target_priority_score": round(target_priority_score, 3),
            "recommended_workflow": recommended_workflow,
            "next_best_action": next_best_action,
            "reasoning_summary": reasoning,
            "metrics": {
                "signals_total": total,
                "delta_growth": delta_growth,
                "vuln_signals": len(vuln),
                "secret_signals": len(secrets),
                "correlation_signals": len(correlation),
                "avg_confidence": round(avg_confidence, 4),
                "duplicate_risk": round(duplicate_risk, 4),
                "queue_reportability": round(queue_reportability, 4),
                "reward_boost": round(reward_boost, 4),
            },
        }

    async def _persist_swarm_outputs(
        self,
        *,
        program_id: UUID,
        scope_target_id: UUID | None,
        workflow_run_id: UUID | None,
        inference_id: UUID,
        scoring: dict[str, Any],
    ) -> int:
        created = 0
        for role in SWARM_ROLES:
            confidence = _clamp(
                float(scoring["metrics"].get("avg_confidence", 0.5)) + 0.1,
                low=0.0,
                high=1.0,
            )
            output = {
                "role": role,
                "recommended_workflow": scoring["recommended_workflow"],
                "next_best_action": scoring["next_best_action"],
                "opportunity_score": scoring["opportunity_score"],
                "target_priority_score": scoring["target_priority_score"],
                "evidence_summary": scoring["metrics"],
            }
            self.db.add(
                SwarmReasoningRecord(
                    program_id=program_id,
                    scope_target_id=scope_target_id,
                    workflow_run_id=workflow_run_id,
                    opportunity_inference_id=inference_id,
                    agent_role=role,
                    confidence_score=confidence,
                    output_json=output,
                    details_json={"reasoning_mode": "deterministic_phase6"},
                    reasoned_at=_utcnow(),
                )
            )
            created += 1
        return created

    async def _apply_adaptive_schedule(
        self,
        *,
        program_id: UUID,
        scope_target_id: UUID | None,
        inference: OpportunityInferenceRecord,
        actor: str,
    ) -> str:
        if scope_target_id is None:
            self.db.add(
                AdaptiveScheduleActionRecord(
                    program_id=program_id,
                    scope_target_id=None,
                    schedule_job_id=None,
                    opportunity_inference_id=inference.id,
                    action_type="schedule_adjustment",
                    action_status="BLOCKED",
                    reason="scope_target_id missing for adaptive action",
                    details_json={},
                    executed_at=_utcnow(),
                )
            )
            return "BLOCKED"
        schedule = await self.db.scalar(
            select(HuntScheduleJob).where(
                HuntScheduleJob.program_id == program_id,
                HuntScheduleJob.scope_target_id == scope_target_id,
                HuntScheduleJob.workflow_template == inference.recommended_workflow,
            )
        )
        if schedule is None:
            self.db.add(
                AdaptiveScheduleActionRecord(
                    program_id=program_id,
                    scope_target_id=scope_target_id,
                    schedule_job_id=None,
                    opportunity_inference_id=inference.id,
                    action_type="schedule_adjustment",
                    action_status="BLOCKED",
                    reason="no matching schedule for recommended workflow",
                    details_json={"recommended_workflow": inference.recommended_workflow},
                    executed_at=_utcnow(),
                )
            )
            return "BLOCKED"
        if schedule.status != SCHEDULE_ACTIVE:
            self.db.add(
                AdaptiveScheduleActionRecord(
                    program_id=program_id,
                    scope_target_id=scope_target_id,
                    schedule_job_id=schedule.id,
                    opportunity_inference_id=inference.id,
                    action_type="schedule_adjustment",
                    action_status="BLOCKED",
                    reason=f"schedule not active ({schedule.status})",
                    details_json={"schedule_id": str(schedule.id)},
                    executed_at=_utcnow(),
                )
            )
            return "BLOCKED"

        new_priority = 1 if inference.target_priority_score >= 85 else 2 if inference.target_priority_score >= 60 else 3
        changed = {
            "priority_tier_before": schedule.priority_tier,
            "priority_tier_after": new_priority,
        }
        schedule.priority_tier = new_priority
        if inference.opportunity_score >= 80:
            schedule.next_scheduled_run_at = _utcnow()
            changed["next_scheduled_run_at"] = schedule.next_scheduled_run_at.isoformat()
        schedule.updated_by = actor
        self.db.add(
            AdaptiveScheduleActionRecord(
                program_id=program_id,
                scope_target_id=scope_target_id,
                schedule_job_id=schedule.id,
                opportunity_inference_id=inference.id,
                action_type="schedule_adjustment",
                action_status="APPLIED",
                reason="adaptive prioritization applied",
                details_json=changed,
                executed_at=_utcnow(),
            )
        )
        return "APPLIED"

    async def run_inference(
        self,
        *,
        program_id: UUID | None,
        actor: str,
        apply_adaptive: bool,
    ) -> dict[str, Any]:
        signal_summary = await self.aggregate_signals(program_id=program_id, actor=actor)
        signal_stmt: Select[tuple[SignalIntelligenceRecord]] = select(SignalIntelligenceRecord)
        if program_id is not None:
            signal_stmt = signal_stmt.where(SignalIntelligenceRecord.program_id == program_id)
        signal_rows = list((await self.db.execute(signal_stmt)).scalars().all())
        grouped: dict[tuple[UUID, UUID | None], list[SignalIntelligenceRecord]] = defaultdict(list)
        for row in signal_rows:
            grouped[(row.program_id, row.scope_target_id)].append(row)

        score_count = 0
        swarm_count = 0
        adaptive_count = 0
        for (pid, scope_id), target_signals in grouped.items():
            queue_stmt: Select[tuple[AnalystQueueItem]] = select(AnalystQueueItem).where(
                AnalystQueueItem.program_id == pid
            )
            if scope_id is not None:
                queue_stmt = queue_stmt.where(AnalystQueueItem.scope_target_id == scope_id)
            queue_items = list((await self.db.execute(queue_stmt.limit(200))).scalars().all())

            workflow_run_id = target_signals[0].workflow_run_id if target_signals else None
            program_row = await self.db.scalar(
                select(Program).where(Program.id == pid)
            )
            program_config = None
            if program_row is not None:
                config = program_row.config_json
                program_config = config.get("opportunity") if isinstance(config, dict) else None

            scoring = self._score_target_signals(
                target_signals,
                queue_items=queue_items,
                program_config=program_config if isinstance(program_config, dict) else None,
            )
            evidence_ids = [str(item.id) for item in target_signals[:50]]
            inference = OpportunityInferenceRecord(
                program_id=pid,
                scope_target_id=scope_id,
                workflow_run_id=workflow_run_id,
                recommended_workflow=scoring["recommended_workflow"],
                next_best_action=scoring["next_best_action"],
                opportunity_score=scoring["opportunity_score"],
                target_priority_score=scoring["target_priority_score"],
                reasoning_summary=scoring["reasoning_summary"],
                supporting_evidence_json=evidence_ids,
                details_json=scoring["metrics"],
                inferred_at=_utcnow(),
            )
            self.db.add(inference)
            await self.db.flush()
            score_count += 1

            swarm_count += await self._persist_swarm_outputs(
                program_id=pid,
                scope_target_id=scope_id,
                workflow_run_id=workflow_run_id,
                inference_id=inference.id,
                scoring=scoring,
            )
            if apply_adaptive:
                status = await self._apply_adaptive_schedule(
                    program_id=pid,
                    scope_target_id=scope_id,
                    inference=inference,
                    actor=actor,
                )
                if status == "APPLIED":
                    adaptive_count += 1

        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="phase6.inference.completed",
            actor=actor,
            message="Phase 6 inference cycle completed",
            payload={
                "program_id": str(program_id) if program_id else None,
                "scores_created": score_count,
                "swarm_records_created": swarm_count,
                "adaptive_actions_applied": adaptive_count,
                **signal_summary,
            },
        )
        return {
            **signal_summary,
            "scores_created": score_count,
            "swarm_records_created": swarm_count,
            "adaptive_actions_applied": adaptive_count,
        }

    async def list_signals(
        self,
        *,
        program_id: UUID | None,
        scope_target_id: UUID | None,
        signal_type: str | None,
        limit: int,
    ) -> list[SignalIntelligenceRecord]:
        stmt: Select[tuple[SignalIntelligenceRecord]] = select(SignalIntelligenceRecord).order_by(
            SignalIntelligenceRecord.observed_at.desc()
        )
        if program_id is not None:
            stmt = stmt.where(SignalIntelligenceRecord.program_id == program_id)
        if scope_target_id is not None:
            stmt = stmt.where(SignalIntelligenceRecord.scope_target_id == scope_target_id)
        if signal_type:
            stmt = stmt.where(SignalIntelligenceRecord.signal_type == signal_type)
        stmt = stmt.limit(max(1, min(limit, 2000)))
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_opportunity_scores(
        self,
        *,
        program_id: UUID | None,
        scope_target_id: UUID | None,
        limit: int,
    ) -> list[OpportunityInferenceRecord]:
        stmt: Select[tuple[OpportunityInferenceRecord]] = select(OpportunityInferenceRecord).order_by(
            OpportunityInferenceRecord.inferred_at.desc()
        )
        if program_id is not None:
            stmt = stmt.where(OpportunityInferenceRecord.program_id == program_id)
        if scope_target_id is not None:
            stmt = stmt.where(OpportunityInferenceRecord.scope_target_id == scope_target_id)
        stmt = stmt.limit(max(1, min(limit, 2000)))
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_swarm_outputs(
        self,
        *,
        program_id: UUID | None,
        scope_target_id: UUID | None,
        agent_role: str | None,
        limit: int,
    ) -> list[SwarmReasoningRecord]:
        stmt: Select[tuple[SwarmReasoningRecord]] = select(SwarmReasoningRecord).order_by(
            SwarmReasoningRecord.reasoned_at.desc()
        )
        if program_id is not None:
            stmt = stmt.where(SwarmReasoningRecord.program_id == program_id)
        if scope_target_id is not None:
            stmt = stmt.where(SwarmReasoningRecord.scope_target_id == scope_target_id)
        if agent_role:
            stmt = stmt.where(SwarmReasoningRecord.agent_role == agent_role)
        stmt = stmt.limit(max(1, min(limit, 2000)))
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_adaptive_actions(
        self,
        *,
        program_id: UUID | None,
        action_status: str | None,
        limit: int,
    ) -> list[AdaptiveScheduleActionRecord]:
        stmt: Select[tuple[AdaptiveScheduleActionRecord]] = select(AdaptiveScheduleActionRecord).order_by(
            AdaptiveScheduleActionRecord.executed_at.desc()
        )
        if program_id is not None:
            stmt = stmt.where(AdaptiveScheduleActionRecord.program_id == program_id)
        if action_status:
            stmt = stmt.where(AdaptiveScheduleActionRecord.action_status == action_status)
        stmt = stmt.limit(max(1, min(limit, 2000)))
        return list((await self.db.execute(stmt)).scalars().all())

    async def analyst_briefing(
        self,
        *,
        program_id: UUID | None,
        limit: int,
    ) -> dict[str, Any]:
        scores = await self.list_opportunity_scores(
            program_id=program_id,
            scope_target_id=None,
            limit=max(limit, 50),
        )
        queue_stmt: Select[tuple[AnalystQueueItem]] = select(AnalystQueueItem).order_by(
            AnalystQueueItem.reportability_score.desc().nullslast(),
            AnalystQueueItem.updated_at.desc(),
        )
        if program_id is not None:
            queue_stmt = queue_stmt.where(AnalystQueueItem.program_id == program_id)
        queue_items = list((await self.db.execute(queue_stmt.limit(max(limit, 1)))).scalars().all())
        actions = await self.list_adaptive_actions(
            program_id=program_id,
            action_status=None,
            limit=max(limit, 1),
        )
        return {
            "generated_at": _utcnow().isoformat(),
            "top_targets": [
                {
                    "program_id": str(item.program_id),
                    "scope_target_id": str(item.scope_target_id) if item.scope_target_id else None,
                    "opportunity_score": item.opportunity_score,
                    "target_priority_score": item.target_priority_score,
                    "recommended_workflow": item.recommended_workflow,
                    "next_best_action": item.next_best_action,
                }
                for item in scores[:limit]
            ],
            "top_candidates": [
                {
                    "queue_item_id": str(item.id),
                    "affected_asset": item.affected_asset,
                    "vulnerability_type": item.vulnerability_type,
                    "reportability_score": item.reportability_score,
                    "status": item.status,
                }
                for item in queue_items[:limit]
            ],
            "adaptive_actions": [
                {
                    "action_id": str(item.id),
                    "action_status": item.action_status,
                    "action_type": item.action_type,
                    "reason": item.reason,
                }
                for item in actions[:limit]
            ],
        }
