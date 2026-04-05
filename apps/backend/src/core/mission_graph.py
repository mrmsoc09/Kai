from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable, Literal, Protocol, cast
from uuid import UUID

from langgraph.graph import END, StateGraph

from .protocol import (
    FindingType,
    KaisonFinding,
    KaisonResult,
    KaisonResultMetadata,
    MissionState,
    Severity,
)


class PraisonSwarmRunner(Protocol):
    """Protocol for phase-scoped PraisonAI micro-swarm execution."""

    def run_phase(self, phase: str, targets: list[str], state: MissionState) -> Any:
        ...


@dataclass(slots=True)
class PraisonMicroSwarmAdapter:
    """
    Lightweight adapter for a PraisonAI micro-swarm runner.

    If no callable runner is supplied, execution safely degrades to empty output.
    """

    runner: Callable[[str, list[str], MissionState], Any] | None = None

    def run_phase(self, phase: str, targets: list[str], state: MissionState) -> Any:
        if self.runner is None:
            return []
        return self.runner(phase, targets, state)


def build_mission_graph(
    swarm_runner: PraisonSwarmRunner | None = None,
):
    """
    Build a fully autonomous LangGraph mission state machine.

    Graph shape:
      Discovery_Node -> Enrichment_Node -> (Discovery_Node | Exploitation_Node | END)
      Exploitation_Node -> (Discovery_Node | END)
    """

    runner = swarm_runner or PraisonMicroSwarmAdapter()
    graph = StateGraph(MissionState)

    def Discovery_Node(state: MissionState) -> MissionState:
        state_obj = _with_defaults(state)
        if state_obj.get("terminate", False):
            return cast(MissionState, state_obj)

        state_obj["cycle_count"] = int(state_obj.get("cycle_count", 0)) + 1
        pending = list(state_obj.get("pending_targets", []))
        if not pending:
            _refresh_state_hash_and_stuck(state_obj)
            return cast(MissionState, state_obj)

        current_target = pending.pop(0)
        state_obj["pending_targets"] = pending
        state_obj["active_target"] = current_target
        state_obj["current_phase"] = "discovery"

        node_results = _execute_phase(runner, "discovery", [current_target], state_obj)
        state_obj = _merge_results(state_obj, node_results)

        if _phase_failed(node_results):
            _finalize_target(state_obj, current_target)
        else:
            new_subdomains = _extract_high_value_subdomains(
                [finding for result in node_results for finding in result.findings],
                exclude={current_target},
            )
            _enqueue_targets(state_obj, new_subdomains, prioritize=True, exclude={current_target})

        _refresh_state_hash_and_stuck(state_obj)
        return cast(MissionState, state_obj)

    def Enrichment_Node(state: MissionState) -> MissionState:
        state_obj = _with_defaults(state)
        if state_obj.get("terminate", False):
            return cast(MissionState, state_obj)

        state_obj["cycle_count"] = int(state_obj.get("cycle_count", 0)) + 1
        current_target = str(state_obj.get("active_target") or "").strip()
        if not current_target:
            pending = list(state_obj.get("pending_targets", []))
            if pending:
                current_target = pending.pop(0)
                state_obj["pending_targets"] = pending
                state_obj["active_target"] = current_target

        if not current_target:
            _refresh_state_hash_and_stuck(state_obj)
            return cast(MissionState, state_obj)

        state_obj["current_phase"] = "enrichment"
        node_results = _execute_phase(runner, "enrichment", [current_target], state_obj)
        state_obj = _merge_results(state_obj, node_results)

        latest_findings = [finding for result in node_results for finding in result.findings]
        state_obj = waf_adaptation(state_obj, latest_findings)

        if _phase_failed(node_results):
            _finalize_target(state_obj, current_target)
            state_obj["re_entry_targets"] = []
        else:
            re_entries = _extract_high_value_subdomains(latest_findings, exclude={current_target})
            state_obj["re_entry_targets"] = re_entries

        _refresh_state_hash_and_stuck(state_obj)
        return cast(MissionState, state_obj)

    def Exploitation_Node(state: MissionState) -> MissionState:
        state_obj = _with_defaults(state)
        if state_obj.get("terminate", False):
            return cast(MissionState, state_obj)

        state_obj["cycle_count"] = int(state_obj.get("cycle_count", 0)) + 1
        current_target = str(state_obj.get("active_target") or "").strip()
        if not current_target:
            pending = list(state_obj.get("pending_targets", []))
            if pending:
                current_target = pending.pop(0)
                state_obj["pending_targets"] = pending
                state_obj["active_target"] = current_target

        if not current_target:
            _refresh_state_hash_and_stuck(state_obj)
            return cast(MissionState, state_obj)

        state_obj["current_phase"] = "exploitation"
        node_results = _execute_phase(runner, "exploitation", [current_target], state_obj)
        state_obj = _merge_results(state_obj, node_results)

        # Always finalize active target after exploitation attempt, including failures.
        _finalize_target(state_obj, current_target)

        _refresh_state_hash_and_stuck(state_obj)
        return cast(MissionState, state_obj)

    graph.add_node("Discovery_Node", Discovery_Node)
    graph.add_node("Enrichment_Node", Enrichment_Node)
    graph.add_node("Exploitation_Node", Exploitation_Node)

    graph.set_entry_point("Discovery_Node")
    graph.add_edge("Discovery_Node", "Enrichment_Node")

    graph.add_conditional_edges(
        "Enrichment_Node",
        re_entry_logic,
        {
            "re_discover": "Discovery_Node",
            "exploit": "Exploitation_Node",
            "terminate": END,
        },
    )

    graph.add_conditional_edges(
        "Exploitation_Node",
        should_continue,
        {
            "continue": "Discovery_Node",
            "complete": END,
            "terminate": END,
        },
    )

    return graph.compile()


