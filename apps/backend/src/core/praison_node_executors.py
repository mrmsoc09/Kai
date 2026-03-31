"""
K1 Mission Graph Node Executors (Phase 4 / 4.5)
==================================================
Typed node callable factories for each standard mission graph node.

Each executor wraps an agent callable with:
  - Event emission (node_entered, node_completed, node_failed)
  - Contract lifecycle (create, validate, activate, complete/violate)
  - Governance checks at sensitive boundaries
  - State update accumulation
  - Error handling and violation recording

Phase 4.5 additions:
  - Governance middleware wrapper (pre-execution validation for any node)
  - Strategy-aware execution (profile selection tracking)
  - Retry-aware execution with bounded retry policy

Node types:
  governance_admission   -- validates mission authorization
  mission_director       -- orchestrates phase sequencing
  phase_coordinator      -- delegates to specialist cluster
  specialist_cluster     -- bounded parallel specialist execution
  evidence_analysis      -- merge/synthesis of specialist outputs
  governance_review      -- approval gate for sensitive findings
  report_synthesis       -- final report generation
  handoff_liaison        -- mission completion and handoff

Simulation-ready:
  All executors read state["execution_mode"]. In "graph_only" mode,
  they return synthetic state updates without calling real agents.
  In "tool_mock" mode, they call agents with mocked tool results.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from apps.backend.src.core.decision_engine.decision_policy import DecisionAction, PolicyDecision
from apps.backend.src.core.decision_engine.decision_trace import DecisionTraceRecorder
from apps.backend.src.core.opportunity_engine import get_opportunity_engine
from apps.backend.src.core.praison_execution_events import (
    emit,
    node_entered_event,
    node_completed_event,
    node_failed_event,
    phase_transition_event,
    approval_requested_event,
    policy_decision_event,
    tool_profile_selected_event,
    prompt_profile_selected_event,
)
from apps.backend.src.core.praison_strategy_scoring import (
    StrategyOutcome,
    recommend_next_action_from_outcome,
)
from apps.backend.src.core.praison_state import ACCUMULATIVE_FIELDS
from apps.backend.src.core.scope_guardrails import evaluate_target_scope, load_scope_policy
from apps.backend.src.core.vulnerability_validation import (
    ValidationEvidence,
    ValidationResult,
    decide_validation_next_action,
)

logger = logging.getLogger(__name__)


# -- Accumulative state fields (canonical definition lives in praison_state) ----
# Re-exported here for backward compatibility with existing importers.
_ACCUMULATIVE_FIELDS = ACCUMULATIVE_FIELDS
_SCOPE_POLICY = load_scope_policy()


def _decision_trace_recorder() -> DecisionTraceRecorder:
    return DecisionTraceRecorder()


# -- Node history entry builder ------------------------------------------------

def _history_entry(
    node_id: str,
    status: str,
    entered_at: str,
    duration_ms: float = 0.0,
) -> dict[str, Any]:
    return {
        "node_id": node_id,
        "status": status,
        "entered_at": entered_at,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": round(duration_ms, 2),
    }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _normalize_domain(value: Any) -> str:
    raw = str(value or "").strip().lower()
    if not raw:
        return ""
    if "://" in raw:
        parsed = urlparse(raw)
        raw = parsed.hostname or ""
    if ":" in raw:
        raw = raw.split(":", 1)[0]
    return raw.strip(".")


def _extract_domains_from_findings(findings: list[dict[str, Any]], state: dict[str, Any]) -> list[str]:
    domains: list[str] = []
    for finding in findings:
        candidate = (
            finding.get("domain")
            or finding.get("host")
            or finding.get("target")
            or finding.get("url")
            or state.get("program_id")
        )
        domain = _normalize_domain(candidate)
        if not domain or "." not in domain or "*" in domain:
            continue
        decision = evaluate_target_scope(domain, _SCOPE_POLICY)
        if decision.allowed:
            domains.append(domain)
    seen: set[str] = set()
    unique: list[str] = []
    for domain in domains:
        if domain not in seen:
            unique.append(domain)
            seen.add(domain)
    return unique


def _estimate_duplicate_risk(findings: list[dict[str, Any]]) -> float:
    targets = [_normalize_domain(row.get("target") or row.get("host") or row.get("domain") or row.get("url")) for row in findings]
    filtered = [row for row in targets if row]
    if not filtered:
        return 0.0
    unique = len(set(filtered))
    duplicate_ratio = 1.0 - (unique / len(filtered))
    return max(0.0, min(1.0, duplicate_ratio))


def _average_confidence(findings: list[dict[str, Any]]) -> float:
    confidences = [_safe_float(row.get("confidence") or row.get("confidence_score"), 0.4) for row in findings]
    if not confidences:
        return 0.0
    return max(0.0, min(1.0, sum(confidences) / len(confidences)))


def _opportunity_signal(findings: list[dict[str, Any]]) -> float:
    if not findings:
        return 0.0
    confidence = _average_confidence(findings)
    duplicate_penalty = 1.0 - _estimate_duplicate_risk(findings)
    repeat_bonus = min(1.0, len(findings) / 4.0)
    return max(0.0, min(1.0, confidence * duplicate_penalty * (0.6 + (0.4 * repeat_bonus))))


def _is_validated_finding(row: dict[str, Any]) -> bool:
    return bool(
        row.get("validated")
        or row.get("validated_vulnerability")
        or row.get("validation_present")
        or row.get("confirmed")
    )


def _build_validation_result(findings: list[dict[str, Any]]) -> ValidationResult:
    top = findings[0]
    validated = any(_is_validated_finding(row) for row in findings)
    confidence = _average_confidence(findings)
    evidence = [
        ValidationEvidence(
            check="runtime_finding_signal",
            passed=bool(row.get("severity", "").lower() in {"critical", "high", "medium"}),
            detail=f"severity={row.get('severity', 'unknown')}",
            confidence_contribution=max(0.0, min(1.0, _safe_float(row.get("confidence") or row.get("confidence_score"), 0.0))),
        )
        for row in findings[:10]
    ]
    return ValidationResult(
        finding_id=str(top.get("finding_id") or top.get("id") or "runtime-finding"),
        validated_vulnerability=validated,
        confidence_score=confidence,
        validation_evidence=evidence,
    )


def _cluster_rows_from_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_type: dict[str, int] = {}
    for row in findings:
        vuln_type = str(row.get("vuln_type") or row.get("type") or "unknown").strip().lower()
        by_type[vuln_type] = by_type.get(vuln_type, 0) + 1
    return [
        {
            "cluster_id": f"cluster:{vuln_type}",
            "vuln_type": vuln_type,
            "count": count,
            "response_similarity": _average_confidence(findings),
        }
        for vuln_type, count in by_type.items()
    ]


def _append_policy_event(
    result: dict[str, Any],
    *,
    node_id: str,
    decision: PolicyDecision,
    trace_id: str,
) -> None:
    result.setdefault("policy_events", [])
    if not isinstance(result["policy_events"], list):
        result["policy_events"] = []
    result["policy_events"].append(
        {
            "type": "runtime_decision",
            "node_id": node_id,
            "decision_action": decision.chosen_action.value,
            "reason_code": decision.reason_code,
            "score": decision.score,
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )


def _governance_approved(state: dict[str, Any], result: dict[str, Any]) -> bool:
    if str(result.get("governance_decision") or state.get("governance_decision") or "").lower() == "approved":
        return True
    resolved = state.get("approvals_resolved", [])
    if isinstance(resolved, list):
        return any(str(row.get("decision", "")).lower() == "approved" for row in resolved if isinstance(row, dict))
    return False


def _generate_opportunities(findings: list[dict[str, Any]], state: dict[str, Any]) -> list[dict[str, Any]]:
    allowed_domains = _extract_domains_from_findings(findings, state)
    if not allowed_domains:
        return []
    try:
        engine = get_opportunity_engine()
        result = engine.detect(
            allowed_domains=allowed_domains,
            min_confidence=0.55,
            max_opportunities=5,
            deduplicate=True,
        )
        return [row.to_dict() for row in result.opportunities]
    except Exception as exc:
        logger.warning("Opportunity generation from runtime decision failed: %s", exc)
        return []


def _apply_evidence_decision(
    state: dict[str, Any],
    result: dict[str, Any],
    decision: PolicyDecision,
    findings: list[dict[str, Any]],
) -> None:
    action = decision.chosen_action
    result["decision_action"] = action.value
    result["decision_reason_code"] = decision.reason_code
    if action == DecisionAction.STOP:
        result["error"] = f"Decision engine stop: {decision.reason_code}"
        result["completed"] = True
        result["phase_complete"] = True
        return
    if action == DecisionAction.PIVOT:
        result["pivot_requested"] = True
        result["phase_complete"] = True
        return
    if action == DecisionAction.VALIDATE:
        result["requires_additional_validation"] = True
        return
    if action == DecisionAction.EXPLOIT:
        approved = _governance_approved(state, result)
        result["exploit_recommended"] = approved
        if not approved:
            result["exploit_blocked_reason"] = "governance_approval_required"
        return
    if action == DecisionAction.GENERATE_OPPORTUNITY:
        generated = _generate_opportunities(findings, state)
        result["generated_opportunities"] = generated
        if generated:
            result["last_artifact_type"] = "opportunity_signal"
        return


def _build_strategy_outcome(state: dict[str, Any], result: dict[str, Any]) -> StrategyOutcome:
    findings = result.get("findings")
    if not isinstance(findings, list):
        findings = state.get("findings", [])
    findings = findings if isinstance(findings, list) else []

    severities = [str(row.get("severity", "")).lower() for row in findings if isinstance(row, dict)]
    high = sum(1 for row in severities if row in {"critical", "high"})
    medium = sum(1 for row in severities if row == "medium")
    low = sum(1 for row in severities if row in {"low", "info", "informational"})
    false_positives = sum(1 for row in findings if isinstance(row, dict) and bool(row.get("false_positive")))
    validated = sum(1 for row in findings if isinstance(row, dict) and _is_validated_finding(row))
    unique_keys = set(
        f"{_normalize_domain(row.get('target') or row.get('host') or row.get('domain') or row.get('url'))}|{row.get('vuln_type') or row.get('type') or ''}"
        for row in findings
        if isinstance(row, dict)
    )
    metrics = state.get("runtime_metrics", {})
    if not isinstance(metrics, dict):
        metrics = {}

    return StrategyOutcome(
        mission_id=str(state.get("mission_id", "")),
        phase=str(state.get("phase", "")),
        strategy_id=str(state.get("workflow_id", "")),
        targets_in_scope=max(1, len(set(_extract_domains_from_findings(findings, state)))),
        targets_covered=max(0, len(set(_extract_domains_from_findings(findings, state)))),
        total_findings=len(findings),
        unique_findings=len([row for row in unique_keys if row and not row.startswith("|")]),
        high_confidence_findings=high,
        medium_confidence_findings=medium,
        low_confidence_findings=low,
        false_positives=false_positives,
        budgeted_seconds=_safe_float(metrics.get("budgeted_seconds"), 3600.0),
        actual_seconds=_safe_float(metrics.get("actual_seconds"), 0.0),
        budgeted_tokens=int(_safe_float(metrics.get("budgeted_tokens"), 100000)),
        actual_tokens=int(_safe_float(metrics.get("actual_tokens"), 0.0)),
        tool_invocations=int(_safe_float(metrics.get("tool_invocations"), 0.0)),
        escalation_count=len(state.get("escalations", []) if isinstance(state.get("escalations", []), list) else []),
        blocked_count=sum(
            1
            for row in (state.get("policy_events", []) if isinstance(state.get("policy_events", []), list) else [])
            if isinstance(row, dict) and str(row.get("decision", "")).lower() == "blocked"
        ),
        approval_count=len(state.get("approvals_resolved", []) if isinstance(state.get("approvals_resolved", []), list) else []),
        artifacts_produced=len(state.get("artifact_ids", []) if isinstance(state.get("artifact_ids", []), list) else []),
        high_value_artifacts=len([row for row in findings if isinstance(row, dict) and str(row.get("severity", "")).lower() in {"critical", "high"}]),
        validated_vulnerabilities=validated,
        exploit_attempts=int(_safe_float(metrics.get("exploit_attempts"), 0.0)),
        exploit_successes=int(_safe_float(metrics.get("exploit_successes"), 0.0)),
        chain_attempts=int(_safe_float(metrics.get("chain_attempts"), 0.0)),
        chain_successes=int(_safe_float(metrics.get("chain_successes"), 0.0)),
        avg_chain_length=_safe_float(metrics.get("avg_chain_length"), 0.0),
    )


# -- Base executor wrapper -----------------------------------------------------

def make_node_executor(
    node_id: str,
    agent_callable: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    *,
    node_type: str = "agent",
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Wrap a raw agent callable into a LangGraph node function that emits
    events, tracks history, and handles errors.

    If agent_callable is None, the node returns a graph_only stub.
    """

    def executor(state: dict[str, Any]) -> dict[str, Any]:
        mission_id = state.get("mission_id", "")
        workflow_id = state.get("workflow_id", "")
        program_id = state.get("program_id", "")
        phase = state.get("phase", "")
        execution_mode = state.get("execution_mode", "live")
        entered_at = datetime.now(timezone.utc).isoformat()
        start = time.monotonic()

        # Emit node_entered
        emit(node_entered_event(
            mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
            node_id=node_id, phase=phase,
        ))

        # Graph-only simulation: return stub state update
        if execution_mode == "graph_only" or agent_callable is None:
            duration = (time.monotonic() - start) * 1000
            emit(node_completed_event(
                mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
                node_id=node_id, phase=phase,
            ))
            return {
                "active_node": node_id,
                "last_agent": node_id,
                "node_history": [_history_entry(node_id, "completed", entered_at, duration)],
                "events": [{"event_type": "node_completed", "node_id": node_id, "mode": execution_mode}],
            }

        # Real execution
        try:
            result = agent_callable(state)
            duration = (time.monotonic() - start) * 1000

            # Build state update from callable result
            update: dict[str, Any] = {
                "active_node": node_id,
                "last_agent": node_id,
                "node_history": [_history_entry(node_id, "completed", entered_at, duration)],
            }

            # Merge callable output into update (accumulative fields stay as lists)
            if isinstance(result, dict):
                for key, val in result.items():
                    if key in update:
                        continue  # don't override our tracking fields
                    update[key] = val

            # Collect artifact IDs
            artifact_ids = []
            for art in result.get("artifacts", []):
                if isinstance(art, dict) and "artifact_id" in art:
                    artifact_ids.append(art["artifact_id"])
            if artifact_ids:
                update["artifact_ids"] = artifact_ids

            emit(node_completed_event(
                mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
                node_id=node_id, phase=phase, artifact_ids=artifact_ids,
            ))
            return update

        except Exception as exc:
            duration = (time.monotonic() - start) * 1000
            error_msg = f"Node {node_id} failed: {exc}"
            logger.error(error_msg, exc_info=True)

            emit(node_failed_event(
                mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
                node_id=node_id, error=str(exc), phase=phase,
            ))
            return {
                "active_node": node_id,
                "last_agent": node_id,
                "error": error_msg,
                "errors": [{"node_id": node_id, "error": str(exc), "timestamp": entered_at}],
                "node_history": [_history_entry(node_id, "failed", entered_at, duration)],
            }

    executor.__name__ = f"node_{node_id}"
    executor.__qualname__ = f"node_{node_id}"
    return executor


