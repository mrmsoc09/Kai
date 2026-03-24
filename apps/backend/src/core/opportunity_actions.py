from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse
from uuid import UUID

from .audit_logger import write_audit_record
from .opportunity_catalog import Opportunity
from .opportunity_expansion import OpportunityExpansionResult
from .praison_execution_events import MissionEvent, emit
from .scope_guardrails import (
    ScopePolicy,
    ScopeDecision,
    audit_scope_decision,
    evaluate_target_scope,
    load_scope_policy,
)
from .prometheus_metrics import (
    observe_opportunity_execution_success_rate,
    observe_opportunity_yield,
    observe_opportunity_validated_findings,
    record_opportunity_approved,
    record_opportunity_batch_ready,
    record_opportunity_expansion_approved,
    record_opportunity_expansion_created,
    record_opportunity_expansion_ranked,
    record_opportunity_executed,
    record_opportunity_missions_generated,
    record_opportunity_rejected,
)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_target(value: str) -> str:
    row = str(value or "").strip().lower()
    if not row:
        return ""
    if "://" in row:
        parsed = urlparse(row)
        row = parsed.hostname or parsed.path or row
    if ":" in row:
        row = row.split(":", 1)[0]
    return row.strip(".")


def _target_matches_scope_pattern(target: str, pattern: str) -> bool:
    normalized_target = _normalize_target(target)
    normalized_pattern = _normalize_target(pattern)
    if not normalized_target or not normalized_pattern:
        return False
    if any(ch in normalized_pattern for ch in "*?[]"):
        return fnmatchcase(normalized_target, normalized_pattern)
    return normalized_target == normalized_pattern or normalized_target.endswith(f".{normalized_pattern}")


def _default_runtime_provider():
    from apps.backend.src.core.praison_mission_runtime import get_mission_runtime

    return get_mission_runtime()


def _default_target_cap() -> int:
    raw = os.getenv("K1_OPPORTUNITY_EXECUTION_TARGET_CAP", "5").strip()
    try:
        return max(1, min(50, int(raw)))
    except ValueError:
        return 5


def _state_path() -> Path:
    raw = os.getenv("K1_OPPORTUNITY_ACTION_STATE_PATH", "artifacts/opportunities/action_state.json")
    return Path(raw).resolve()


ALLOWED_TERMINAL_STATES = {"completed", "failed", "cancelled", "rejected"}


@dataclass
class OpportunityActionRecord:
    opportunity_id: str
    tenant_id: str
    source_memory_id: str | None
    source_pattern_id: str | None
    vuln_type: str
    candidate_targets: list[str]
    confidence_score: float
    estimated_yield: float
    duplicate_risk: float
    source_type: str = "catalog_program"
    source_object_id: str | None = None
    expected_yield: float = 0.0
    expansion_candidates: list[dict[str, Any]] = field(default_factory=list)
    approved_targets: list[str] = field(default_factory=list)
    rejected_targets: list[str] = field(default_factory=list)
    target_batches: list[dict[str, Any]] = field(default_factory=list)
    expansion_rationale: str = ""
    expansion_score: float = 0.0
    expected_report_quality: float = 0.0
    recommended_execution_order: list[str] = field(default_factory=list)
    status: str = "proposed"
    approval_state: str = "pending"
    approval_reason: str | None = None
    rejection_reason: str | None = None
    execution_metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utcnow_iso)
    updated_at: str = field(default_factory=_utcnow_iso)
    created_by: str | None = None
    approved_by: str | None = None
    rejected_by: str | None = None
    executed_by: str | None = None
    action_history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "OpportunityActionRecord":
        return cls(
            opportunity_id=str(payload.get("opportunity_id", "")),
            tenant_id=str(payload.get("tenant_id", "")),
            source_memory_id=payload.get("source_memory_id"),
            source_pattern_id=payload.get("source_pattern_id"),
            source_type=str(payload.get("source_type", "catalog_program")),
            source_object_id=payload.get("source_object_id"),
            vuln_type=str(payload.get("vuln_type", "unknown")),
            candidate_targets=[str(value) for value in payload.get("candidate_targets", [])],
            confidence_score=float(payload.get("confidence_score", 0.0)),
            estimated_yield=float(payload.get("estimated_yield", 0.0)),
            duplicate_risk=float(payload.get("duplicate_risk", 0.0)),
            expected_yield=float(payload.get("expected_yield", payload.get("estimated_yield", 0.0))),
            expansion_candidates=[dict(row) for row in payload.get("expansion_candidates", []) if isinstance(row, dict)],
            approved_targets=[str(value) for value in payload.get("approved_targets", [])],
            rejected_targets=[str(value) for value in payload.get("rejected_targets", [])],
            target_batches=[dict(row) for row in payload.get("target_batches", []) if isinstance(row, dict)],
            expansion_rationale=str(payload.get("expansion_rationale", "")),
            expansion_score=float(payload.get("expansion_score", 0.0)),
            expected_report_quality=float(payload.get("expected_report_quality", 0.0)),
            recommended_execution_order=[str(value) for value in payload.get("recommended_execution_order", [])],
            status=str(payload.get("status", "proposed")),
            approval_state=str(payload.get("approval_state", "pending")),
            approval_reason=payload.get("approval_reason"),
            rejection_reason=payload.get("rejection_reason"),
            execution_metadata=dict(payload.get("execution_metadata", {})),
            created_at=str(payload.get("created_at", _utcnow_iso())),
            updated_at=str(payload.get("updated_at", _utcnow_iso())),
            created_by=payload.get("created_by"),
            approved_by=payload.get("approved_by"),
            rejected_by=payload.get("rejected_by"),
            executed_by=payload.get("executed_by"),
            action_history=list(payload.get("action_history", [])),
        )