def should_continue(state: MissionState) -> Literal["continue", "complete", "terminate"]:
    """Continue autonomously while pending targets remain and state progresses."""
    if state.get("terminate", False):
        return "terminate"
    if _cycle_exhausted(state):
        return "terminate"
    if int(state.get("unchanged_cycles", 0)) >= 2:
        return "terminate"

    pending = list(state.get("pending_targets", []))
    return "continue" if bool(pending) else "complete"


def re_entry_logic(state: MissionState) -> Literal["re_discover", "exploit", "terminate"]:
    """
    Re-enter discovery when enrichment produces high-value new assets.

    New re-entry assets are prioritized in front of pending targets and the
    current enriched target is re-queued for later exploitation.
    """
    state_obj = _with_defaults(state)
    if state_obj.get("terminate", False):
        return "terminate"
    if _cycle_exhausted(state_obj):
        return "terminate"
    if int(state_obj.get("unchanged_cycles", 0)) >= 2:
        return "terminate"

    re_entries = _dedupe_strings(state_obj.get("re_entry_targets", []))
    if not re_entries:
        return "exploit"

    current_target = str(state_obj.get("active_target") or "").strip()
    if current_target:
        _enqueue_targets(state_obj, [current_target], prioritize=False)

    _enqueue_targets(state_obj, re_entries, prioritize=True, exclude={current_target})
    state_obj["re_entry_targets"] = []
    state_obj["active_target"] = ""
    return "re_discover"


def waf_adaptation(state: MissionState, findings: list[KaisonFinding]) -> MissionState:
    """
    Force low-thread, high-latency execution profile when WAF is detected.
    """
    state_obj = _with_defaults(state)
    waf_detected = any(_is_waf_finding(finding) for finding in findings)
    if not waf_detected:
        return cast(MissionState, state_obj)

    profile = dict(state_obj.get("execution_profile", {}))
    profile.update(
        {
            "latency_mode": "high",
            "threads": 1,
            "max_concurrency": 1,
            "request_delay_ms": 1200,
            "jitter_ms": 450,
        }
    )

    state_obj["execution_profile"] = profile
    state_obj["waf_flagged"] = True
    return cast(MissionState, state_obj)