# -- Governance admission node -------------------------------------------------

def make_governance_admission_executor(
    agent_callable: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Mission entry gate. Validates mission authorization before any work begins.
    Sets governance_decision to "approved" or "blocked".
    """
    base = make_node_executor("governance_admission", agent_callable, node_type="governance")

    def executor(state: dict[str, Any]) -> dict[str, Any]:
        result = base(state)
        # Default to approved if no error and no explicit decision
        if not result.get("error") and not result.get("governance_decision"):
            result["governance_decision"] = "approved"
        elif result.get("error"):
            result["governance_decision"] = "blocked"
        result["phase"] = "governance"
        return result

    executor.__name__ = "governance_admission"
    return executor


# -- Mission director node -----------------------------------------------------

def make_mission_director_executor(
    agent_callable: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Orchestrates phase sequencing. Sets phase and active_cluster_id.
    """
    base = make_node_executor("mission_director", agent_callable, node_type="director")

    def executor(state: dict[str, Any]) -> dict[str, Any]:
        result = base(state)
        if not result.get("error"):
            result.setdefault("phase", "recon")
            result["governance_decision"] = ""  # reset for next gate
            result["phase_complete"] = False
        return result

    executor.__name__ = "mission_director"
    return executor


# -- Phase coordinator node ----------------------------------------------------

def make_phase_coordinator_executor(
    phase_name: str,
    agent_callable: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Coordinates specialists within a phase cluster."""
    node_id = f"phase_coordinator_{phase_name}"
    base = make_node_executor(node_id, agent_callable, node_type="coordinator")

    def executor(state: dict[str, Any]) -> dict[str, Any]:
        mission_id = state.get("mission_id", "")
        workflow_id = state.get("workflow_id", "")
        program_id = state.get("program_id", "")
        old_phase = state.get("phase", "")

        result = base(state)
        result["phase"] = phase_name

        if old_phase and old_phase != phase_name:
            emit(phase_transition_event(
                mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
                from_phase=old_phase, to_phase=phase_name,
            ))

        return result

    executor.__name__ = node_id
    return executor


# -- Specialist cluster node ---------------------------------------------------

def make_specialist_cluster_executor(
    cluster_name: str,
    agent_callable: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    simulation_artifact_type: str = "",
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Bounded specialist execution. Cluster node that delegates to specialists
    under DelegationContracts with TTL enforcement.

    simulation_artifact_type: artifact type to set in graph_only/tool_mock mode
      so that ON_ARTIFACT conditional edges can fire during topology validation.
    """
    node_id = f"specialist_cluster_{cluster_name}"
    base = make_node_executor(node_id, agent_callable, node_type="cluster")

    def executor(state: dict[str, Any]) -> dict[str, Any]:
        result = base(state)
        # Propagate cluster status
        cluster_status = dict(state.get("cluster_status", {}))
        cluster_status[cluster_name] = {
            "phase": state.get("phase", ""),
            "success": not result.get("error"),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        result["cluster_status"] = cluster_status
        # In simulation modes, set artifact type so ON_ARTIFACT edges can fire
        execution_mode = state.get("execution_mode", "live")
        if simulation_artifact_type and (
            execution_mode in ("graph_only", "tool_mock")
            or (execution_mode == "live" and agent_callable is None)
        ):
            result["last_artifact_type"] = simulation_artifact_type
        return result

    executor.__name__ = node_id
    return executor


# -- Evidence analysis / merge node --------------------------------------------

def _artifacts_root() -> Path:
    return Path(os.getenv("K1_ARTIFACTS_ROOT", "artifacts")).resolve()


def _extract_recon_findings(artifacts: list[dict[str, Any]], mission_id: str, program_id: str) -> list[dict[str, Any]]:
    """
    Extract structured recon findings from tool_bootstrap_result artifacts.
    Returns a list of finding dicts compatible with K1GraphState findings.
    """
    findings: list[dict[str, Any]] = []
    ts = datetime.now(timezone.utc).isoformat()

    for art in artifacts:
        if not isinstance(art, dict):
            continue
        art_type = art.get("artifact_type", "")
        content = art.get("content", {})
        if not isinstance(content, dict):
            continue
        if art_type != "tool_bootstrap_result":
            continue

        tool_id = content.get("tool_id", "unknown")
        target = content.get("target", "")
        result = content.get("result", {})

        # result may be a ToolResult-like object or a dict from GovernedToolWrapper
        if isinstance(result, dict):
            tool_status = result.get("status", "unknown")
            inner = result.get("result", result)
            if hasattr(inner, "output"):
                output = inner.output  # ToolResult.output
            elif isinstance(inner, dict):
                output = inner.get("output", inner)
            else:
                output = {}
        else:
            tool_status = "unknown"
            output = {}

        if not isinstance(output, dict):
            output = {}

        # Subdomains from subfinder / amass_enum
        subs = output.get("subdomains", [])
        if isinstance(subs, list) and subs:
            findings.append({
                "finding_id": str(uuid.uuid4()),
                "finding_type": "subdomain_enum",
                "severity": "info",
                "tool": tool_id,
                "target": target,
                "program_id": program_id,
                "mission_id": mission_id,
                "timestamp": ts,
                "data": {"subdomains": subs[:200], "count": len(subs)},
                "confidence": 0.85,
                "source": "recon_specialist_bootstrap",
            })
            continue

        # URLs from gau / waybackurls / katana
        urls = output.get("urls", output.get("items", []))
        if isinstance(urls, list) and urls and tool_id in {"gau", "waybackurls", "katana", "gospider"}:
            findings.append({
                "finding_id": str(uuid.uuid4()),
                "finding_type": "url_surface",
                "severity": "info",
                "tool": tool_id,
                "target": target,
                "program_id": program_id,
                "mission_id": mission_id,
                "timestamp": ts,
                "data": {"url_count": len(urls), "sample": urls[:20]},
                "confidence": 0.75,
                "source": "recon_specialist_bootstrap",
            })
            continue

        # DNS records from dnsx / httpx
        records = output.get("records", output.get("hosts", []))
        if isinstance(records, list) and records:
            findings.append({
                "finding_id": str(uuid.uuid4()),
                "finding_type": "dns_resolution",
                "severity": "info",
                "tool": tool_id,
                "target": target,
                "program_id": program_id,
                "mission_id": mission_id,
                "timestamp": ts,
                "data": {"record_count": len(records), "sample": records[:20]},
                "confidence": 0.8,
                "source": "recon_specialist_bootstrap",
            })
            continue

        # Nuclei findings — jsonl items
        items = output.get("items", [])
        if isinstance(items, list) and tool_id == "nuclei_scan":
            for item in items[:50]:
                if isinstance(item, dict):
                    severity = str(item.get("info", {}).get("severity", "info")).lower()
                    findings.append({
                        "finding_id": str(uuid.uuid4()),
                        "finding_type": "vulnerability",
                        "severity": severity,
                        "tool": tool_id,
                        "target": item.get("host", target),
                        "program_id": program_id,
                        "mission_id": mission_id,
                        "timestamp": ts,
                        "data": item,
                        "confidence": 0.7,
                        "source": "nuclei_scan",
                    })

    # De-duplicate by (finding_type, tool, target)
    seen: set[tuple[str, str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for f in findings:
        key = (f.get("finding_type", ""), f.get("tool", ""), f.get("target", ""))
        if key not in seen:
            seen.add(key)
            deduped.append(f)
    return deduped


def _write_report_artifact(
    mission_id: str,
    program_id: str,
    findings: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Write a structured mission report JSON and return an artifact dict."""
    ts = datetime.now(timezone.utc).isoformat()
    report_id = f"report-{uuid.uuid4()}"
    report = {
        "report_id": report_id,
        "mission_id": mission_id,
        "program_id": program_id,
        "generated_at": ts,
        "finding_count": len(findings),
        "findings_by_severity": {},
        "findings": findings,
        "artifact_count": len(artifacts),
        "artifact_summary": [
            {
                "artifact_type": a.get("artifact_type", ""),
                "summary": a.get("summary", ""),
            }
            for a in artifacts[:50]
            if isinstance(a, dict)
        ],
    }
    for f in findings:
        sev = f.get("severity", "info")
        report["findings_by_severity"][sev] = report["findings_by_severity"].get(sev, 0) + 1

    report_dir = _artifacts_root() / "reports" / "generated"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{report_id}.json"
    report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    logger.info("Report written to %s (%d findings)", report_path, len(findings))

    return {
        "artifact_id": report_id,
        "artifact_type": "final_report",
        "artifact_path": str(report_path),
        "summary": f"Mission report: {len(findings)} findings for {program_id}",
        "timestamp": ts,
    }


def make_evidence_analysis_executor(
    agent_callable: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Merges and synthesizes specialist outputs into findings."""
    base = make_node_executor("evidence_analysis", agent_callable, node_type="analyst")

    def executor(state: dict[str, Any]) -> dict[str, Any]:
        result = base(state)
        # Determine artifact type for routing
        findings = result.get("findings", [])
        findings = findings if isinstance(findings, list) else []
        findings = [row for row in findings if isinstance(row, dict)]

        # Fallback: synthesize findings from bootstrap artifacts when agent_callable is None
        if not findings and agent_callable is None:
            state_artifacts = state.get("artifacts", [])
            if isinstance(state_artifacts, list) and state_artifacts:
                mission_id = state.get("mission_id", "")
                program_id = state.get("program_id", "")
                findings = _extract_recon_findings(state_artifacts, mission_id, program_id)
                if findings:
                    result["findings"] = findings
                    logger.info(
                        "EvidenceAnalyst fallback: extracted %d findings from %d bootstrap artifacts",
                        len(findings), len(state_artifacts),
                    )

        has_significant = any(
            f.get("severity") in ("critical", "high", "medium") for f in findings
        )
        if has_significant:
            result["last_artifact_type"] = "vulnerability_signal"
        else:
            result["last_artifact_type"] = "recon_surface"

        if isinstance(findings, list) and findings:
            runtime_metrics = state.get("runtime_metrics", {})
            if not isinstance(runtime_metrics, dict):
                runtime_metrics = {}
            decision = decide_validation_next_action(
                _build_validation_result(findings),
                clusters=_cluster_rows_from_findings(findings),
                memory_hits=state.get("memory_hits", []) if isinstance(state.get("memory_hits", []), list) else [],
                duplicate_risk=_estimate_duplicate_risk(findings),
                budget_remaining_ratio=_safe_float(runtime_metrics.get("budget_remaining_ratio"), 1.0),
                time_remaining_ratio=_safe_float(runtime_metrics.get("time_remaining_ratio"), 1.0),
                opportunity_signal=_opportunity_signal(findings),
                trace_recorder=None,
            )
            trace_recorder = _decision_trace_recorder()
            trace = trace_recorder.build_trace(
                input_evidence=[
                    {
                        "mission_id": state.get("mission_id", ""),
                        "workflow_id": state.get("workflow_id", ""),
                        "finding_count": len(findings),
                        "duplicate_risk": _estimate_duplicate_risk(findings),
                        "opportunity_signal": _opportunity_signal(findings),
                    }
                ],
                hypotheses=[],
                decision=decision,
                metadata={
                    "source": "praison_node_executors.evidence_analysis",
                    "node_id": "evidence_analysis",
                    "phase": state.get("phase", ""),
                },
            )
            trace_recorder.record(trace)
            _append_policy_event(
                result,
                node_id="evidence_analysis",
                decision=decision,
                trace_id=trace.trace_id,
            )
            emit(policy_decision_event(
                mission_id=state.get("mission_id", ""),
                workflow_id=state.get("workflow_id", ""),
                program_id=state.get("program_id", ""),
                decision=decision.chosen_action.value,
                reason=f"{decision.reason_code};trace_id={trace.trace_id}",
                node_id="evidence_analysis",
            ))
            _apply_evidence_decision(state, result, decision, findings)
        return result

    executor.__name__ = "evidence_analysis"
    return executor


# -- Governance review node (approval gate) ------------------------------------

def make_governance_review_executor(
    agent_callable: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Approval gate for sensitive findings. May request HIL review.
    Sets governance_decision to "approved" or "blocked".
    """
    base = make_node_executor("governance_review", agent_callable, node_type="governance")

    def executor(state: dict[str, Any]) -> dict[str, Any]:
        mission_id = state.get("mission_id", "")
        workflow_id = state.get("workflow_id", "")
        program_id = state.get("program_id", "")

        result = base(state)

        if not result.get("governance_decision"):
            result["governance_decision"] = "approved"

        # Emit approval events based on decision
        if result.get("governance_decision") == "approved":
            result["policy_events"] = [{
                "type": "governance_review_passed",
                "node_id": "governance_review",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }]
        else:
            approval_id = str(uuid.uuid4())
            emit(approval_requested_event(
                mission_id=mission_id, workflow_id=workflow_id, program_id=program_id,
                approval_id=approval_id, node_id="governance_review",
                reason=result.get("error", "Governance review required"),
            ))
            result["approvals_required"] = [{
                "approval_id": approval_id,
                "node_id": "governance_review",
                "reason": "Findings require governance approval",
                "requested_at": datetime.now(timezone.utc).isoformat(),
            }]

        return result

    executor.__name__ = "governance_review"
    return executor


# -- Report synthesis node -----------------------------------------------------

def make_report_synthesis_executor(
    agent_callable: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Generates the final mission report."""
    base = make_node_executor("report_synthesis", agent_callable, node_type="reporter")

    def executor(state: dict[str, Any]) -> dict[str, Any]:
        result = base(state)
        # Set final_report_id if report artifact was produced by the agent
        for art in result.get("artifacts", []):
            if isinstance(art, dict) and art.get("artifact_type") in ("report_draft", "final_report"):
                result["final_report_id"] = art.get("artifact_id", "")
                break

        # Fallback: write a structured report when agent_callable is None
        if not result.get("final_report_id") and agent_callable is None:
            mission_id = state.get("mission_id", "")
            program_id = state.get("program_id", "")
            findings = state.get("findings", [])
            if not isinstance(findings, list):
                findings = []
            findings = [f for f in findings if isinstance(f, dict)]
            state_artifacts = state.get("artifacts", [])
            if not isinstance(state_artifacts, list):
                state_artifacts = []
            try:
                report_art = _write_report_artifact(mission_id, program_id, findings, state_artifacts)
                result["final_report_id"] = report_art["artifact_id"]
                existing = result.get("artifacts", [])
                result["artifacts"] = (existing if isinstance(existing, list) else []) + [report_art]
                result["artifact_ids"] = [report_art["artifact_id"]]
            except Exception as exc:
                logger.warning("ReportSynthesisAgent fallback failed: %s", exc)

        return result

    executor.__name__ = "report_synthesis"
    return executor


# -- Handoff liaison node (mission completion) ---------------------------------

def make_handoff_liaison_executor(
    agent_callable: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Mission completion and handoff. Sets completed=True."""
    base = make_node_executor("handoff_liaison", agent_callable, node_type="handoff")

    def executor(state: dict[str, Any]) -> dict[str, Any]:
        result = base(state)
        result["completed"] = True
        result["progress"] = 1.0
        findings = result.get("findings")
        if not isinstance(findings, list):
            findings = state.get("findings", [])
        findings = findings if isinstance(findings, list) else []
        findings = [row for row in findings if isinstance(row, dict)]
        strategy_outcome = _build_strategy_outcome(state, result)
        decision = recommend_next_action_from_outcome(
            strategy_outcome,
            duplicate_risk=_estimate_duplicate_risk(findings),
            top_hypothesis_confidence=_average_confidence(findings),
            hypothesis_count=max(1, len(findings)),
            opportunity_signal=_opportunity_signal(findings),
            trace_recorder=None,
        )
        trace_recorder = _decision_trace_recorder()
        trace = trace_recorder.build_trace(
            input_evidence=[
                {
                    "mission_id": state.get("mission_id", ""),
                    "workflow_id": state.get("workflow_id", ""),
                    "phase": state.get("phase", ""),
                    "finding_count": len(findings),
                }
            ],
            hypotheses=[],
            decision=decision,
            metadata={
                "source": "praison_node_executors.handoff_liaison",
                "node_id": "handoff_liaison",
            },
        )
        trace_recorder.record(trace)
        result["next_action_recommendation"] = decision.to_dict()
        _append_policy_event(
            result,
            node_id="handoff_liaison",
            decision=decision,
            trace_id=trace.trace_id,
        )
        emit(policy_decision_event(
            mission_id=state.get("mission_id", ""),
            workflow_id=state.get("workflow_id", ""),
            program_id=state.get("program_id", ""),
            decision=decision.chosen_action.value,
            reason=f"{decision.reason_code};trace_id={trace.trace_id}",
            node_id="handoff_liaison",
        ))
        if decision.chosen_action == DecisionAction.GENERATE_OPPORTUNITY:
            generated = _generate_opportunities(findings, state)
            if generated:
                result["generated_opportunities"] = generated
        return result

    executor.__name__ = "handoff_liaison"
    return executor


# -- Governance middleware wrapper (Phase 4.5) ---------------------------------

def make_governance_middleware(
    inner_executor: Callable[[dict[str, Any]], dict[str, Any]],
    node_id: str,
    *,
    validate_agent_spawn: Callable[..., None] | None = None,
    validate_tool_request: Callable[..., None] | None = None,
    risk_profile: str = "standard",
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Wrap any node executor with pre-execution governance validation.

    Calls governance checks (agent spawn, tool request) before executing
    the inner node. If governance blocks, the node returns a blocked state
    update without executing the inner callable.

    This is the integration point where LangGraph nodes call PraisonGovernor
    validation. Governance is called synchronously on the fast path.
    """

    def governed_executor(state: dict[str, Any]) -> dict[str, Any]:
        mission_id = state.get("mission_id", "")
        workflow_id = state.get("workflow_id", "")
        program_id = state.get("program_id", "")

        # Pre-execution governance check
        if validate_agent_spawn is not None:
            try:
                validate_agent_spawn(
                    agent_id=node_id,
                    workflow_id=workflow_id,
                    program_id=program_id,
                    risk_profile=risk_profile,
                )
            except Exception as exc:
                emit(policy_decision_event(
                    mission_id=mission_id,
                    workflow_id=workflow_id,
                    program_id=program_id,
                    decision="blocked",
                    reason=str(exc),
                    node_id=node_id,
                ))
                return {
                    "active_node": node_id,
                    "governance_decision": "blocked",
                    "error": f"Governance blocked node {node_id}: {exc}",
                    "policy_events": [{
                        "type": "governance_blocked",
                        "node_id": node_id,
                        "reason": str(exc),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }],
                    "errors": [{
                        "node_id": node_id,
                        "error": f"Governance blocked: {exc}",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }],
                }

        # Execute inner node
        result = inner_executor(state)

        # Record governance pass
        if not result.get("error"):
            emit(policy_decision_event(
                mission_id=mission_id,
                workflow_id=workflow_id,
                program_id=program_id,
                decision="permitted",
                reason="governance_middleware_pass",
                node_id=node_id,
            ))

        return result

    governed_executor.__name__ = f"governed_{node_id}"
    governed_executor.__qualname__ = f"governed_{node_id}"
    return governed_executor


# -- Strategy-aware executor wrapper (Phase 4.5) -------------------------------

def make_strategy_aware_executor(
    inner_executor: Callable[[dict[str, Any]], dict[str, Any]],
    node_id: str,
    *,
    tool_profile_id: str = "",
    prompt_profile_id: str = "",
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Wrap a node executor with strategy profile tracking.

    Records which tool/prompt profiles were used for this node's execution.
    Emits profile selection events for telemetry.
    """

    def strategy_executor(state: dict[str, Any]) -> dict[str, Any]:
        mission_id = state.get("mission_id", "")
        workflow_id = state.get("workflow_id", "")
        program_id = state.get("program_id", "")

        # Emit profile selection events
        if tool_profile_id:
            emit(tool_profile_selected_event(
                mission_id=mission_id,
                workflow_id=workflow_id,
                program_id=program_id,
                agent_id=node_id,
                profile_id=tool_profile_id,
            ))
        if prompt_profile_id:
            emit(prompt_profile_selected_event(
                mission_id=mission_id,
                workflow_id=workflow_id,
                program_id=program_id,
                agent_id=node_id,
                profile_id=prompt_profile_id,
            ))

        # Execute inner node
        result = inner_executor(state)

        # Record profile usage in state
        if tool_profile_id or prompt_profile_id:
            profile_entry = {
                "node_id": node_id,
                "tool_profile_id": tool_profile_id,
                "prompt_profile_id": prompt_profile_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            result.setdefault("strategy_profiles_used", [])
            if isinstance(result["strategy_profiles_used"], list):
                result["strategy_profiles_used"].append(profile_entry)
            else:
                result["strategy_profiles_used"] = [profile_entry]

        return result

    strategy_executor.__name__ = f"strategy_{node_id}"
    strategy_executor.__qualname__ = f"strategy_{node_id}"
    return strategy_executor


# -- Retry-aware executor wrapper (Phase 4.5) ----------------------------------

def make_retry_executor(
    inner_executor: Callable[[dict[str, Any]], dict[str, Any]],
    node_id: str,
    *,
    max_retries: int = 0,
    backoff_seconds: float = 1.0,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Wrap a node executor with bounded retry logic.

    Retries on failure up to max_retries times with fixed backoff.
    Retry parameters come from ExecutionStrategy.retry_policy.
    """

    def retry_executor(state: dict[str, Any]) -> dict[str, Any]:
        last_result = None
        for attempt in range(max_retries + 1):
            result = inner_executor(state)
            if not result.get("error"):
                return result
            last_result = result
            if attempt < max_retries:
                import time as _time
                _time.sleep(min(backoff_seconds * (attempt + 1), 60.0))
                logger.info(
                    "Node %s retry %d/%d after error: %s",
                    node_id, attempt + 1, max_retries, result.get("error", ""),
                )
        return last_result or {}

    retry_executor.__name__ = f"retry_{node_id}"
    retry_executor.__qualname__ = f"retry_{node_id}"
    return retry_executor


# -- Build standard node callables map -----------------------------------------

def build_standard_node_callables(
    agent_callables: dict[str, Callable[[dict[str, Any]], dict[str, Any]] | None] | None = None,
) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    """
    Build the standard set of LangGraph node callables for a K1 bug bounty mission.

    agent_callables: optional {node_id: raw_callable} for real agent execution.
    If None or missing for a node, that node runs in graph_only mode.

    Returns {node_id: wrapped_executor} ready for PraisonLangGraphBuilder.
    """
    ac = agent_callables or {}

    return {
        "GovernanceDirector": make_governance_admission_executor(ac.get("GovernanceDirector")),
        "MissionDirector": make_mission_director_executor(ac.get("MissionDirector")),
        "PhaseCoordinator": make_phase_coordinator_executor("recon", ac.get("PhaseCoordinator")),
        "SurfaceMapper": make_specialist_cluster_executor(
            "surface_scan", ac.get("SurfaceMapper"), simulation_artifact_type="recon_surface"
        ),
        "ReconSpecialist": make_specialist_cluster_executor(
            "active_recon", ac.get("ReconSpecialist"), simulation_artifact_type="pentest_evidence"
        ),
        "EvidenceAnalyst": make_evidence_analysis_executor(ac.get("EvidenceAnalyst")),
        "ReportSynthesisAgent": make_report_synthesis_executor(ac.get("ReportSynthesisAgent")),
        "HandoffLiaison": make_handoff_liaison_executor(ac.get("HandoffLiaison")),
    }