class OpportunityActionService:
    def __init__(
        self,
        *,
        runtime_provider: Callable[[], Any] | None = None,
        event_emitter: Callable[[MissionEvent], None] | None = None,
        target_cap: int | None = None,
    ) -> None:
        self._runtime_provider = runtime_provider or _default_runtime_provider
        self._event_emitter = event_emitter or emit
        self._target_cap = target_cap if target_cap is not None else _default_target_cap()
        self._lock = threading.Lock()
        self._policy = load_scope_policy()

    def _load(self) -> dict[str, dict[str, dict[str, Any]]]:
        path = _state_path()
        if not path.exists():
            return {}
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return {}
            raw_tenants = payload.get("tenants", {})
            if not isinstance(raw_tenants, dict):
                return {}
            return {
                str(tenant_id): {
                    str(opportunity_id): dict(record)
                    for opportunity_id, record in tenant_records.items()
                    if isinstance(tenant_records, dict) and isinstance(record, dict)
                }
                for tenant_id, tenant_records in raw_tenants.items()
            }
        except Exception:
            return {}

    def _save(self, tenants: dict[str, dict[str, dict[str, Any]]]) -> None:
        path = _state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"tenants": tenants, "updated_at": _utcnow_iso()}
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def _record_from_opportunity(
        self,
        opportunity: Opportunity,
        *,
        tenant_id: str,
        created_by: str | None,
    ) -> OpportunityActionRecord:
        target_count = max(1, len(opportunity.scope_domains))
        estimated_yield = round(opportunity.priority_score * target_count * 0.6, 2)
        return OpportunityActionRecord(
            opportunity_id=opportunity.id,
            tenant_id=tenant_id,
            source_memory_id=None,
            source_pattern_id=None,
            vuln_type=opportunity.vuln_types[0] if opportunity.vuln_types else "unknown",
            candidate_targets=list(opportunity.scope_domains),
            confidence_score=float(opportunity.priority_score),
            estimated_yield=estimated_yield,
            expected_yield=estimated_yield,
            duplicate_risk=0.0,
            source_type="catalog_program",
            source_object_id=opportunity.id,
            created_by=created_by,
            execution_metadata={
                "mission_lineage": [],
                "missions_launched": 0,
                "missions_completed": 0,
                "missions_failed": 0,
                "findings_produced": 0,
                "validated_findings_produced": 0,
                "actual_yield_proxy": 0.0,
                "report_ids": [],
                "report_ids_by_mission": {},
                "reports_generated": 0,
                "reports_deduplicated": 0,
                "last_error": None,
                "target_review": {
                    "approved_targets": list(opportunity.scope_domains),
                    "rejected_targets": [],
                    "batch_ids": [],
                },
            },
        )

    def get_existing_state(self, tenant_id: str, opportunity_id: str) -> OpportunityActionRecord | None:
        with self._lock:
            tenants = self._load()
            record = tenants.get(tenant_id, {}).get(opportunity_id)
            return OpportunityActionRecord.from_dict(record) if record else None

    def ensure_state(
        self,
        opportunity: Opportunity,
        *,
        tenant_id: str,
        created_by: str | None,
    ) -> OpportunityActionRecord:
        with self._lock:
            tenants = self._load()
            tenant_records = tenants.setdefault(tenant_id, {})
            existing = tenant_records.get(opportunity.id)
            if existing:
                return OpportunityActionRecord.from_dict(existing)
            created = self._record_from_opportunity(opportunity, tenant_id=tenant_id, created_by=created_by)
            tenant_records[opportunity.id] = created.to_dict()
            self._save(tenants)
            return created

    def _select_review_targets(
        self,
        record: OpportunityActionRecord,
        *,
        approved_targets: list[str] | None = None,
        rejected_targets: list[str] | None = None,
        batch_ids: list[str] | None = None,
    ) -> tuple[list[str], list[str]]:
        available_targets = {_normalize_target(row) for row in record.candidate_targets if _normalize_target(row)}
        batch_lookup: dict[str, list[str]] = {}
        for row in record.target_batches:
            if not isinstance(row, dict):
                continue
            batch_id = str(row.get("batch_id") or "").strip()
            if not batch_id:
                continue
            targets = [_normalize_target(value) for value in row.get("targets", []) if _normalize_target(value)]
            if targets:
                batch_lookup[batch_id] = targets

        selected: set[str] = set()
        if batch_ids:
            for batch_id in batch_ids:
                selected.update(batch_lookup.get(str(batch_id), []))
        if approved_targets:
            selected.update(_normalize_target(row) for row in approved_targets if _normalize_target(row))

        if selected:
            approved = sorted(target for target in selected if target in available_targets)
        else:
            approved = sorted(available_targets)

        rejected: set[str] = set()
        if rejected_targets:
            rejected.update(_normalize_target(row) for row in rejected_targets if _normalize_target(row))
        for target in available_targets:
            if target not in approved:
                rejected.add(target)
        return approved, sorted(target for target in rejected if target)

    def apply_expansion(
        self,
        opportunity: Opportunity,
        *,
        tenant_id: str,
        actor: str,
        source_type: str,
        source_object_id: str | None,
        source_memory_id: str | None,
        source_pattern_id: str | None,
        expansion: OpportunityExpansionResult,
        source_context: dict[str, Any] | None = None,
    ) -> OpportunityActionRecord:
        record = self.ensure_state(opportunity, tenant_id=tenant_id, created_by=actor)
        candidate_targets = [_normalize_target(row.target) for row in expansion.expansion_candidates if _normalize_target(row.target)]
        if not candidate_targets:
            candidate_targets = [_normalize_target(row) for row in record.candidate_targets if _normalize_target(row)]
        blocked_targets = [
            _normalize_target(row.get("target", ""))
            for row in expansion.blocked_targets
            if isinstance(row, dict) and _normalize_target(row.get("target", ""))
        ]
        approved_targets = sorted(set(candidate_targets))
        rejected_targets = sorted(set(blocked_targets))
        record.source_type = source_type or "validated_finding"
        record.source_object_id = source_object_id
        record.source_memory_id = source_memory_id
        record.source_pattern_id = source_pattern_id
        record.vuln_type = expansion.source_vuln_type or record.vuln_type
        record.candidate_targets = list(candidate_targets)
        record.confidence_score = max(record.confidence_score, float(expansion.confidence))
        record.estimated_yield = max(float(record.estimated_yield), float(expansion.expected_yield))
        record.expected_yield = float(expansion.expected_yield)
        record.duplicate_risk = max(float(record.duplicate_risk), float(expansion.duplicate_risk))
        record.expansion_candidates = [row.to_dict() for row in expansion.expansion_candidates]
        record.target_batches = [row.to_dict() for row in expansion.target_batches]
        record.expansion_rationale = expansion.expansion_rationale
        record.expansion_score = float(expansion.expansion_score)
        record.expected_report_quality = float(expansion.expected_report_quality)
        record.recommended_execution_order = list(expansion.recommended_execution_order)
        record.approved_targets = approved_targets
        record.rejected_targets = rejected_targets
        record.updated_at = _utcnow_iso()
        record.execution_metadata["target_review"] = {
            "approved_targets": approved_targets,
            "rejected_targets": rejected_targets,
            "batch_ids": list(expansion.recommended_execution_order),
            "reviewed_by": actor,
            "reviewed_at": _utcnow_iso(),
        }
        if source_context:
            record.execution_metadata["source_context"] = dict(source_context)
        detail = {
            "source_type": record.source_type,
            "source_object_id": record.source_object_id,
            "source_memory_id": record.source_memory_id,
            "candidate_count": len(record.expansion_candidates),
            "batch_count": len(record.target_batches),
            "blocked_targets": expansion.blocked_targets,
            "expansion_score": record.expansion_score,
        }
        self._append_history(record, "expansion_created", actor, record.expansion_rationale, detail)
        self._audit("opportunity.expansion.created", record, actor, record.expansion_rationale, detail)
        self._emit_opportunity_event("opportunity_expansion_created", record, detail=detail)
        self._emit_opportunity_event(
            "opportunity_expansion_ranked",
            record,
            detail={
                "candidate_count": len(record.expansion_candidates),
                "recommended_execution_order": list(record.recommended_execution_order),
                "expansion_score": record.expansion_score,
                "expected_yield": record.expected_yield,
            },
        )
        self._emit_opportunity_event(
            "opportunity_batch_ready",
            record,
            detail={
                "batch_count": len(record.target_batches),
                "batches": list(record.target_batches),
            },
        )
        record_opportunity_expansion_created()
        record_opportunity_expansion_ranked()
        record_opportunity_batch_ready(len(record.target_batches))
        return self._persist(record)

    def _persist(self, record: OpportunityActionRecord) -> OpportunityActionRecord:
        with self._lock:
            tenants = self._load()
            tenant_records = tenants.setdefault(record.tenant_id, {})
            tenant_records[record.opportunity_id] = record.to_dict()
            self._save(tenants)
        return record

    def _append_history(self, record: OpportunityActionRecord, action: str, actor: str, reason: str | None = None, detail: dict[str, Any] | None = None) -> None:
        record.action_history.append(
            {
                "timestamp": _utcnow_iso(),
                "action": action,
                "actor": actor,
                "reason": reason or "",
                "detail": detail or {},
            }
        )

    def _audit(self, event_type: str, record: OpportunityActionRecord, actor: str, reason: str | None = None, detail: dict[str, Any] | None = None) -> None:
        write_audit_record(
            event_type=event_type,
            tenant_id=record.tenant_id,
            user_id=actor,
            mission_id="",
            decision=record.status,
            reason=reason or "",
            detail={
                "opportunity_id": record.opportunity_id,
                "approval_state": record.approval_state,
                "execution_metadata": record.execution_metadata,
                **(detail or {}),
            },
        )

    def _emit_opportunity_event(
        self,
        event_type: str,
        record: OpportunityActionRecord,
        *,
        detail: dict[str, Any] | None = None,
        mission_id: str | None = None,
    ) -> None:
        payload = {
            "tenant_id": record.tenant_id,
            "opportunity_id": record.opportunity_id,
            "status": record.status,
            "approval_state": record.approval_state,
            **(detail or {}),
        }
        event = MissionEvent(
            event_type=event_type,
            mission_id=mission_id or f"opportunity:{record.opportunity_id}",
            workflow_id=f"opportunity:{record.opportunity_id}",
            program_id=record.vuln_type,
            detail=payload,
        )
        self._event_emitter(event)

    def _effective_scope_policy(self, scope_patterns: list[str] | None) -> ScopePolicy:
        if not scope_patterns:
            return self._policy

        allowlist = list(self._policy.allowlist)
        seen = {row.lower() for row in allowlist}
        for raw_pattern in scope_patterns:
            pattern = _normalize_target(raw_pattern)
            if not pattern:
                continue
            if pattern not in seen:
                allowlist.append(pattern)
                seen.add(pattern)
            if pattern.startswith("*."):
                # Treat wildcard scope as allowing the root domain as the seed target.
                root_domain = pattern[2:]
                if root_domain and root_domain not in seen:
                    allowlist.append(root_domain)
                    seen.add(root_domain)

        return ScopePolicy(
            allowlist=allowlist,
            denylist=list(self._policy.denylist),
            cidr_allowlist=list(self._policy.cidr_allowlist),
            safe_mode_default=self._policy.safe_mode_default,
            strict_allowlist=self._policy.strict_allowlist,
        )

    def _materialize_executable_target(self, target: str) -> tuple[str | None, str]:
        normalized = _normalize_target(target)
        if not normalized:
            return None, "invalid_target"
        if normalized.startswith("*."):
            root_domain = normalized[2:]
            if root_domain and "." in root_domain:
                return root_domain, "wildcard_seed_target"
            return None, "wildcard_target_not_executable"
        if any(ch in normalized for ch in "*?[]"):
            return None, "wildcard_target_not_executable"
        if "." not in normalized:
            return None, "non_network_target"
        return normalized, "ok"

    def _validate_targets(
        self,
        targets: list[str],
        *,
        scope_patterns: list[str] | None = None,
    ) -> tuple[list[str], list[dict[str, str]]]:
        policy = self._effective_scope_policy(scope_patterns)
        valid: list[str] = []
        blocked: list[dict[str, str]] = []
        for raw_target in targets:
            target, executable_reason = self._materialize_executable_target(raw_target)
            if not target:
                blocked.append({"target": raw_target, "reason": executable_reason})
                continue

            decision: ScopeDecision = evaluate_target_scope(target, policy)
            audit_scope_decision(decision)
            if decision.allowed:
                valid.append(target)
            else:
                blocked.append(
                    {
                        "target": raw_target,
                        "evaluated_target": target,
                        "reason": decision.reason,
                    }
                )
        return valid, blocked

    def _parse_tenant_uuid(self, tenant_id: str) -> UUID:
        try:
            return UUID(tenant_id)
        except ValueError as exc:
            raise ValueError("tenant_context_invalid") from exc

    def approve(
        self,
        opportunity: Opportunity,
        *,
        tenant_id: str,
        actor: str,
        reason: str | None = None,
        approved_targets: list[str] | None = None,
        rejected_targets: list[str] | None = None,
        batch_ids: list[str] | None = None,
    ) -> OpportunityActionRecord:
        record = self.ensure_state(opportunity, tenant_id=tenant_id, created_by=actor)
        if record.status in {"executing", "completed"}:
            raise ValueError(f"invalid_state:{record.status}")
        reviewed_approved, reviewed_rejected = self._select_review_targets(
            record,
            approved_targets=approved_targets,
            rejected_targets=rejected_targets,
            batch_ids=batch_ids,
        )
        if reviewed_approved:
            record.approved_targets = reviewed_approved
        if reviewed_rejected:
            record.rejected_targets = reviewed_rejected
        record.status = "approved"
        record.approval_state = "approved"
        record.approval_reason = reason or "Approved for controlled execution."
        record.rejection_reason = None
        record.approved_by = actor
        record.updated_at = _utcnow_iso()
        review_detail = {
            "approved_target_count": len(record.approved_targets or record.candidate_targets),
            "rejected_target_count": len(record.rejected_targets),
            "batch_ids": [str(value) for value in (batch_ids or [])],
        }
        record.execution_metadata["target_review"] = {
            "approved_targets": list(record.approved_targets or record.candidate_targets),
            "rejected_targets": list(record.rejected_targets),
            "batch_ids": [str(value) for value in (batch_ids or [])],
            "reviewed_by": actor,
            "reviewed_at": _utcnow_iso(),
        }
        self._append_history(record, "approve", actor, record.approval_reason, review_detail)
        self._audit("opportunity.approved", record, actor, record.approval_reason, review_detail)
        self._emit_opportunity_event("opportunity_approved", record, detail={"reason": record.approval_reason})
        if record.expansion_candidates:
            self._emit_opportunity_event("opportunity_expansion_approved", record, detail=review_detail)
            record_opportunity_expansion_approved(len(record.approved_targets or record.candidate_targets))
        record_opportunity_approved()
        return self._persist(record)

    def reject(self, opportunity: Opportunity, *, tenant_id: str, actor: str, reason: str | None = None) -> OpportunityActionRecord:
        record = self.ensure_state(opportunity, tenant_id=tenant_id, created_by=actor)
        if record.status == "executing":
            raise ValueError("invalid_state:executing")
        record.status = "rejected"
        record.approval_state = "rejected"
        record.rejection_reason = reason or "Rejected by operator."
        record.rejected_by = actor
        record.updated_at = _utcnow_iso()
        self._append_history(record, "reject", actor, record.rejection_reason)
        self._audit("opportunity.rejected", record, actor, record.rejection_reason)
        self._emit_opportunity_event("opportunity_rejected", record, detail={"reason": record.rejection_reason})
        record_opportunity_rejected()
        return self._persist(record)

    def execute(
        self,
        opportunity: Opportunity,
        *,
        tenant_id: str,
        actor: str,
        reason: str | None = None,
        execution_mode: str = "live",
        max_targets: int | None = None,
    ) -> OpportunityActionRecord:
        record = self.ensure_state(opportunity, tenant_id=tenant_id, created_by=actor)
        if record.approval_state != "approved":
            raise ValueError("approval_required")
        if record.status in {"executing", "completed"}:
            raise ValueError(f"invalid_state:{record.status}")

        execution_targets = list(record.approved_targets) if record.approved_targets else list(record.candidate_targets)
        valid_targets, blocked_targets = self._validate_targets(
            execution_targets,
            scope_patterns=record.candidate_targets,
        )
        deduped_valid_targets: list[str] = []
        seen_targets: set[str] = set()
        for target in valid_targets:
            if target in seen_targets:
                continue
            seen_targets.add(target)
            deduped_valid_targets.append(target)

        valid_targets = deduped_valid_targets
        if not valid_targets:
            record.status = "failed"
            record.updated_at = _utcnow_iso()
            record.execution_metadata["blocked_targets"] = blocked_targets
            record.execution_metadata["last_error"] = "no_executable_targets"
            self._append_history(record, "execute_failed", actor, "No in-scope executable targets.", {"blocked_targets": blocked_targets})
            self._audit("opportunity.execution.failed", record, actor, "No executable targets.", {"blocked_targets": blocked_targets})
            self._emit_opportunity_event(
                "opportunity_execution_failed",
                record,
                detail={"error": "no_executable_targets", "blocked_targets": blocked_targets},
            )
            return self._persist(record)

        target_limit = max_targets if max_targets is not None else self._target_cap
        target_limit = max(1, min(50, int(target_limit)))
        selected_targets = valid_targets[:target_limit]
        tenant_uuid = self._parse_tenant_uuid(tenant_id)
        runtime = self._runtime_provider()

        mission_lineage: list[dict[str, str]] = []
        for index, target in enumerate(selected_targets, start=1):
            workflow_id = f"opportunity-{record.opportunity_id}-{index}"
            handle = runtime.create_mission(
                tenant_id=tenant_uuid,
                workflow_id=workflow_id,
                program_id=target,
                mission_name=f"Opportunity {record.opportunity_id} target {target}",
                execution_mode=execution_mode,
            )
            mission_lineage.append(
                {
                    "mission_id": handle.mission_id,
                    "target": target,
                    "workflow_id": workflow_id,
                    "program_id": target,
                }
            )

        record.status = "executing"
        record.executed_by = actor
        record.updated_at = _utcnow_iso()
        record.execution_metadata.update(
            {
                "requested_target_count": len(execution_targets),
                "valid_targets": valid_targets,
                "blocked_targets": blocked_targets,
                "selected_targets": selected_targets,
                "target_cap": target_limit,
                "mission_lineage": mission_lineage,
                "mission_ids": [row["mission_id"] for row in mission_lineage],
                "missions_launched": len(mission_lineage),
                "missions_completed": 0,
                "missions_failed": 0,
                "last_execution_started_at": _utcnow_iso(),
                "execution_reason": reason or "",
                "completion_event_emitted": False,
                "last_error": None,
            }
        )
        self._append_history(
            record,
            "execute",
            actor,
            reason,
            {
                "selected_targets": selected_targets,
                "blocked_targets": blocked_targets,
                "mission_ids": record.execution_metadata.get("mission_ids", []),
            },
        )
        self._audit(
            "opportunity.execution.started",
            record,
            actor,
            reason,
            {
                "selected_targets": selected_targets,
                "blocked_targets": blocked_targets,
                "mission_ids": record.execution_metadata.get("mission_ids", []),
            },
        )
        self._emit_opportunity_event(
            "opportunity_execution_started",
            record,
            detail={
                "selected_targets": selected_targets,
                "blocked_targets": blocked_targets,
                "mission_ids": record.execution_metadata.get("mission_ids", []),
            },
            mission_id=(record.execution_metadata.get("mission_ids", [None])[0] or None),
        )
        record_opportunity_executed()
        record_opportunity_missions_generated(len(mission_lineage))
        return self._persist(record)

    def _is_terminal_mission_state(self, value: str) -> bool:
        return value in {"completed", "failed", "cancelled", "paused"}

    def _pick_chain_for_finding(self, finding: dict[str, Any], chains: list[dict[str, Any]]) -> dict[str, Any] | None:
        finding_id = str(finding.get("finding_id") or finding.get("id") or "").strip()
        vuln_type = str(finding.get("vuln_type") or finding.get("type") or "").strip().lower()
        if not chains:
            return None
        if not finding_id and not vuln_type:
            return chains[0]
        for chain in chains:
            if not isinstance(chain, dict):
                continue
            nodes = chain.get("nodes")
            if not isinstance(nodes, list):
                continue
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                node_value = str(node.get("value") or "").strip()
                node_vuln = str(node.get("vuln_type") or "").strip().lower()
                if finding_id and node_value and node_value == finding_id:
                    return chain
                if vuln_type and node_vuln and node_vuln == vuln_type:
                    return chain
        return chains[0]

    def _generate_reports_for_execution(
        self,
        record: OpportunityActionRecord,
        mission_states: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        if not mission_states:
            return {
                "report_ids": [],
                "report_ids_by_mission": {},
                "reports_generated": 0,
                "reports_deduplicated": 0,
            }

        try:
            from .report_engine import get_report_engine
        except Exception:
            return {
                "report_ids": [],
                "report_ids_by_mission": {},
                "reports_generated": 0,
                "reports_deduplicated": 0,
            }

        engine = get_report_engine()
        report_ids: list[str] = []
        report_ids_by_mission: dict[str, list[str]] = {}
        generated = 0
        deduplicated = 0
        lineage_rows = record.execution_metadata.get("mission_lineage", [])
        lineage_by_mission = {
            str(row.get("mission_id")): row
            for row in lineage_rows
            if isinstance(row, dict) and row.get("mission_id")
        }

        for mission_id, state in mission_states.items():
            if not isinstance(state, dict):
                continue
            lineage = lineage_by_mission.get(mission_id, {})
            target = str(lineage.get("target") or "").strip()
            mission_reports: list[str] = []
            artifacts = state.get("artifacts", [])
            artifact_rows = artifacts if isinstance(artifacts, list) else []
            chains = state.get("exploit_chains", [])
            chain_rows = chains if isinstance(chains, list) else []

            validated_findings = state.get("validated_findings", [])
            finding_rows = validated_findings if isinstance(validated_findings, list) else []
            for finding in finding_rows:
                if not isinstance(finding, dict):
                    continue
                report_finding = dict(finding)
                report_finding.setdefault("target", target)
                report_finding.setdefault("severity", "high")
                report_finding.setdefault("validated", True)
                report_finding.setdefault("confidence_score", 0.75)
                exploit_chain = self._pick_chain_for_finding(report_finding, chain_rows)
                report, was_deduplicated = engine.generate_and_store_report(
                    finding=report_finding,
                    exploit_chain=exploit_chain,
                    artifacts=artifact_rows,
                    tenant_id=record.tenant_id,
                    mission_id=mission_id,
                    opportunity_id=record.opportunity_id,
                    generated_by=record.executed_by or "system",
                    deduplicate=True,
                )
                generated += 1
                if was_deduplicated:
                    deduplicated += 1
                mission_reports.append(report.report_id)
                report_ids.append(report.report_id)

            if not mission_reports and chain_rows:
                primary_chain = chain_rows[0] if isinstance(chain_rows[0], dict) else None
                if primary_chain:
                    chain_finding = {
                        "finding_id": f"{mission_id}-chain",
                        "title": f"Exploit chain detected for {target or mission_id}",
                        "vuln_type": record.vuln_type,
                        "target": target or mission_id,
                        "severity": "high",
                        "summary": "Exploit chain was detected during opportunity-derived mission execution.",
                        "validation_evidence": ["Exploit chain linkage detected from mission telemetry."],
                        "confidence_score": max(record.confidence_score, 0.65),
                    }
                    report, was_deduplicated = engine.generate_and_store_report(
                        finding=chain_finding,
                        exploit_chain=primary_chain,
                        artifacts=artifact_rows,
                        tenant_id=record.tenant_id,
                        mission_id=mission_id,
                        opportunity_id=record.opportunity_id,
                        generated_by=record.executed_by or "system",
                        deduplicate=True,
                    )
                    generated += 1
                    if was_deduplicated:
                        deduplicated += 1
                    mission_reports.append(report.report_id)
                    report_ids.append(report.report_id)

            if mission_reports:
                report_ids_by_mission[mission_id] = mission_reports

        unique_report_ids: list[str] = []
        seen: set[str] = set()
        for report_id in report_ids:
            if report_id in seen:
                continue
            seen.add(report_id)
            unique_report_ids.append(report_id)

        return {
            "report_ids": unique_report_ids,
            "report_ids_by_mission": report_ids_by_mission,
            "reports_generated": generated,
            "reports_deduplicated": deduplicated,
        }

    def refresh_execution(self, record: OpportunityActionRecord) -> OpportunityActionRecord:
        if record.status != "executing":
            return record

        mission_ids = [str(value) for value in record.execution_metadata.get("mission_ids", []) if value]
        if not mission_ids:
            return record

        try:
            runtime = self._runtime_provider()
            tenant_uuid = self._parse_tenant_uuid(record.tenant_id)
        except Exception:
            return record

        completed = 0
        failed = 0
        findings = 0
        validated = 0
        all_terminal = True
        mission_states: dict[str, dict[str, Any]] = {}

        for mission_id in mission_ids:
            try:
                status = runtime.get_status(mission_id, tenant_id=tenant_uuid)
                state_value = str(status.state)
                if state_value == "completed":
                    completed += 1
                elif state_value in {"failed", "cancelled"}:
                    failed += 1
                else:
                    all_terminal = False
                mission_state = runtime.get_state(mission_id)
                if isinstance(mission_state, dict):
                    mission_states[mission_id] = mission_state
                findings += len(mission_state.get("findings", [])) if isinstance(mission_state.get("findings"), list) else 0
                findings += len(mission_state.get("vuln_candidates", [])) if isinstance(mission_state.get("vuln_candidates"), list) else 0
                validated += len(mission_state.get("validated_findings", [])) if isinstance(mission_state.get("validated_findings"), list) else 0
            except Exception:
                all_terminal = False

        record.execution_metadata["missions_completed"] = completed
        record.execution_metadata["missions_failed"] = failed
        record.execution_metadata["findings_produced"] = findings
        record.execution_metadata["validated_findings_produced"] = validated
        record.execution_metadata["actual_yield_proxy"] = round(validated + (0.25 * findings), 3)
        record.updated_at = _utcnow_iso()

        if not all_terminal:
            return self._persist(record)

        success_rate = completed / max(1, len(mission_ids))
        record.execution_metadata["execution_success_rate"] = round(success_rate, 4)
        record.execution_metadata["last_execution_completed_at"] = _utcnow_iso()
        report_summary = self._generate_reports_for_execution(record, mission_states)
        record.execution_metadata["report_ids"] = report_summary.get("report_ids", [])
        record.execution_metadata["report_ids_by_mission"] = report_summary.get("report_ids_by_mission", {})
        record.execution_metadata["reports_generated"] = int(report_summary.get("reports_generated", 0))
        record.execution_metadata["reports_deduplicated"] = int(report_summary.get("reports_deduplicated", 0))

        if failed > 0 and completed == 0:
            record.status = "failed"
            event_type = "opportunity_execution_failed"
        else:
            record.status = "completed"
            event_type = "opportunity_execution_completed"

        if not bool(record.execution_metadata.get("completion_event_emitted")):
            record.execution_metadata["completion_event_emitted"] = True
            self._emit_opportunity_event(
                event_type,
                record,
                detail={
                    "mission_ids": mission_ids,
                    "missions_completed": completed,
                    "missions_failed": failed,
                    "findings_produced": findings,
                    "validated_findings_produced": validated,
                    "execution_success_rate": success_rate,
                    "actual_yield_proxy": record.execution_metadata.get("actual_yield_proxy", 0.0),
                    "report_ids": record.execution_metadata.get("report_ids", []),
                    "reports_generated": record.execution_metadata.get("reports_generated", 0),
                },
                mission_id=(mission_ids[0] if mission_ids else None),
            )
            self._audit(
                "opportunity.execution.completed" if record.status == "completed" else "opportunity.execution.failed",
                record,
                actor=record.executed_by or "",
                reason=f"Execution {record.status}",
            )
            observe_opportunity_execution_success_rate(success_rate)
            observe_opportunity_validated_findings(validated)
            observe_opportunity_yield(float(record.execution_metadata.get("actual_yield_proxy", 0.0)))

        return self._persist(record)

    def start_execution_missions(self, record: OpportunityActionRecord) -> None:
        mission_ids = [str(value) for value in record.execution_metadata.get("mission_ids", []) if value]
        if not mission_ids:
            return
        try:
            runtime = self._runtime_provider()
            tenant_uuid = self._parse_tenant_uuid(record.tenant_id)
        except Exception as exc:
            record.status = "failed"
            record.updated_at = _utcnow_iso()
            record.execution_metadata["last_error"] = str(exc)
            self._append_history(record, "execute_dispatch_failed", record.executed_by or "", str(exc))
            self._emit_opportunity_event(
                "opportunity_execution_failed",
                record,
                detail={"error": str(exc), "mission_ids": mission_ids},
                mission_id=(mission_ids[0] if mission_ids else None),
            )
            self._persist(record)
            return

        any_started = False
        last_error: str | None = None
        for mission_id in mission_ids:
            try:
                runtime.start_mission(mission_id, tenant_id=tenant_uuid)
                any_started = True
            except Exception as exc:
                last_error = str(exc)

        if any_started:
            self._persist(record)
            return

        record.status = "failed"
        record.updated_at = _utcnow_iso()
        record.execution_metadata["last_error"] = last_error or "mission_start_failed"
        self._append_history(record, "execute_dispatch_failed", record.executed_by or "", last_error)
        self._emit_opportunity_event(
            "opportunity_execution_failed",
            record,
            detail={"error": record.execution_metadata["last_error"], "mission_ids": mission_ids},
            mission_id=(mission_ids[0] if mission_ids else None),
        )
        self._persist(record)

    def merge_opportunity_view(self, opportunity: Opportunity, *, tenant_id: str, created_by: str | None) -> dict[str, Any]:
        existing = self.get_existing_state(tenant_id, opportunity.id)
        if existing is None:
            state = self.ensure_state(opportunity, tenant_id=tenant_id, created_by=created_by)
        else:
            state = self.refresh_execution(existing)
        return state.to_dict()


_SERVICE: OpportunityActionService | None = None
_SERVICE_LOCK = threading.Lock()


def get_opportunity_action_service() -> OpportunityActionService:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = OpportunityActionService()
        return _SERVICE