def _execute_phase(
    runner: PraisonSwarmRunner,
    phase: str,
    targets: list[str],
    state: MissionState,
) -> list[KaisonResult]:
    mission_id = str(state.get("mission_id") or "mission-001")
    raw = runner.run_phase(phase, targets, state)
    results = _normalize_results(raw, mission_id=mission_id, phase=phase, target=targets[0] if targets else "")
    return _dedupe_results(results)


def _normalize_results(
    raw: Any,
    *,
    mission_id: str,
    phase: str,
    target: str,
) -> list[KaisonResult]:
    if raw is None:
        return [_empty_result(mission_id, phase, target, status="partial")]

    if isinstance(raw, KaisonResult):
        return [raw]

    if isinstance(raw, dict):
        return [_coerce_result(raw, mission_id=mission_id, phase=phase, target=target)]

    if isinstance(raw, list):
        out: list[KaisonResult] = []
        for item in raw:
            if isinstance(item, KaisonResult):
                out.append(item)
            elif isinstance(item, dict):
                out.append(_coerce_result(item, mission_id=mission_id, phase=phase, target=target))
        return out or [_empty_result(mission_id, phase, target, status="partial")]

    return [_empty_result(mission_id, phase, target, status="partial")]


def _coerce_result(
    payload: dict[str, Any],
    *,
    mission_id: str,
    phase: str,
    target: str,
) -> KaisonResult:
    findings: list[KaisonFinding] = []
    for item in payload.get("findings", []):
        try:
            if isinstance(item, dict):
                findings.append(KaisonFinding.model_validate(_normalize_finding_payload(item)))
        except Exception:
            continue

    started_at = _parse_datetime(payload.get("started_at")) or datetime.now(UTC)
    ended_at = _parse_datetime(payload.get("ended_at")) or datetime.now(UTC)
    runtime_ms = payload.get("runtime_ms")
    if runtime_ms is None:
        runtime_ms = max(0, int((ended_at - started_at).total_seconds() * 1000))

    return KaisonResult(
        mission_id=str(payload.get("mission_id") or mission_id),
        source_agent=str(payload.get("source_agent") or f"praison_{phase}"),
        status=str(payload.get("status") or "success"),
        target_context=dict(payload.get("target_context") or {"target": target, "phase": phase}),
        metadata=KaisonResultMetadata(
            started_at=started_at,
            ended_at=ended_at,
            runtime_ms=int(runtime_ms),
        ),
        findings=findings,
    )


def _empty_result(mission_id: str, phase: str, target: str, status: str) -> KaisonResult:
    now = datetime.now(UTC)
    return KaisonResult(
        mission_id=mission_id,
        source_agent=f"praison_{phase}",
        status=status,
        target_context={"target": target, "phase": phase},
        metadata=KaisonResultMetadata(
            started_at=now,
            ended_at=now,
            runtime_ms=0,
        ),
        findings=[],
    )


def _normalize_finding_payload(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)

    raw_id = normalized.get("finding_id")
    if isinstance(raw_id, str):
        try:
            normalized["finding_id"] = UUID(raw_id)
        except ValueError:
            pass

    raw_type = normalized.get("finding_type")
    if isinstance(raw_type, str):
        try:
            normalized["finding_type"] = FindingType(raw_type.strip().lower())
        except ValueError:
            pass

    raw_severity = normalized.get("severity")
    if isinstance(raw_severity, str):
        try:
            normalized["severity"] = Severity(raw_severity.strip().lower())
        except ValueError:
            pass

    return normalized


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)

    if isinstance(value, str) and value.strip():
        token = value.strip()
        if token.endswith("Z"):
            token = token[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(token)
        except ValueError:
            return None
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)

    return None


