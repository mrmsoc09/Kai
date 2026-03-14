from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from .audit_events import record_transition_event
from ..models.bug_bounty import (
    AgentEvaluationRecord,
    AgentExecutionRecord,
    AgentRegistryRecord,
    AnalystCaseRecord,
    AnalystQueueItem,
    DuplicateRiskRecord,
    EvidenceCompletenessRecord,
    NotificationAlertRecord,
    OpportunitySelectionRecord,
    SignalIntelligenceRecord,
    TargetYieldScoreRecord,
    VulnerabilityPredictionRecord,
    WorkflowDeltaRecord,
    WorkflowRecommendationRecord,
)
from ..models.campaign import CampaignRun
from ..models.workflow import WorkflowRun


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _json_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _clamp(value: float, *, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class AgentDefinition:
    agent_id: str
    agent_name: str
    agent_role: str
    category: str
    purpose: str
    allowed_tools: tuple[str, ...]
    forbidden_tools: tuple[str, ...]
    input_schema_reference: str
    output_schema_reference: str
    model_preference: str
    model_runtime: str
    confidence_threshold: float
    max_runtime_seconds: int
    retry_policy: dict[str, Any]
    escalation_agent_id: str | None
    enabled: bool
    safety_notes: str
    observability_tags: tuple[str, ...]


FIRST_WAVE_AGENT_DEFINITIONS: tuple[AgentDefinition, ...] = (
    AgentDefinition(
        agent_id="scope_parsing_agent",
        agent_name="Scope Parsing Agent",
        agent_role="scope_parsing_agent",
        category="recon_discovery",
        purpose="Parses target identifiers and verifies basic scope readiness for bounded workflows.",
        allowed_tools=("scope_resolver",),
        forbidden_tools=("sqlmap", "commix", "metasploit"),
        input_schema_reference="phase10_5.scope_parsing_agent.input.v1",
        output_schema_reference="phase10_5.agent_output.v1",
        model_preference="kai/selfhosted-small",
        model_runtime="self_hosted",
        confidence_threshold=0.75,
        max_runtime_seconds=30,
        retry_policy={"max_retries": 1, "backoff_seconds": 2},
        escalation_agent_id="analyst_briefing_agent",
        enabled=True,
        safety_notes="Read-only parsing; never authorizes execution directly.",
        observability_tags=("scope", "safety", "phase10_5"),
    ),
    AgentDefinition(
        agent_id="url_discovery_classification_agent",
        agent_name="URL Discovery Classification Agent",
        agent_role="url_discovery_classification_agent",
        category="recon_discovery",
        purpose="Classifies discovered URL signal quality and route suitability for deeper workflows.",
        allowed_tools=("katana", "gau", "waybackurls"),
        forbidden_tools=("masscan", "sqlmap"),
        input_schema_reference="phase10_5.url_discovery_classification_agent.input.v1",
        output_schema_reference="phase10_5.agent_output.v1",
        model_preference="kai/selfhosted-small",
        model_runtime="self_hosted",
        confidence_threshold=0.7,
        max_runtime_seconds=45,
        retry_policy={"max_retries": 1, "backoff_seconds": 2},
        escalation_agent_id="next_best_workflow_agent",
        enabled=True,
        safety_notes="Classifies existing URL intelligence; no scanning side effects.",
        observability_tags=("recon", "url", "classification"),
    ),
    AgentDefinition(
        agent_id="technology_fingerprint_explanation_agent",
        agent_name="Technology Fingerprint Explanation Agent",
        agent_role="technology_fingerprint_explanation_agent",
        category="recon_discovery",
        purpose="Explains technology fingerprint deltas and expected risk impact.",
        allowed_tools=("httpx", "tlsx"),
        forbidden_tools=("sqlmap", "nmap"),
        input_schema_reference="phase10_5.technology_fingerprint_explanation_agent.input.v1",
        output_schema_reference="phase10_5.agent_output.v1",
        model_preference="kai/selfhosted-medium",
        model_runtime="self_hosted",
        confidence_threshold=0.7,
        max_runtime_seconds=60,
        retry_policy={"max_retries": 1, "backoff_seconds": 3},
        escalation_agent_id="recommendation_explanation_agent",
        enabled=True,
        safety_notes="Evidence explanation only; no active fingerprinting in agent logic.",
        observability_tags=("technology", "explanation", "phase10_5"),
    ),
    AgentDefinition(
        agent_id="delta_importance_agent",
        agent_name="Delta Importance Agent",
        agent_role="delta_importance_agent",
        category="triage_classification",
        purpose="Scores operational importance of recent run-to-run deltas.",
        allowed_tools=("delta_detector",),
        forbidden_tools=("metasploit",),
        input_schema_reference="phase10_5.delta_importance_agent.input.v1",
        output_schema_reference="phase10_5.agent_output.v1",
        model_preference="kai/selfhosted-small",
        model_runtime="self_hosted",
        confidence_threshold=0.72,
        max_runtime_seconds=45,
        retry_policy={"max_retries": 1, "backoff_seconds": 2},
        escalation_agent_id="opportunity_ranking_agent",
        enabled=True,
        safety_notes="Operates on persisted deltas; no scan triggering.",
        observability_tags=("delta", "prioritization"),
    ),
    AgentDefinition(
        agent_id="duplicate_risk_agent",
        agent_name="Duplicate Risk Agent",
        agent_role="duplicate_risk_agent",
        category="triage_classification",
        purpose="Summarizes duplicate-risk posture for candidate findings.",
        allowed_tools=("nuclei",),
        forbidden_tools=("metasploit",),
        input_schema_reference="phase10_5.duplicate_risk_agent.input.v1",
        output_schema_reference="phase10_5.agent_output.v1",
        model_preference="kai/selfhosted-small",
        model_runtime="self_hosted",
        confidence_threshold=0.7,
        max_runtime_seconds=40,
        retry_policy={"max_retries": 1, "backoff_seconds": 2},
        escalation_agent_id="recommendation_explanation_agent",
        enabled=True,
        safety_notes="Risk synthesis only; no mutation of candidate outcomes.",
        observability_tags=("duplicate", "triage"),
    ),
    AgentDefinition(
        agent_id="evidence_completeness_agent",
        agent_name="Evidence Completeness Agent",
        agent_role="evidence_completeness_agent",
        category="triage_classification",
        purpose="Checks evidence readiness and missing context for analyst escalation.",
        allowed_tools=("artifact_store",),
        forbidden_tools=("metasploit",),
        input_schema_reference="phase10_5.evidence_completeness_agent.input.v1",
        output_schema_reference="phase10_5.agent_output.v1",
        model_preference="kai/selfhosted-small",
        model_runtime="self_hosted",
        confidence_threshold=0.72,
        max_runtime_seconds=45,
        retry_policy={"max_retries": 1, "backoff_seconds": 2},
        escalation_agent_id="analyst_briefing_agent",
        enabled=True,
        safety_notes="Evidence scoring only; no automatic report submission.",
        observability_tags=("evidence", "readiness"),
    ),
    AgentDefinition(
        agent_id="opportunity_ranking_agent",
        agent_name="Opportunity Ranking Agent",
        agent_role="opportunity_ranking_agent",
        category="strategy_recommendation",
        purpose="Ranks opportunities across programs/targets from canonical scoring records.",
        allowed_tools=("ranking_engine",),
        forbidden_tools=("metasploit",),
        input_schema_reference="phase10_5.opportunity_ranking_agent.input.v1",
        output_schema_reference="phase10_5.agent_output.v1",
        model_preference="kai/selfhosted-medium",
        model_runtime="self_hosted",
        confidence_threshold=0.78,
        max_runtime_seconds=75,
        retry_policy={"max_retries": 1, "backoff_seconds": 3},
        escalation_agent_id="next_best_workflow_agent",
        enabled=True,
        safety_notes="Ranking synthesis only; scheduling remains policy-gated.",
        observability_tags=("ranking", "strategy"),
    ),
    AgentDefinition(
        agent_id="next_best_workflow_agent",
        agent_name="Next Best Workflow Agent",
        agent_role="next_best_workflow_agent",
        category="strategy_recommendation",
        purpose="Recommends follow-up workflow actions from canonical recommendations and yield scores.",
        allowed_tools=("workflow_recommendation_engine",),
        forbidden_tools=("metasploit",),
        input_schema_reference="phase10_5.next_best_workflow_agent.input.v1",
        output_schema_reference="phase10_5.agent_output.v1",
        model_preference="kai/selfhosted-medium",
        model_runtime="self_hosted",
        confidence_threshold=0.8,
        max_runtime_seconds=75,
        retry_policy={"max_retries": 1, "backoff_seconds": 3},
        escalation_agent_id="recommendation_explanation_agent",
        enabled=True,
        safety_notes="Outputs recommendations only; execution remains explicit and gated.",
        observability_tags=("workflow", "recommendation"),
    ),
    AgentDefinition(
        agent_id="recommendation_explanation_agent",
        agent_name="Recommendation Explanation Agent",
        agent_role="recommendation_explanation_agent",
        category="strategy_recommendation",
        purpose="Explains recommendation provenance for operator trust and auditability.",
        allowed_tools=("audit_log",),
        forbidden_tools=("metasploit",),
        input_schema_reference="phase10_5.recommendation_explanation_agent.input.v1",
        output_schema_reference="phase10_5.agent_output.v1",
        model_preference="kai/selfhosted-medium",
        model_runtime="self_hosted",
        confidence_threshold=0.75,
        max_runtime_seconds=60,
        retry_policy={"max_retries": 1, "backoff_seconds": 2},
        escalation_agent_id="analyst_briefing_agent",
        enabled=True,
        safety_notes="Pure explanation pathway; no control-plane mutation.",
        observability_tags=("explainability", "recommendations"),
    ),
    AgentDefinition(
        agent_id="alert_summarizer_agent",
        agent_name="Alert Summarizer Agent",
        agent_role="alert_summarizer_agent",
        category="operations",
        purpose="Summarizes unresolved alert pressure and escalation needs.",
        allowed_tools=("alert_center",),
        forbidden_tools=("metasploit",),
        input_schema_reference="phase10_5.alert_summarizer_agent.input.v1",
        output_schema_reference="phase10_5.agent_output.v1",
        model_preference="kai/selfhosted-small",
        model_runtime="self_hosted",
        confidence_threshold=0.68,
        max_runtime_seconds=35,
        retry_policy={"max_retries": 1, "backoff_seconds": 2},
        escalation_agent_id="analyst_briefing_agent",
        enabled=True,
        safety_notes="Alert synthesis only; no auto-notification side effects.",
        observability_tags=("alerts", "operations"),
    ),
    AgentDefinition(
        agent_id="analyst_briefing_agent",
        agent_name="Analyst Briefing Agent",
        agent_role="analyst_briefing_agent",
        category="operations",
        purpose="Creates concise analyst-ready briefings from candidate, alert, and recommendation signals.",
        allowed_tools=("briefing_generator",),
        forbidden_tools=("metasploit",),
        input_schema_reference="phase10_5.analyst_briefing_agent.input.v1",
        output_schema_reference="phase10_5.agent_output.v1",
        model_preference="kai/selfhosted-medium",
        model_runtime="self_hosted",
        confidence_threshold=0.74,
        max_runtime_seconds=75,
        retry_policy={"max_retries": 1, "backoff_seconds": 3},
        escalation_agent_id=None,
        enabled=True,
        safety_notes="Briefing output only; analyst remains final decision authority.",
        observability_tags=("briefing", "operations"),
    ),
)


AGENT_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "scope_parsing_agent": ("target_identifier",),
    "url_discovery_classification_agent": tuple(),
    "technology_fingerprint_explanation_agent": tuple(),
    "delta_importance_agent": tuple(),
    "duplicate_risk_agent": tuple(),
    "evidence_completeness_agent": tuple(),
    "opportunity_ranking_agent": tuple(),
    "next_best_workflow_agent": tuple(),
    "recommendation_explanation_agent": tuple(),
    "alert_summarizer_agent": tuple(),
    "analyst_briefing_agent": tuple(),
}


