from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from .praison_execution_events import MissionEvent, get_event_bus
from .ws import manager

logger = logging.getLogger(__name__)

_SUBSCRIBED = False
_SUBSCRIBE_LOCK = threading.Lock()
_LOOP: asyncio.AbstractEventLoop | None = None


def _event_category(event_type: str) -> str:
    if event_type.startswith("opportunity_"):
        return "operation"
    if event_type.startswith("simulation_") or event_type.startswith("replay_"):
        return "simulation"
    if event_type in {"fixture_applied", "mock_tool_result_emitted", "replay_event_emitted"}:
        return "simulation"
    if event_type in {"approval_requested", "approval_resolved", "policy_decision"}:
        return "governance"
    if event_type.startswith("approval_"):
        return "governance"
    if event_type.startswith("artifact_"):
        return "artifact"
    if event_type.startswith("mission_"):
        return "lifecycle"
    if event_type.startswith("node_"):
        return "node"
    if event_type.startswith("phase_"):
        return "lifecycle"
    return "operation"


def _event_status(event: MissionEvent) -> str | None:
    event_type = event.event_type
    if event_type == "opportunity_expansion_created":
        return "created"
    if event_type == "opportunity_expansion_ranked":
        return "ranked"
    if event_type == "opportunity_batch_ready":
        return "ready"
    if event_type == "opportunity_expansion_approved":
        return "approved"
    if event_type == "opportunity_approved":
        return "approved"
    if event_type == "opportunity_rejected":
        return "rejected"
    if event_type == "opportunity_execution_started":
        return "running"
    if event_type == "opportunity_execution_completed":
        return "completed"
    if event_type == "opportunity_execution_failed":
        return "failed"
    if event_type == "mission_started":
        return "running"
    if event_type == "mission_completed":
        success = bool(event.detail.get("success", True))
        return "completed" if success else "failed"
    if event_type == "node_entered":
        return "running"
    if event_type == "node_completed":
        return "completed"
    if event_type == "node_failed":
        return "failed"
    if event_type == "approval_requested":
        return "pending"
    if event_type == "approval_resolved":
        decision = event.detail.get("decision")
        return str(decision) if isinstance(decision, str) else "resolved"
    if event_type == "policy_decision":
        decision = event.detail.get("decision")
        return str(decision) if isinstance(decision, str) else None
    if event_type in {"simulation_started", "replay_started"}:
        return "running"
    if event_type in {"simulation_completed", "replay_completed"}:
        return "completed"
    if event_type == "simulation_failed":
        return "failed"
    return None


def _event_summary(event: MissionEvent) -> str:
    detail = event.detail
    if event.event_type == "opportunity_expansion_created":
        count = detail.get("candidate_count")
        if isinstance(count, int):
            return f"Expansion created with {count} candidates"
        return "Opportunity expansion created"
    if event.event_type == "opportunity_expansion_ranked":
        return "Opportunity expansion ranked"
    if event.event_type == "opportunity_batch_ready":
        count = detail.get("batch_count")
        if isinstance(count, int):
            return f"{count} expansion batches ready"
        return "Opportunity batches ready"
    if event.event_type == "opportunity_expansion_approved":
        reviewed = detail.get("approved_target_count")
        if isinstance(reviewed, int):
            return f"Expansion approved with {reviewed} targets"
        return "Opportunity expansion approved"
    if event.event_type == "opportunity_approved":
        return "Opportunity approved"
    if event.event_type == "opportunity_rejected":
        return "Opportunity rejected"
    if event.event_type == "opportunity_execution_started":
        return "Opportunity execution started"
    if event.event_type == "opportunity_execution_completed":
        return "Opportunity execution completed"
    if event.event_type == "opportunity_execution_failed":
        error = detail.get("error")
        if isinstance(error, str) and error:
            return error
        return "Opportunity execution failed"
    if event.event_type == "approval_requested":
        reason = detail.get("reason")
        if isinstance(reason, str) and reason:
            return reason
        return "Approval requested"
    if event.event_type == "approval_resolved":
        decision = detail.get("decision")
        if isinstance(decision, str) and decision:
            return f"Approval {decision}"
        return "Approval resolved"
    if event.event_type == "node_failed":
        error = detail.get("error")
        if isinstance(error, str) and error:
            return error
        return "Node failed"
    if event.event_type == "mission_completed":
        success = bool(detail.get("success", True))
        return "Mission completed" if success else "Mission failed"
    if event.event_type == "policy_decision":
        reason = detail.get("reason")
        if isinstance(reason, str) and reason:
            return reason
        return "Policy decision"
    return event.event_type.replace("_", " ")

def _resolve_tenant_for_mission(mission_id: str) -> str | None:
    try:
        from .praison_mission_runtime import get_mission_runtime
    except Exception as exc:
        logger.debug("Mission runtime import unavailable for realtime bridge: %s", exc)
        return None

    try:
        runtime = get_mission_runtime()
        tenant_id = runtime.tenant_for_mission(mission_id)
        return str(tenant_id) if tenant_id else None
    except Exception as exc:
        logger.debug("Tenant lookup failed for mission %s: %s", mission_id, exc)
        return None


def normalize_mission_event(event: MissionEvent) -> dict[str, Any] | None:
    if not event.mission_id:
        return None

    tenant_id = _resolve_tenant_for_mission(event.mission_id)
    if not tenant_id:
        tenant_from_detail = event.detail.get("tenant_id")
        if isinstance(tenant_from_detail, str) and tenant_from_detail.strip():
            tenant_id = tenant_from_detail.strip()
    if not tenant_id:
        return None

    approval_id = event.detail.get("approval_id")
    return {
        "schema_version": "1.0",
        "event_id": event.event_id,
        "event_type": event.event_type,
        "timestamp": event.timestamp,
        "tenant_id": tenant_id,
        "mission_id": event.mission_id,
        "workflow_id": event.workflow_id,
        "program_id": event.program_id,
        "node_id": event.node_id or None,
        "phase": event.phase or None,
        "status": _event_status(event),
        "summary": _event_summary(event),
        "detail": event.detail,
        "artifact_id": event.artifact_id or None,
        "approval_id": str(approval_id) if approval_id is not None else None,
        "category": _event_category(event.event_type),
    }


def recent_mission_events(mission_id: str, limit: int = 100) -> list[dict[str, Any]]:
    events = get_event_bus().for_mission(mission_id)
    rows = events[-limit:] if limit > 0 else events
    normalized: list[dict[str, Any]] = []
    for event in rows:
        payload = normalize_mission_event(event)
        if payload:
            normalized.append(payload)
    return normalized


def _handle_bus_event(event: MissionEvent) -> None:
    payload = normalize_mission_event(event)
    if not payload:
        return

    loop = _LOOP
    if not loop or loop.is_closed():
        return

    try:
        asyncio.run_coroutine_threadsafe(manager.broadcast_mission_event(payload), loop)
    except RuntimeError as exc:
        logger.warning("Realtime broadcast scheduling failed: %s", exc)


def start_realtime_event_bridge(loop: asyncio.AbstractEventLoop | None = None) -> None:
    global _SUBSCRIBED, _LOOP
    with _SUBSCRIBE_LOCK:
        if _SUBSCRIBED:
            return
        _LOOP = loop or asyncio.get_running_loop()
        get_event_bus().subscribe(_handle_bus_event)
        _SUBSCRIBED = True