def _merge_results(state: dict[str, Any], node_results: list[KaisonResult]) -> dict[str, Any]:
    history = [_safe_result(item) for item in state.get("results_history", [])]
    merged_history = _dedupe_results(history + node_results)
    state["results_history"] = merged_history

    current_findings = [_safe_finding(item) for item in state.get("findings", [])]
    new_findings = [f for result in node_results for f in result.findings]
    merged_findings = _dedupe_findings(current_findings + new_findings)
    state["findings"] = merged_findings

    discovered = dict(state.get("discovered_assets", {}))
    subdomains = set(discovered.get("subdomains", []))
    ports = set(discovered.get("ports", []))

    for finding in new_findings:
        if finding.finding_type == FindingType.SUBDOMAIN:
            subdomains.add(finding.value)
        elif finding.finding_type == FindingType.PORT:
            ports.add(finding.value)

    discovered["subdomains"] = sorted(subdomains)
    discovered["ports"] = sorted(ports)
    state["discovered_assets"] = discovered

    return state


def _safe_result(item: Any) -> KaisonResult:
    if isinstance(item, KaisonResult):
        return item
    return KaisonResult.model_validate(item)


def _safe_finding(item: Any) -> KaisonFinding:
    if isinstance(item, KaisonFinding):
        return item
    return KaisonFinding.model_validate(item)