class Phase10_5AgentFrameworkService:
    """Canonical specialized agent framework service (Phase 10.5)."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self._definitions = {item.agent_id: item for item in FIRST_WAVE_AGENT_DEFINITIONS}

    async def sync_registry(self, *, actor: str, emit_event: bool = True) -> dict[str, int]:
        created = 0
        updated = 0
        for definition in FIRST_WAVE_AGENT_DEFINITIONS:
            existing = await self.db.scalar(
                select(AgentRegistryRecord).where(AgentRegistryRecord.agent_id == definition.agent_id)
            )
            if existing is None:
                self.db.add(self._registry_record_from_definition(definition))
                created += 1
                continue
            changed = False
            for field_name, value in self._definition_to_fields(definition).items():
                if getattr(existing, field_name) != value:
                    setattr(existing, field_name, value)
                    changed = True
            if changed:
                updated += 1

        await self.db.flush()
        if emit_event:
            await record_transition_event(
                self.db,
                event_type="phase10_5.agent_registry.synced",
                actor=actor,
                message="Phase 10.5 agent registry synchronized",
                payload={"created": created, "updated": updated},
            )
        return {"created": created, "updated": updated, "total": len(FIRST_WAVE_AGENT_DEFINITIONS)}

    def _definition_to_fields(self, definition: AgentDefinition) -> dict[str, Any]:
        return {
            "agent_name": definition.agent_name,
            "agent_role": definition.agent_role,
            "category": definition.category,
            "purpose": definition.purpose,
            "allowed_tools_json": list(definition.allowed_tools),
            "forbidden_tools_json": list(definition.forbidden_tools),
            "input_schema_reference": definition.input_schema_reference,
            "output_schema_reference": definition.output_schema_reference,
            "model_preference": definition.model_preference,
            "model_runtime": definition.model_runtime,
            "confidence_threshold": float(definition.confidence_threshold),
            "max_runtime_seconds": int(definition.max_runtime_seconds),
            "retry_policy_json": dict(definition.retry_policy),
            "escalation_agent_id": definition.escalation_agent_id,
            "enabled": bool(definition.enabled),
            "safety_notes": definition.safety_notes,
            "observability_tags_json": list(definition.observability_tags),
        }

    def _registry_record_from_definition(self, definition: AgentDefinition) -> AgentRegistryRecord:
        return AgentRegistryRecord(
            agent_id=definition.agent_id,
            details_json={},
            **self._definition_to_fields(definition),
        )

    async def list_agents(
        self,
        *,
        enabled_only: bool = False,
        category: str | None = None,
        limit: int = 200,
    ) -> list[AgentRegistryRecord]:
        await self.sync_registry(actor="system.phase10_5.registry.autosync", emit_event=False)
        stmt: Select[tuple[AgentRegistryRecord]] = select(AgentRegistryRecord).order_by(
            AgentRegistryRecord.category.asc(),
            AgentRegistryRecord.agent_name.asc(),
        )
        if enabled_only:
            stmt = stmt.where(AgentRegistryRecord.enabled.is_(True))
        if category:
            stmt = stmt.where(AgentRegistryRecord.category == category)
        stmt = stmt.limit(max(1, min(limit, 2000)))
        return list((await self.db.execute(stmt)).scalars().all())

    async def get_agent(self, agent_id: str) -> AgentRegistryRecord | None:
        await self.sync_registry(actor="system.phase10_5.registry.autosync", emit_event=False)
        return await self.db.scalar(
            select(AgentRegistryRecord).where(AgentRegistryRecord.agent_id == agent_id)
        )

    async def list_executions(
        self,
        *,
        program_id: UUID | None = None,
        agent_id: str | None = None,
        execution_status: str | None = None,
        limit: int = 500,
    ) -> list[AgentExecutionRecord]:
        stmt: Select[tuple[AgentExecutionRecord]] = select(AgentExecutionRecord).order_by(
            AgentExecutionRecord.started_at.desc()
        )
        if program_id is not None:
            stmt = stmt.where(AgentExecutionRecord.program_id == program_id)
        if agent_id:
            stmt = stmt.where(AgentExecutionRecord.agent_id == agent_id)
        if execution_status:
            stmt = stmt.where(AgentExecutionRecord.execution_status == execution_status.upper())
        stmt = stmt.limit(max(1, min(limit, 2000)))
        return list((await self.db.execute(stmt)).scalars().all())

    async def list_evaluations(
        self,
        *,
        agent_id: str | None = None,
        status: str | None = None,
        limit: int = 500,
    ) -> list[AgentEvaluationRecord]:
        stmt: Select[tuple[AgentEvaluationRecord]] = select(AgentEvaluationRecord).order_by(
            AgentEvaluationRecord.executed_at.desc()
        )
        if agent_id:
            stmt = stmt.where(AgentEvaluationRecord.agent_id == agent_id)
        if status:
            stmt = stmt.where(AgentEvaluationRecord.status == status.upper())
        stmt = stmt.limit(max(1, min(limit, 2000)))
        return list((await self.db.execute(stmt)).scalars().all())

    def _input_hash(self, payload: dict[str, Any]) -> str:
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    async def _resolve_program_context(
        self,
        *,
        program_id: UUID | None,
        scope_target_id: UUID | None,
        workflow_run_id: UUID | None,
        analyst_case_id: UUID | None,
        analyst_queue_item_id: UUID | None,
    ) -> tuple[UUID, UUID | None]:
        resolved_program_id = program_id
        resolved_scope_target_id = scope_target_id

        if analyst_case_id is not None:
            case = await self.db.scalar(select(AnalystCaseRecord).where(AnalystCaseRecord.id == analyst_case_id))
            if case is None:
                raise ValueError("analyst_case_id not found")
            resolved_program_id = case.program_id
            resolved_scope_target_id = case.scope_target_id or resolved_scope_target_id

        if analyst_queue_item_id is not None:
            queue_item = await self.db.scalar(
                select(AnalystQueueItem).where(AnalystQueueItem.id == analyst_queue_item_id)
            )
            if queue_item is None:
                raise ValueError("analyst_queue_item_id not found")
            resolved_program_id = queue_item.program_id
            resolved_scope_target_id = queue_item.scope_target_id or resolved_scope_target_id

        if workflow_run_id is not None and resolved_program_id is None:
            workflow_run = await self.db.scalar(select(WorkflowRun).where(WorkflowRun.id == workflow_run_id))
            if workflow_run and workflow_run.campaign_run_id is not None:
                campaign = await self.db.scalar(
                    select(CampaignRun).where(CampaignRun.id == workflow_run.campaign_run_id)
                )
                if campaign:
                    resolved_program_id = campaign.program_id
                    resolved_scope_target_id = workflow_run.scope_target_id or resolved_scope_target_id

        if resolved_program_id is None:
            raise ValueError(
                "program_id is required unless analyst_case_id, analyst_queue_item_id, or workflow_run_id resolves it"
            )
        return resolved_program_id, resolved_scope_target_id

    def _resolve_model(self, definition: AgentDefinition, *, allow_escalation: bool) -> tuple[str, str]:
        scoped_name = definition.agent_id.upper().replace("-", "_")
        explicit = os.getenv(f"K1_AGENT_MODEL_{scoped_name}")
        if explicit:
            return explicit, "self_hosted_explicit"
        default_self_hosted = os.getenv("K1_AGENT_MODEL_SELF_HOSTED", definition.model_preference)
        if definition.model_runtime == "self_hosted":
            return default_self_hosted, "self_hosted_default"
        if allow_escalation:
            escalation_model = os.getenv("K1_AGENT_MODEL_ESCALATION")
            if escalation_model:
                return escalation_model, "escalated_override"
        return default_self_hosted, "self_hosted_fallback"

    async def run_agent(
        self,
        *,
        agent_id: str,
        actor: str,
        input_payload: dict[str, Any] | None = None,
        program_id: UUID | None = None,
        scope_target_id: UUID | None = None,
        workflow_run_id: UUID | None = None,
        analyst_case_id: UUID | None = None,
        analyst_queue_item_id: UUID | None = None,
        persist_record: bool = True,
    ) -> AgentExecutionRecord | dict[str, Any]:
        registry = await self.get_agent(agent_id)
        if registry is None:
            raise ValueError("Unknown agent_id")
        if not registry.enabled:
            raise ValueError("Agent is disabled")

        payload = input_payload if isinstance(input_payload, dict) else {}
        missing = [field for field in AGENT_REQUIRED_FIELDS.get(agent_id, ()) if not payload.get(field)]
        if missing:
            raise ValueError(f"Missing required input fields: {', '.join(missing)}")

        resolved_program_id, resolved_scope_target_id = await self._resolve_program_context(
            program_id=program_id,
            scope_target_id=scope_target_id,
            workflow_run_id=workflow_run_id,
            analyst_case_id=analyst_case_id,
            analyst_queue_item_id=analyst_queue_item_id,
        )
        started_at = _utcnow()
        model_used, routing_policy = self._resolve_model(
            self._definitions.get(agent_id, FIRST_WAVE_AGENT_DEFINITIONS[0]),
            allow_escalation=True,
        )

        try:
            output = await self._execute_logic(
                agent_id=agent_id,
                program_id=resolved_program_id,
                scope_target_id=resolved_scope_target_id,
                workflow_run_id=workflow_run_id,
                analyst_case_id=analyst_case_id,
                analyst_queue_item_id=analyst_queue_item_id,
                payload=payload,
            )
            execution_status = str(output.get("status", "SUCCEEDED")).upper()
            confidence = float(output.get("confidence") or 0.0)
            threshold = float(registry.confidence_threshold or 0.0)
            escalation_taken = False
            escalation_agent_id = None
            failure_reason = output.get("failure_reason")

            if execution_status == "SUCCEEDED" and confidence < threshold:
                escalation_agent_id = registry.escalation_agent_id
                escalation_taken = escalation_agent_id is not None
                output["escalation_recommended"] = escalation_taken
                if escalation_taken:
                    execution_status = "ESCALATED"
                    output["status"] = "ESCALATED"
                    output["failure_reason"] = (
                        f"confidence {confidence:.3f} below threshold {threshold:.3f}"
                    )
                else:
                    execution_status = "DEFERRED"
                    output["status"] = "DEFERRED"
                    output["failure_reason"] = (
                        f"confidence {confidence:.3f} below threshold {threshold:.3f}"
                    )
                failure_reason = output.get("failure_reason")

        except Exception as exc:  # pragma: no cover - safety net for runtime faults
            output = {
                "status": "FAILED",
                "confidence": 0.0,
                "reasoning_summary": "Agent execution failed with an internal error.",
                "key_observations": [],
                "suggested_next_action": "defer_to_operator",
                "supporting_evidence_refs": [],
                "failure_reason": str(exc),
                "escalation_recommended": True,
                "data": {},
            }
            execution_status = "FAILED"
            confidence = 0.0
            escalation_taken = True
            escalation_agent_id = registry.escalation_agent_id
            failure_reason = str(exc)

        finished_at = _utcnow()
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        output["status"] = execution_status
        output["confidence"] = _clamp(confidence, low=0.0, high=1.0)
        output["execution_metadata"] = {
            "agent_id": agent_id,
            "model_used": model_used,
            "routing_policy": routing_policy,
            "duration_ms": duration_ms,
        }

        if not persist_record:
            return output

        execution = AgentExecutionRecord(
            agent_registry_id=registry.id,
            agent_id=registry.agent_id,
            program_id=resolved_program_id,
            scope_target_id=resolved_scope_target_id,
            workflow_run_id=workflow_run_id,
            analyst_case_id=analyst_case_id,
            analyst_queue_item_id=analyst_queue_item_id,
            input_ref=payload.get("input_ref"),
            input_hash=self._input_hash(payload),
            output_json=output,
            model_used=model_used,
            routing_policy=routing_policy,
            confidence=output.get("confidence"),
            execution_status=execution_status,
            failure_reason=failure_reason,
            escalation_taken=escalation_taken,
            escalation_agent_id=escalation_agent_id,
            started_at=started_at,
            finished_at=finished_at,
            duration_ms=duration_ms,
            log_path=payload.get("log_path"),
            artifact_refs_json=[
                str(item) for item in _json_list(payload.get("artifact_refs"))[:50]
            ],
            details_json={
                "actor": actor,
                "input_payload": payload,
                "escalation_candidate": registry.escalation_agent_id,
            },
        )
        self.db.add(execution)
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="phase10_5.agent.execution",
            actor=actor,
            message=f"Agent execution {execution_status.lower()}: {agent_id}",
            payload={
                "agent_execution_id": str(execution.id),
                "agent_id": agent_id,
                "program_id": str(resolved_program_id),
                "execution_status": execution_status,
                "confidence": output.get("confidence"),
                "model_used": model_used,
                "routing_policy": routing_policy,
            },
            dedupe_key=f"phase10_5:agent:{agent_id}:{execution.id}",
        )
        return execution

    async def evaluate_agent(
        self,
        *,
        agent_id: str,
        actor: str,
        benchmark_name: str = "default",
    ) -> AgentEvaluationRecord:
        registry = await self.get_agent(agent_id)
        if registry is None:
            raise ValueError("Unknown agent_id")

        fixtures = self._evaluation_fixtures(agent_id)
        if not fixtures:
            raise ValueError("No evaluation fixtures configured for agent")

        passed_count = 0
        failed_count = 0
        confidences: list[float] = []
        latencies: list[int] = []
        results: list[dict[str, Any]] = []

        for fixture in fixtures:
            start = _utcnow()
            output = await self.run_agent(
                agent_id=agent_id,
                actor=actor,
                input_payload=fixture["input_payload"],
                program_id=fixture["program_id"],
                scope_target_id=fixture["scope_target_id"],
                workflow_run_id=fixture["workflow_run_id"],
                analyst_case_id=fixture["analyst_case_id"],
                analyst_queue_item_id=fixture["analyst_queue_item_id"],
                persist_record=False,
            )
            latency_ms = int((_utcnow() - start).total_seconds() * 1000)
            latencies.append(latency_ms)
            confidence = float(output.get("confidence") or 0.0)
            confidences.append(confidence)
            status = str(output.get("status") or "FAILED").upper()
            ok = status in {"SUCCEEDED", "ESCALATED"} and confidence >= float(
                registry.confidence_threshold or 0.0
            )
            if ok:
                passed_count += 1
            else:
                failed_count += 1
            results.append(
                {
                    "fixture_name": fixture["name"],
                    "status": status,
                    "confidence": confidence,
                    "latency_ms": latency_ms,
                    "ok": ok,
                }
            )

        fixture_count = len(fixtures)
        success_rate = passed_count / fixture_count if fixture_count else 0.0
        status = "PASSED" if success_rate >= 0.8 else ("PARTIAL" if success_rate >= 0.5 else "FAILED")
        model_used, _ = self._resolve_model(self._definitions[agent_id], allow_escalation=True)
        evaluation = AgentEvaluationRecord(
            agent_registry_id=registry.id,
            agent_id=agent_id,
            benchmark_name=benchmark_name,
            model_used=model_used,
            fixture_count=fixture_count,
            passed_count=passed_count,
            failed_count=failed_count,
            avg_confidence=(sum(confidences) / len(confidences)) if confidences else None,
            avg_latency_ms=int(sum(latencies) / len(latencies)) if latencies else None,
            success_rate=round(success_rate, 4),
            status=status,
            results_json={"fixtures": results},
            run_by=actor,
            run_reason="phase10_5.agent_evaluation",
            executed_at=_utcnow(),
        )
        self.db.add(evaluation)
        await self.db.flush()
        await record_transition_event(
            self.db,
            event_type="phase10_5.agent.evaluation",
            actor=actor,
            message=f"Agent evaluation completed: {agent_id}",
            payload={
                "evaluation_id": str(evaluation.id),
                "agent_id": agent_id,
                "status": status,
                "success_rate": evaluation.success_rate,
                "fixture_count": fixture_count,
            },
            dedupe_key=f"phase10_5:evaluation:{agent_id}:{evaluation.id}",
        )
        return evaluation

    def _evaluation_fixtures(self, agent_id: str) -> list[dict[str, Any]]:
        # Program/context IDs are resolved by runtime lookup from linked case/queue when available.
        nil_uuid = UUID("00000000-0000-0000-0000-000000000001")
        return [
            {
                "name": f"{agent_id}.baseline",
                "program_id": nil_uuid,
                "scope_target_id": None,
                "workflow_run_id": None,
                "analyst_case_id": None,
                "analyst_queue_item_id": None,
                "input_payload": {"target_identifier": "example.org"},
            }
        ]

    async def _execute_logic(
        self,
        *,
        agent_id: str,
        program_id: UUID,
        scope_target_id: UUID | None,
        workflow_run_id: UUID | None,
        analyst_case_id: UUID | None,
        analyst_queue_item_id: UUID | None,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        if agent_id == "scope_parsing_agent":
            return await self._scope_parsing(program_id=program_id, payload=payload)
        if agent_id == "url_discovery_classification_agent":
            return await self._url_classification(program_id=program_id, scope_target_id=scope_target_id)
        if agent_id == "technology_fingerprint_explanation_agent":
            return await self._technology_explanation(program_id=program_id, scope_target_id=scope_target_id)
        if agent_id == "delta_importance_agent":
            return await self._delta_importance(program_id=program_id, scope_target_id=scope_target_id)
        if agent_id == "duplicate_risk_agent":
            return await self._duplicate_risk(program_id=program_id, queue_item_id=analyst_queue_item_id)
        if agent_id == "evidence_completeness_agent":
            return await self._evidence_completeness(program_id=program_id, queue_item_id=analyst_queue_item_id)
        if agent_id == "opportunity_ranking_agent":
            return await self._opportunity_ranking(program_id=program_id)
        if agent_id == "next_best_workflow_agent":
            return await self._next_best_workflow(program_id=program_id, scope_target_id=scope_target_id)
        if agent_id == "recommendation_explanation_agent":
            return await self._recommendation_explanation(program_id=program_id, scope_target_id=scope_target_id)
        if agent_id == "alert_summarizer_agent":
            return await self._alert_summarizer(program_id=program_id)
        if agent_id == "analyst_briefing_agent":
            return await self._analyst_briefing(program_id=program_id, scope_target_id=scope_target_id)
        raise ValueError(f"Unsupported agent_id: {agent_id}")

    async def _scope_parsing(self, *, program_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        target = str(payload.get("target_identifier") or "").strip()
        if not target:
            return {
                "status": "FAILED",
                "confidence": 0.0,
                "reasoning_summary": "target_identifier is required for scope parsing.",
                "key_observations": [],
                "suggested_next_action": "provide_target_identifier",
                "supporting_evidence_refs": [],
                "failure_reason": "target_identifier missing",
                "escalation_recommended": True,
                "data": {},
            }

        target_type = "domain"
        if target.startswith("http://") or target.startswith("https://"):
            target_type = "url"
        elif "/" in target and not target.startswith("http"):
            target_type = "cidr_or_path"
        elif target.replace(".", "").isdigit():
            target_type = "ip"

        confidence = 0.85 if target_type in {"domain", "url"} else 0.65
        return {
            "status": "SUCCEEDED",
            "confidence": confidence,
            "reasoning_summary": f"Parsed target as {target_type} for program {program_id}.",
            "key_observations": [f"target={target}", f"target_type={target_type}"],
            "suggested_next_action": "validate_scope_against_program",
            "supporting_evidence_refs": [],
            "failure_reason": None,
            "escalation_recommended": confidence < 0.7,
            "data": {"target": target, "target_type": target_type},
        }

    async def _url_classification(
        self,
        *,
        program_id: UUID,
        scope_target_id: UUID | None,
    ) -> dict[str, Any]:
        stmt = select(SignalIntelligenceRecord).where(
            SignalIntelligenceRecord.program_id == program_id,
            SignalIntelligenceRecord.signal_type.ilike("%url%"),
        )
        if scope_target_id is not None:
            stmt = stmt.where(SignalIntelligenceRecord.scope_target_id == scope_target_id)
        rows = list((await self.db.execute(stmt.limit(200))).scalars().all())
        high_conf = sum(1 for row in rows if float(row.confidence_score or 0.0) >= 0.7)
        confidence = _clamp((high_conf / max(len(rows), 1)) + (0.2 if rows else 0.0), low=0.0, high=1.0)
        return {
            "status": "SUCCEEDED",
            "confidence": round(confidence, 4),
            "reasoning_summary": f"Classified {len(rows)} URL-oriented signals with {high_conf} high-confidence records.",
            "key_observations": [f"url_signals={len(rows)}", f"high_confidence={high_conf}"],
            "suggested_next_action": "run_endpoint_discovery" if len(rows) >= 5 else "continue_recon_collection",
            "supporting_evidence_refs": [str(row.id) for row in rows[:10]],
            "failure_reason": None,
            "escalation_recommended": len(rows) == 0,
            "data": {"url_signal_count": len(rows), "high_confidence_count": high_conf},
        }

    async def _technology_explanation(
        self,
        *,
        program_id: UUID,
        scope_target_id: UUID | None,
    ) -> dict[str, Any]:
        stmt = select(WorkflowDeltaRecord).where(
            WorkflowDeltaRecord.program_id == program_id,
            WorkflowDeltaRecord.delta_type.in_(("technology", "service")),
        )
        if scope_target_id is not None:
            stmt = stmt.where(WorkflowDeltaRecord.scope_target_id == scope_target_id)
        deltas = list((await self.db.execute(stmt.limit(200))).scalars().all())
        changed = sum(1 for row in deltas if row.change_type in {"NEW", "CHANGED"})
        confidence = _clamp((changed / max(len(deltas), 1)) * 0.8 + 0.2, low=0.0, high=1.0)
        return {
            "status": "SUCCEEDED",
            "confidence": round(confidence, 4),
            "reasoning_summary": f"Observed {changed} changed/new technology deltas out of {len(deltas)} records.",
            "key_observations": [f"technology_deltas={len(deltas)}", f"changed_or_new={changed}"],
            "suggested_next_action": "prioritize_tech_sensitive_templates" if changed > 0 else "monitor_technology_baseline",
            "supporting_evidence_refs": [str(item.id) for item in deltas[:10]],
            "failure_reason": None,
            "escalation_recommended": changed >= 8,
            "data": {"total_technology_deltas": len(deltas), "changed_or_new": changed},
        }

    async def _delta_importance(
        self,
        *,
        program_id: UUID,
        scope_target_id: UUID | None,
    ) -> dict[str, Any]:
        stmt = select(WorkflowDeltaRecord).where(WorkflowDeltaRecord.program_id == program_id)
        if scope_target_id is not None:
            stmt = stmt.where(WorkflowDeltaRecord.scope_target_id == scope_target_id)
        rows = list((await self.db.execute(stmt.order_by(WorkflowDeltaRecord.created_at.desc()).limit(200))).scalars().all())
        severe = sum(1 for row in rows if str(row.severity_hint or "").lower() in {"high", "critical"})
        new_items = sum(1 for row in rows if row.change_type == "NEW")
        importance = _clamp((severe * 0.12) + (new_items * 0.04), low=0.0, high=1.0)
        return {
            "status": "SUCCEEDED",
            "confidence": round(_clamp(0.55 + importance, low=0.0, high=1.0), 4),
            "reasoning_summary": f"Delta importance derived from {new_items} new items and {severe} severe changes.",
            "key_observations": [f"new_deltas={new_items}", f"severe_deltas={severe}"],
            "suggested_next_action": "escalate_delta_review" if importance >= 0.55 else "standard_delta_monitoring",
            "supporting_evidence_refs": [str(item.id) for item in rows[:10]],
            "failure_reason": None,
            "escalation_recommended": severe >= 3,
            "data": {"importance_score": round(importance, 4)},
        }

    async def _duplicate_risk(self, *, program_id: UUID, queue_item_id: UUID | None) -> dict[str, Any]:
        stmt = select(DuplicateRiskRecord).where(DuplicateRiskRecord.program_id == program_id).order_by(
            DuplicateRiskRecord.assessed_at.desc()
        )
        if queue_item_id is not None:
            stmt = stmt.where(DuplicateRiskRecord.analyst_queue_item_id == queue_item_id)
        record = await self.db.scalar(stmt.limit(1))
        if record is None:
            return {
                "status": "DEFERRED",
                "confidence": 0.45,
                "reasoning_summary": "No duplicate-risk record found for the selected context.",
                "key_observations": [],
                "suggested_next_action": "run_phase7_duplicate_risk_scoring",
                "supporting_evidence_refs": [],
                "failure_reason": "duplicate risk record missing",
                "escalation_recommended": False,
                "data": {},
            }
        score = float(record.duplicate_risk_score or 0.0)
        return {
            "status": "SUCCEEDED",
            "confidence": round(_clamp(0.5 + abs(score - 0.5), low=0.0, high=1.0), 4),
            "reasoning_summary": record.reasoning_summary,
            "key_observations": [f"risk_band={record.risk_band}", f"score={score:.3f}"],
            "suggested_next_action": "deescalate_likely_duplicate" if score >= 0.7 else "continue_validation",
            "supporting_evidence_refs": [str(item) for item in _json_list(record.supporting_signal_ids_json)],
            "failure_reason": None,
            "escalation_recommended": score <= 0.25,
            "data": {"duplicate_risk_score": score, "risk_band": record.risk_band},
        }

    async def _evidence_completeness(self, *, program_id: UUID, queue_item_id: UUID | None) -> dict[str, Any]:
        stmt = select(EvidenceCompletenessRecord).where(
            EvidenceCompletenessRecord.program_id == program_id
        ).order_by(EvidenceCompletenessRecord.assessed_at.desc())
        if queue_item_id is not None:
            stmt = stmt.where(EvidenceCompletenessRecord.analyst_queue_item_id == queue_item_id)
        record = await self.db.scalar(stmt.limit(1))
        if record is None:
            return {
                "status": "DEFERRED",
                "confidence": 0.4,
                "reasoning_summary": "No evidence-completeness record found for selected context.",
                "key_observations": [],
                "suggested_next_action": "run_phase7_evidence_scoring",
                "supporting_evidence_refs": [],
                "failure_reason": "evidence completeness record missing",
                "escalation_recommended": False,
                "data": {},
            }
        score = float(record.evidence_completeness_score or 0.0)
        missing = [str(item) for item in _json_list(record.missing_fields_json)]
        return {
            "status": "SUCCEEDED",
            "confidence": round(_clamp(0.55 + (score * 0.35), low=0.0, high=1.0), 4),
            "reasoning_summary": record.reasoning_summary,
            "key_observations": [f"readiness_state={record.readiness_state}", f"missing_fields={len(missing)}"],
            "suggested_next_action": "ready_for_report" if score >= 0.8 else "collect_missing_evidence",
            "supporting_evidence_refs": [record.candidate_key],
            "failure_reason": None,
            "escalation_recommended": score >= 0.85,
            "data": {"evidence_completeness_score": score, "missing_fields": missing},
        }

    async def _opportunity_ranking(self, *, program_id: UUID) -> dict[str, Any]:
        rows = list(
            (
                await self.db.execute(
                    select(OpportunitySelectionRecord)
                    .where(OpportunitySelectionRecord.program_id == program_id)
                    .order_by(
                        OpportunitySelectionRecord.priority_rank.asc().nullslast(),
                        OpportunitySelectionRecord.selection_score.desc(),
                    )
                    .limit(20)
                )
            )
            .scalars()
            .all()
        )
        top = rows[0] if rows else None
        confidence = _clamp((float(top.confidence_score or 0.0) if top else 0.0) + 0.25, low=0.0, high=1.0)
        return {
            "status": "SUCCEEDED" if top else "DEFERRED",
            "confidence": round(confidence, 4),
            "reasoning_summary": (
                f"Top opportunity {top.subject_type}:{top.subject_key} score={top.selection_score:.2f}"
                if top
                else "No opportunity ranking records found."
            ),
            "key_observations": [f"ranking_records={len(rows)}"],
            "suggested_next_action": "prioritize_top_ranked_target" if top else "run_phase7_prediction_cycle",
            "supporting_evidence_refs": [str(row.id) for row in rows[:10]],
            "failure_reason": None if top else "opportunity rankings unavailable",
            "escalation_recommended": bool(top and float(top.selection_score) >= 85.0),
            "data": {
                "top_subject_type": top.subject_type if top else None,
                "top_subject_key": top.subject_key if top else None,
                "top_selection_score": float(top.selection_score) if top else None,
            },
        }

    async def _next_best_workflow(self, *, program_id: UUID, scope_target_id: UUID | None) -> dict[str, Any]:
        stmt = select(WorkflowRecommendationRecord).where(
            WorkflowRecommendationRecord.program_id == program_id
        ).order_by(
            WorkflowRecommendationRecord.action_priority.asc(),
            WorkflowRecommendationRecord.recommended_at.desc(),
        )
        if scope_target_id is not None:
            stmt = stmt.where(WorkflowRecommendationRecord.scope_target_id == scope_target_id)
        recommendation = await self.db.scalar(stmt.limit(1))
        if recommendation is None:
            return {
                "status": "DEFERRED",
                "confidence": 0.35,
                "reasoning_summary": "No recommendation record available in current context.",
                "key_observations": [],
                "suggested_next_action": "run_phase7_prediction_cycle",
                "supporting_evidence_refs": [],
                "failure_reason": "workflow recommendation missing",
                "escalation_recommended": False,
                "data": {},
            }

        confidence = _clamp(
            (1.0 - min(int(recommendation.action_priority or 5), 5) / 7.0)
            + (0.15 if recommendation.recommendation_status == "APPLIED" else 0.0),
            low=0.0,
            high=1.0,
        )
        return {
            "status": "SUCCEEDED",
            "confidence": round(confidence, 4),
            "reasoning_summary": recommendation.reasoning_summary,
            "key_observations": [
                f"recommended_workflow={recommendation.recommended_workflow}",
                f"recommendation_status={recommendation.recommendation_status}",
            ],
            "suggested_next_action": recommendation.recommended_action,
            "supporting_evidence_refs": [str(item) for item in _json_list(recommendation.supporting_record_ids_json)],
            "failure_reason": None,
            "escalation_recommended": recommendation.recommendation_status in {"BLOCKED", "DEFERRED"},
            "data": {
                "recommended_workflow": recommendation.recommended_workflow,
                "recommended_action": recommendation.recommended_action,
                "action_priority": int(recommendation.action_priority or 3),
                "recommendation_status": recommendation.recommendation_status,
            },
        }

    async def _recommendation_explanation(
        self,
        *,
        program_id: UUID,
        scope_target_id: UUID | None,
    ) -> dict[str, Any]:
        stmt = select(WorkflowRecommendationRecord).where(
            WorkflowRecommendationRecord.program_id == program_id
        ).order_by(WorkflowRecommendationRecord.recommended_at.desc())
        if scope_target_id is not None:
            stmt = stmt.where(WorkflowRecommendationRecord.scope_target_id == scope_target_id)
        recommendations = list((await self.db.execute(stmt.limit(5))).scalars().all())
        if not recommendations:
            return {
                "status": "DEFERRED",
                "confidence": 0.35,
                "reasoning_summary": "No recommendation history to explain.",
                "key_observations": [],
                "suggested_next_action": "run_phase7_prediction_cycle",
                "supporting_evidence_refs": [],
                "failure_reason": "recommendation history missing",
                "escalation_recommended": False,
                "data": {},
            }
        top = recommendations[0]
        yield_row = await self.db.scalar(
            select(TargetYieldScoreRecord)
            .where(TargetYieldScoreRecord.program_id == program_id)
            .order_by(TargetYieldScoreRecord.scored_at.desc())
            .limit(1)
        )
        detail_parts = [top.reasoning_summary]
        if yield_row is not None:
            detail_parts.append(f"yield_score={float(yield_row.yield_score):.2f}")
        return {
            "status": "SUCCEEDED",
            "confidence": 0.76,
            "reasoning_summary": " | ".join(detail_parts),
            "key_observations": [
                f"recent_recommendations={len(recommendations)}",
                f"top_action={top.recommended_action}",
            ],
            "suggested_next_action": top.recommended_action,
            "supporting_evidence_refs": [str(item.id) for item in recommendations],
            "failure_reason": None,
            "escalation_recommended": top.recommendation_status == "BLOCKED",
            "data": {
                "top_recommended_workflow": top.recommended_workflow,
                "top_action_priority": int(top.action_priority or 3),
                "yield_score": float(yield_row.yield_score) if yield_row else None,
            },
        }

    async def _alert_summarizer(self, *, program_id: UUID) -> dict[str, Any]:
        alerts = list(
            (
                await self.db.execute(
                    select(NotificationAlertRecord)
                    .where(NotificationAlertRecord.program_id == program_id)
                    .order_by(NotificationAlertRecord.last_seen_at.desc())
                    .limit(300)
                )
            )
            .scalars()
            .all()
        )
        open_count = sum(1 for item in alerts if item.status in {"OPEN", "ACKNOWLEDGED"})
        critical_count = sum(1 for item in alerts if item.severity == "CRITICAL")
        unresolved_ratio = open_count / len(alerts) if alerts else 0.0
        confidence = _clamp(0.4 + (len(alerts) / 500.0) + (critical_count / 20.0), low=0.0, high=1.0)
        return {
            "status": "SUCCEEDED",
            "confidence": round(confidence, 4),
            "reasoning_summary": (
                f"alerts_total={len(alerts)} unresolved={open_count} critical={critical_count}"
            ),
            "key_observations": [
                f"alerts_total={len(alerts)}",
                f"unresolved_ratio={unresolved_ratio:.2f}",
                f"critical_open={critical_count}",
            ],
            "suggested_next_action": "prioritize_alert_triage" if critical_count > 0 else "continue_alert_monitoring",
            "supporting_evidence_refs": [str(item.id) for item in alerts[:15]],
            "failure_reason": None,
            "escalation_recommended": critical_count >= 3,
            "data": {
                "total_alerts": len(alerts),
                "open_or_acknowledged": open_count,
                "critical_count": critical_count,
            },
        }

    async def _analyst_briefing(
        self,
        *,
        program_id: UUID,
        scope_target_id: UUID | None,
    ) -> dict[str, Any]:
        case_stmt = select(AnalystCaseRecord).where(AnalystCaseRecord.program_id == program_id).order_by(
            AnalystCaseRecord.priority.desc(),
            AnalystCaseRecord.last_transition_at.desc().nullslast(),
        )
        prediction_stmt = select(VulnerabilityPredictionRecord).where(
            VulnerabilityPredictionRecord.program_id == program_id
        ).order_by(VulnerabilityPredictionRecord.predicted_at.desc())
        recommendation_stmt = select(WorkflowRecommendationRecord).where(
            WorkflowRecommendationRecord.program_id == program_id
        ).order_by(WorkflowRecommendationRecord.recommended_at.desc())
        if scope_target_id is not None:
            case_stmt = case_stmt.where(AnalystCaseRecord.scope_target_id == scope_target_id)
            prediction_stmt = prediction_stmt.where(
                VulnerabilityPredictionRecord.scope_target_id == scope_target_id
            )
            recommendation_stmt = recommendation_stmt.where(
                WorkflowRecommendationRecord.scope_target_id == scope_target_id
            )

        cases = list((await self.db.execute(case_stmt.limit(12))).scalars().all())
        predictions = list((await self.db.execute(prediction_stmt.limit(12))).scalars().all())
        recommendations = list((await self.db.execute(recommendation_stmt.limit(12))).scalars().all())
        ready_cases = [item for item in cases if item.status == "ready_for_report"]
        high_reportability = [item for item in predictions if float(item.reportability_score or 0.0) >= 0.75]
        confidence = _clamp(
            (len(high_reportability) / max(len(predictions), 1)) * 0.6 + (len(ready_cases) / 10.0),
            low=0.0,
            high=1.0,
        )
        recommended_action = (
            "prioritize_report_drafting"
            if len(ready_cases) > 0
            else (
                recommendations[0].recommended_action
                if recommendations
                else "continue_triage"
            )
        )
        return {
            "status": "SUCCEEDED",
            "confidence": round(confidence, 4),
            "reasoning_summary": (
                f"cases={len(cases)} ready_for_report={len(ready_cases)} "
                f"predictions={len(predictions)} high_reportability={len(high_reportability)}"
            ),
            "key_observations": [
                f"ready_cases={len(ready_cases)}",
                f"high_reportability_predictions={len(high_reportability)}",
                f"recommendations={len(recommendations)}",
            ],
            "suggested_next_action": recommended_action,
            "supporting_evidence_refs": [str(item.id) for item in ready_cases[:5]]
            + [str(item.id) for item in recommendations[:5]],
            "failure_reason": None,
            "escalation_recommended": len(ready_cases) >= 2,
            "data": {
                "ready_case_ids": [str(item.id) for item in ready_cases[:10]],
                "high_reportability_prediction_ids": [str(item.id) for item in high_reportability[:10]],
                "recommendation_ids": [str(item.id) for item in recommendations[:10]],
            },
        }