def _dedupe_findings(findings: list[KaisonFinding]) -> list[KaisonFinding]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[KaisonFinding] = []

    for finding in findings:
        key = (
            finding.finding_type.value,
            finding.value.strip().lower(),
            finding.source_agent.strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(finding)

    return deduped


def _dedupe_results(results: list[KaisonResult]) -> list[KaisonResult]:
    seen: set[tuple[str, str, str]] = set()
    deduped: list[KaisonResult] = []

    for result in results:
        target = str(result.target_context.get("target", "")).strip().lower()
        key = (
            result.source_agent.strip().lower(),
            target,
            result.metadata.started_at.isoformat(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(result)

    return deduped


def _extract_high_value_subdomains(
    findings: list[KaisonFinding],
    exclude: set[str] | None = None,
) -> list[str]:
    excluded = {item.strip().lower() for item in (exclude or set()) if item}
    out: list[str] = []

    for finding in findings:
        if finding.finding_type != FindingType.SUBDOMAIN:
            continue

        value = finding.value.strip().lower()
        if not value or value in excluded:
            continue
        if _is_high_value_asset(value):
            out.append(value)

    return _dedupe_strings(out)


def _is_high_value_asset(hostname: str) -> bool:
    high_signal_tokens = (
        "admin",
        "api",
        "auth",
        "internal",
        "dev",
        "stage",
        "prod",
        "vpn",
        "gateway",
        "kibana",
        "grafana",
    )
    return any(token in hostname for token in high_signal_tokens)


def _is_waf_finding(finding: KaisonFinding) -> bool:
    text_chunks = [
        finding.value,
        str(finding.raw_evidence.get("title", "")),
        str(finding.raw_evidence.get("vendor", "")),
        str(finding.raw_evidence.get("server", "")),
        str(finding.raw_evidence.get("waf", "")),
    ]
    corpus = " ".join(text_chunks).lower()
    waf_tokens = ("waf", "cloudflare", "akamai", "imperva", "f5", "fastly")
    return any(token in corpus for token in waf_tokens)


def _with_defaults(state: MissionState) -> dict[str, Any]:
    state_obj = dict(state)

    pending = list(state_obj.get("pending_targets", []))
    if not pending:
        pending = list(state_obj.get("target_queue", []))
    state_obj["pending_targets"] = _dedupe_strings(pending)

    state_obj.setdefault("target_queue", list(state_obj["pending_targets"]))
    state_obj.setdefault("active_targets", [])
    state_obj.setdefault("completed_targets", [])
    state_obj.setdefault("findings", [])
    state_obj.setdefault("results_history", [])
    state_obj.setdefault("discovered_assets", {})
    state_obj.setdefault("re_entry_targets", [])
    state_obj.setdefault("execution_profile", {"latency_mode": "normal", "threads": 10})
    state_obj.setdefault("waf_flagged", False)
    state_obj.setdefault("cycle_count", 0)
    state_obj.setdefault("max_cycles", 200)
    state_obj.setdefault("state_hash", "")
    state_obj.setdefault("previous_state_hash", "")
    state_obj.setdefault("unchanged_cycles", 0)
    state_obj.setdefault("terminate", False)
    state_obj.setdefault("terminate_reason", "")

    active_target = str(state_obj.get("active_target") or "").strip()
    if active_target and active_target not in state_obj["active_targets"]:
        state_obj["active_targets"].append(active_target)

    return state_obj


def _enqueue_targets(
    state: dict[str, Any],
    candidates: list[str],
    *,
    prioritize: bool,
    exclude: set[str] | None = None,
) -> None:
    excluded = {item.strip().lower() for item in (exclude or set()) if item}
    completed = {item.strip().lower() for item in state.get("completed_targets", [])}

    queue = list(state.get("pending_targets", []))
    normalized = []
    for item in candidates:
        target = str(item).strip().lower()
        if not target:
            continue
        if target in excluded or target in completed:
            continue
        normalized.append(target)

    if prioritize:
        queue = normalized + queue
    else:
        queue.extend(normalized)

    state["pending_targets"] = _dedupe_strings(queue)
    state["target_queue"] = list(state["pending_targets"])


def _dedupe_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        token = str(value).strip().lower()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _cycle_exhausted(state: dict[str, Any] | MissionState) -> bool:
    cycle_count = int(state.get("cycle_count", 0))
    max_cycles = int(state.get("max_cycles", 200))
    return cycle_count >= max_cycles


def _phase_failed(results: list[KaisonResult]) -> bool:
    if not results:
        return True
    failure_statuses = {"failure", "failed", "error", "timeout", "partial"}
    return all(result.status.strip().lower() in failure_statuses for result in results)


def _finalize_target(state: dict[str, Any], target: str) -> None:
    token = str(target).strip().lower()
    if not token:
        return

    completed = _dedupe_strings(list(state.get("completed_targets", [])) + [token])
    state["completed_targets"] = completed

    pending = [item for item in state.get("pending_targets", []) if item != token]
    state["pending_targets"] = pending
    state["target_queue"] = list(pending)

    state["active_target"] = ""
    state["active_targets"] = [item for item in state.get("active_targets", []) if item != token]


def _refresh_state_hash_and_stuck(state: dict[str, Any]) -> None:
    digest = _state_digest(state)
    previous = str(state.get("state_hash") or "")

    state["previous_state_hash"] = previous
    state["state_hash"] = digest

    if previous and previous == digest:
        state["unchanged_cycles"] = int(state.get("unchanged_cycles", 0)) + 1
    else:
        state["unchanged_cycles"] = 0

    if int(state.get("unchanged_cycles", 0)) >= 2:
        state["terminate"] = True
        state["terminate_reason"] = "state_hash_stuck"

    if _cycle_exhausted(state):
        state["terminate"] = True
        state["terminate_reason"] = "max_cycles_exhausted"


def _state_digest(state: dict[str, Any]) -> str:
    finding_sig = sorted(
        (
            finding.finding_type.value,
            finding.value.strip().lower(),
            finding.source_agent.strip().lower(),
        )
        for finding in [_safe_finding(item) for item in state.get("findings", [])]
    )

    payload = {
        "pending_targets": _dedupe_strings(list(state.get("pending_targets", []))),
        "active_target": str(state.get("active_target") or "").strip().lower(),
        "completed_targets": _dedupe_strings(list(state.get("completed_targets", []))),
        "findings": finding_sig,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
