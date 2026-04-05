"""
K1 Mission Runtime (Phase 4 / 4.5)
=====================================
Top-level mission lifecycle manager that bridges:
  - Praison authority layer (identities, contracts, governance, policy)
  - LangGraph execution engine (compiled StateGraph, checkpointing)
  - Event telemetry (MissionEvent emission)
  - Adaptive execution (plan patches, bounded strategy changes)

Mission lifecycle:
  create_mission()     -> MissionHandle (mission_id, initial state, compiled graph)
  start_mission()      -> executes the graph, returns final state
  resume_mission()     -> resumes from checkpoint after approval/stop
  get_status()         -> returns current mission state snapshot
  get_state()          -> returns full current state dict
  inspect_state()      -> returns detailed state inspection for debugging
  approve_pending()    -> resolves a pending approval and resumes
  stop_mission()       -> gracefully pauses and checkpoints
  cancel_mission()     -> permanently terminates a mission
  list_missions()      -> returns all tracked mission statuses

Praison is the authority layer:
  All personas, permissions, contracts, governance, lifecycle policy,
  and authority boundaries originate from Praison. LangGraph is the
  execution/state engine only.

Simulation-ready:
  execution_mode in initial state controls behavior:
    "live"       -> full execution with real agents and tools
    "graph_only" -> topology validation, stub node execution
    "tool_mock"  -> agents run with mocked tool results
    "replay"     -> checkpoint replay (future)

Checkpointing:
  Uses PostgreSQL checkpointer when available, MemorySaver fallback.
  Every interrupt (approval gate, timeout, controlled stop) creates a
  checkpoint that can be resumed.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

from apps.backend.src.core.kai_execution_selector import (
    ExecutionSubstrate,
    normalize_selector_inputs,
    selector_artifact_for_stage,
)
from apps.backend.src.core.kai_execution_benchmarks import (
    load_benchmark_payload,
    mission_benchmark_record_from_state,
    persist_benchmark_run,
)
from apps.backend.src.core.kai_persona_contracts import validate_persona_contract
from apps.backend.src.core.praison_execution_events import (
    EventBus,
    MissionEvent,
    emit,
    get_event_bus,
    mission_started_event,
    mission_completed_event,
    approval_resolved_event,
)
from apps.backend.src.core.praison_langgraph_builder import (
    PraisonLangGraphBuilder,
    _LANGGRAPH_AVAILABLE,
)
from apps.backend.src.core.praison_node_executors import build_standard_node_callables, make_node_executor
from apps.backend.src.core.praison_state import (
    K1GraphState,
    make_initial_state,
    merge_state,
    state_snapshot,
)
from apps.backend.src.core.praison_adapter_contract import BasicPraisonAdapterContract
from apps.backend.src.core.praison_topology import MissionGraphSpec, PraisonTopology

logger = logging.getLogger(__name__)


# -- DB persistence (fire-and-forget) -----------------------------------------

def _get_db_url_sync() -> str | None:
    """Resolve a synchronous (psycopg2) DATABASE_URL from environment. Returns None if unavailable."""
    import os
    raw = (os.getenv("DATABASE_URL") or "").strip()
    if not raw:
        return None
    # Convert asyncpg URL to psycopg2 URL
    if raw.startswith("postgresql+asyncpg://"):
        raw = raw.replace("postgresql+asyncpg://", "postgresql://", 1)
    return raw


def _fire_and_forget_db(fn: Any, *args: Any, **kwargs: Any) -> None:
    """Run a synchronous DB write in a daemon thread so it never blocks the caller."""
    def _runner() -> None:
        try:
            fn(*args, **kwargs)
        except Exception as exc:
            logger.debug("praison DB persist error (non-fatal): %s", exc)

    t = threading.Thread(target=_runner, daemon=True)
    t.start()


def _upsert_mission_row(
    mission_id: str,
    workflow_id: str,
    program_id: str,
    tenant_id: str,
    mission_name: str,
    execution_mode: str,
    status: str,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
    tools_executed: int = 0,
    artifacts_written: int = 0,
    final_state_summary: dict | None = None,
    error: str | None = None,
) -> None:
    """Insert or update a praison_missions row using psycopg2. Swallows all errors."""
    import json as _json
    import uuid as _uuid

    db_url = _get_db_url_sync()
    if not db_url:
        return
    try:
        import psycopg2
        import psycopg2.extras

        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        cur = conn.cursor()
        fss = _json.dumps(final_state_summary) if final_state_summary else None

        cur.execute("SELECT id FROM praison_missions WHERE mission_id = %s", (mission_id,))
        row = cur.fetchone()
        if row:
            cur.execute(
                """UPDATE praison_missions
                   SET status = %s,
                       started_at = COALESCE(%s, started_at),
                       completed_at = COALESCE(%s, completed_at),
                       tools_executed = %s,
                       artifacts_written = %s,
                       final_state_summary = %s::jsonb,
                       error = %s,
                       updated_at = NOW()
                 WHERE mission_id = %s""",
                (status, started_at, completed_at, tools_executed, artifacts_written, fss, error, mission_id),
            )
        else:
            cur.execute(
                """INSERT INTO praison_missions
                   (id, mission_id, tenant_id, workflow_id, program_id, mission_name,
                    execution_mode, status, started_at, completed_at,
                    tools_executed, artifacts_written, final_state_summary, error,
                    created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,NOW(),NOW())""",
                (
                    str(_uuid.uuid4()), mission_id, tenant_id, workflow_id, program_id, mission_name,
                    execution_mode, status, started_at, completed_at,
                    tools_executed, artifacts_written, fss, error,
                ),
            )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as exc:
        logger.debug("_upsert_mission_row failed (non-fatal): %s", exc)


def _insert_tool_run_row(
    mission_id: str,
    agent_id: str,
    tool_id: str,
    target: str | None,
    status: str,
    execution_time_ms: float | None,
    result_summary: dict | None,
    error: str | None,
) -> None:
    """Append a praison_tool_runs row using psycopg2. Swallows all errors."""
    import json as _json
    import uuid as _uuid

    db_url = _get_db_url_sync()
    if not db_url:
        return
    try:
        import psycopg2

        conn = psycopg2.connect(db_url)
        conn.autocommit = False
        cur = conn.cursor()
        rs = _json.dumps(result_summary) if result_summary else None
        cur.execute(
            """INSERT INTO praison_tool_runs
               (id, mission_id, agent_id, tool_id, target, status,
                execution_time_ms, result_summary, error, created_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,NOW(),NOW())""",
            (
                str(_uuid.uuid4()), mission_id, agent_id, tool_id, target, status,
                execution_time_ms, rs, error,
            ),
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as exc:
        logger.debug("_insert_tool_run_row failed (non-fatal): %s", exc)


# -- Mission handle ------------------------------------------------------------

@dataclass
class MissionHandle:
    """
    Handle to a created (but not yet started) mission.

    Contains the compiled graph, initial state, and metadata needed
    to start, resume, or inspect the mission.
    """
    mission_id: str
    tenant_id: UUID
    workflow_id: str
    program_id: str
    graph_spec: MissionGraphSpec
    compiled_graph: Any         # LangGraph CompiledGraph or None
    initial_state: K1GraphState
    scaffold_spec: dict[str, Any]
    node_callables: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = field(default_factory=dict)
    execution_mode: str = "live"
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    @property
    def is_executable(self) -> bool:
        """True if a compiled LangGraph is available for real execution."""
        return self.compiled_graph is not None


# -- Mission status ------------------------------------------------------------

@dataclass(frozen=True)
class MissionStatus:
    mission_id: str
    tenant_id: UUID
    workflow_id: str
    program_id: str
    state: str          # "created" | "running" | "paused" | "completed" | "failed"
    execution_mode: str
    phase: str
    active_node: str
    progress: float
    error: str
    snapshot: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mission_id": self.mission_id,
            "tenant_id": str(self.tenant_id),
            "workflow_id": self.workflow_id,
            "program_id": self.program_id,
            "state": self.state,
            "execution_mode": self.execution_mode,
            "phase": self.phase,
            "active_node": self.active_node,
            "progress": self.progress,
            "error": self.error,
            "snapshot": self.snapshot,
        }


# -- MissionRuntime ------------------------------------------------------------

class MissionRuntime:
    """
    Top-level mission lifecycle manager.

    Thread-safe for status reads. Mission execution is single-threaded
    per mission_id (enforced by LangGraph's checkpoint locking).
    """

    def __init__(
        self,
        event_bus: EventBus | None = None,
        checkpointer_dsn: str | None = None,
    ) -> None:
        self._event_bus = event_bus or get_event_bus()
        self._checkpointer_dsn = checkpointer_dsn
        self._missions: dict[tuple[UUID, str], MissionHandle] = {}
        self._states: dict[str, dict[str, Any]] = {}
        self._statuses: dict[str, str] = {}  # mission_id -> state string
        self._mission_locks: dict[str, asyncio.Lock] = {}
        self._metrics_lock = threading.Lock()
        self._selector_performance_profile: dict[str, dict[str, float]] = {}
        self._event_bus.subscribe(self._capture_runtime_metrics_event)

    def _get_lock(self, mission_id: str) -> asyncio.Lock:
        """Return the per-mission asyncio.Lock, creating it on first access."""
        if mission_id not in self._mission_locks:
            self._mission_locks[mission_id] = asyncio.Lock()
        return self._mission_locks[mission_id]

    @staticmethod
    def _run_sync_or_async(coro: Awaitable[Any]) -> Any:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)
        return coro

    def _resolve_tenant_id(
        self,
        mission_id: str,
        tenant_id: UUID | None = None,
    ) -> UUID:
        if tenant_id is not None:
            return tenant_id
        discovered = self.tenant_for_mission(mission_id)
        if discovered is not None:
            return discovered
        raise ValueError(f"Mission {mission_id} not found")

    def _merge_selector_inputs(
        self,
        state: dict[str, Any],
        handle: MissionHandle,
        *,
        stage_id: str,
        node_id: str,
    ) -> dict[str, Any]:
        base_inputs = normalize_selector_inputs(state.get("selector_inputs", {}))
        merged = dict(base_inputs)
        merged.update({
            "stage_id": stage_id,
            "node_id": node_id,
            "execution_mode": state.get("execution_mode", handle.execution_mode),
            "needs_resume": base_inputs.get("needs_resume", True),
        })
        if self._selector_performance_profile and not merged.get("performance_profile"):
            merged["performance_profile"] = self._selector_performance_profile
        if merged.get("execution_mode") == "graph_only":
            merged["is_stateless"] = True
            merged["needs_resume"] = False
            merged["workflow_complexity"] = "low"
            merged["tool_privilege_level"] = "read"
            merged["latency_slo_ms"] = 100
        return merged

    def _refresh_selector_performance_profile(self) -> None:
        payload = load_benchmark_payload()
        profile = payload.get("selector_performance_profile", {}) if isinstance(payload, dict) else {}
        if isinstance(profile, dict):
            self._selector_performance_profile = {
                str(k): v for k, v in profile.items() if isinstance(v, dict)
            }

    @staticmethod
    def _selector_policy_event_from_artifact(artifact: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": "execution_selector_policy",
            "stage_id": artifact.get("stage_id", ""),
            "node_id": artifact.get("node_id", ""),
            "decision": artifact.get("selected_substrate", ""),
            "fallback_substrate": artifact.get("fallback_substrate", ""),
            "denied": bool(artifact.get("denied", False)),
            "timestamp": artifact.get("timestamp"),
        }

    @staticmethod
    def _safe_float(value: Any, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return float(default)

    @staticmethod
    def _safe_int(value: Any, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return int(default)

    def _ensure_runtime_metrics(self, state: dict[str, Any]) -> dict[str, Any]:
        metrics = state.get("runtime_metrics", {})
        if not isinstance(metrics, dict):
            metrics = {}
        metrics.setdefault("stage_timings", [])
        metrics.setdefault("tool_timings", [])
        metrics.setdefault("selector_decision_count", 0)
        metrics.setdefault("tool_invocations", 0)
        metrics.setdefault("tool_failures", 0)
        metrics.setdefault("tool_retry_count", 0)
        metrics.setdefault("tool_duration_ms_total", 0.0)
        metrics.setdefault("model_calls", 0)
        metrics.setdefault("total_tokens", 0)
        metrics.setdefault("estimated_cost_cents", 0.0)
        state["runtime_metrics"] = metrics
        return metrics

    def _append_stage_timing(
        self,
        state: dict[str, Any],
        *,
        stage_id: str,
        node_id: str,
        selected_substrate: str,
        status: str,
        duration_ms: float,
        started_at: str,
    ) -> None:
        metrics = self._ensure_runtime_metrics(state)
        stage_timings = metrics.get("stage_timings")
        if not isinstance(stage_timings, list):
            stage_timings = []
        stage_timings.append({
            "stage_id": stage_id,
            "node_id": node_id,
            "selected_substrate": selected_substrate,
            "status": status,
            "duration_ms": round(float(duration_ms), 2),
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        })
        metrics["stage_timings"] = stage_timings

    def _finalize_runtime_metrics(
        self,
        state: dict[str, Any],
        *,
        mission_started_monotonic: float,
    ) -> dict[str, Any]:
        metrics = self._ensure_runtime_metrics(state)
        total_mission_ms = (time.monotonic() - mission_started_monotonic) * 1000.0
        metrics["total_mission_ms"] = round(total_mission_ms, 2)
        metrics["mission_completed_at"] = datetime.now(timezone.utc).isoformat()

        stage_timings = metrics.get("stage_timings", [])
        if not isinstance(stage_timings, list):
            stage_timings = []
        stage_durations = [
            self._safe_float(row.get("duration_ms"), 0.0)
            for row in stage_timings
            if isinstance(row, dict)
        ]
        stage_failures = [
            row for row in stage_timings
            if isinstance(row, dict) and str(row.get("status", "")).lower() not in {"completed", "success"}
        ]
        metrics["stage_count"] = len(stage_timings)
        metrics["stage_failure_count"] = len(stage_failures)
        metrics["stage_failure_rate"] = round(len(stage_failures) / max(1, len(stage_timings)), 4)
        metrics["avg_stage_ms"] = round(sum(stage_durations) / max(1, len(stage_durations)), 2)

        tool_invocations = self._safe_int(metrics.get("tool_invocations"), 0)
        tool_failures = self._safe_int(metrics.get("tool_failures"), 0)
        tool_retry_count = self._safe_int(metrics.get("tool_retry_count"), 0)
        metrics["tool_failure_rate"] = round(tool_failures / max(1, tool_invocations), 4)
        metrics["retry_frequency"] = round(tool_retry_count / max(1, tool_invocations), 4)
        metrics["avg_tool_duration_ms"] = round(
            self._safe_float(metrics.get("tool_duration_ms_total"), 0.0) / max(1, tool_invocations),
            2,
        )

        state["runtime_metrics"] = metrics
        return metrics

    def _runtime_metrics_summary(self, state: dict[str, Any]) -> dict[str, Any]:
        metrics = state.get("runtime_metrics", {})
        if not isinstance(metrics, dict):
            return {}
        return {
            "total_mission_ms": self._safe_float(metrics.get("total_mission_ms"), 0.0),
            "stage_count": self._safe_int(metrics.get("stage_count"), 0),
            "avg_stage_ms": self._safe_float(metrics.get("avg_stage_ms"), 0.0),
            "tool_invocations": self._safe_int(metrics.get("tool_invocations"), 0),
            "tool_failure_rate": self._safe_float(metrics.get("tool_failure_rate"), 0.0),
            "retry_frequency": self._safe_float(metrics.get("retry_frequency"), 0.0),
            "model_calls": self._safe_int(metrics.get("model_calls"), 0),
            "total_tokens": self._safe_int(metrics.get("total_tokens"), 0),
            "estimated_cost_cents": self._safe_float(metrics.get("estimated_cost_cents"), 0.0),
            "selected_substrate": str(metrics.get("selected_substrate", "")),
        }

    def _capture_runtime_metrics_event(self, event: MissionEvent) -> None:
        event_type = str(getattr(event, "event_type", "") or "")
        if event_type not in {"tool_invocation_completed", "llm_invocation_completed"}:
            return

        mission_id = str(getattr(event, "mission_id", "") or "")
        if not mission_id:
            return

        with self._metrics_lock:
            state = self._states.get(mission_id)
            if not isinstance(state, dict):
                return
            detail = getattr(event, "detail", {})
            if not isinstance(detail, dict):
                detail = {}
            metrics = self._ensure_runtime_metrics(state)

            if event_type == "tool_invocation_completed":
                metrics["tool_invocations"] = self._safe_int(metrics.get("tool_invocations"), 0) + 1
                status = str(detail.get("status") or "").lower()
                if status and status not in {"completed", "success", "dispatched"}:
                    metrics["tool_failures"] = self._safe_int(metrics.get("tool_failures"), 0) + 1

                duration_ms = self._safe_float(detail.get("duration_ms"), 0.0)
                metrics["tool_duration_ms_total"] = (
                    self._safe_float(metrics.get("tool_duration_ms_total"), 0.0) + duration_ms
                )
                retries = self._safe_int(detail.get("retry_count"), 0)
                metrics["tool_retry_count"] = self._safe_int(metrics.get("tool_retry_count"), 0) + retries

                tokens = self._safe_int(detail.get("estimated_tokens"), 0)
                metrics["total_tokens"] = self._safe_int(metrics.get("total_tokens"), 0) + max(0, tokens)
                metrics["estimated_cost_cents"] = round(
                    self._safe_float(metrics.get("estimated_cost_cents"), 0.0)
                    + self._safe_float(detail.get("estimated_cost_cents"), 0.0),
                    6,
                )

                tool_timings = metrics.get("tool_timings", [])
                if not isinstance(tool_timings, list):
                    tool_timings = []
                tool_timings.append({
                    "tool_id": str(detail.get("tool_id") or detail.get("tool_name") or ""),
                    "tool_execution_id": str(detail.get("tool_execution_id") or ""),
                    "node_id": str(detail.get("node_id") or ""),
                    "stage_id": str(detail.get("stage_id") or ""),
                    "duration_ms": round(duration_ms, 2),
                    "status": str(detail.get("status") or ""),
                    "selected_substrate": str(detail.get("selected_substrate") or ""),
                    "retry_count": retries,
                })
                metrics["tool_timings"] = tool_timings
            elif event_type == "llm_invocation_completed":
                metrics["model_calls"] = self._safe_int(metrics.get("model_calls"), 0) + 1
                token_usage = detail.get("token_usage", {})
                if isinstance(token_usage, dict):
                    total_tokens = self._safe_int(
                        token_usage.get("total_tokens")
                        or token_usage.get("total")
                        or (self._safe_int(token_usage.get("input_tokens"), 0)
                            + self._safe_int(token_usage.get("output_tokens"), 0)),
                        0,
                    )
                    metrics["total_tokens"] = self._safe_int(metrics.get("total_tokens"), 0) + max(0, total_tokens)

            state["runtime_metrics"] = metrics
            self._states[mission_id] = state

    def _validate_persona_contract(
        self,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        persona_contract = state.get("persona_contract")
        if not isinstance(persona_contract, dict) or not persona_contract:
            return {
                "valid": True,
                "blocked": False,
                "errors": [],
                "translation_loss_warnings": [],
                "block_reasons": [],
                "normalized": {},
            }
        tenant_mode = str(
            state.get("selector_inputs", {}).get("tenant_mode", "single")
            if isinstance(state.get("selector_inputs"), dict)
            else "single"
        )
        return validate_persona_contract(persona_contract, tenant_mode=tenant_mode)

    def _try_praison_adapter(
        self,
        handle: MissionHandle,
        state: dict[str, Any],
    ) -> dict[str, Any] | None:
        backend = state.get("praison_adapter_backend")
        if backend is None:
            return None

        adapter = BasicPraisonAdapterContract(backend)
        ticket = adapter.submit(
            mission_id=handle.mission_id,
            workflow_id=handle.workflow_id,
            program_id=handle.program_id,
            payload={
                "mission_name": state.get("mission_name", ""),
                "phase": state.get("phase", ""),
                "selector_inputs": state.get("selector_inputs", {}),
            },
            idempotency_key=f"{handle.mission_id}:{handle.workflow_id}:{handle.program_id}",
        )
        reconciliation = adapter.reconcile(ticket)
        update: dict[str, Any] = {
            "artifacts": [{
                "artifact_id": str(uuid.uuid4()),
                "artifact_type": "praison_adapter_reconciliation",
                "summary": f"Praison adapter status={reconciliation.get('status', 'unknown')}",
                "content": {
                    "ticket": ticket.to_dict(),
                    "reconciliation": reconciliation,
                },
            }],
            "events": [{
                "event_type": "praison_adapter_reconciliation",
                "status": reconciliation.get("status"),
                "terminal": reconciliation.get("terminal", False),
            }],
        }
        if reconciliation.get("terminal"):
            if reconciliation.get("status") == "completed":
                update["summary"] = "Mission completed through Praison adapter contract."
                update["completed"] = True
                update["phase_complete"] = True
                update["progress"] = 1.0
            else:
                update["error"] = f"Praison adapter terminal status={reconciliation.get('status')}"
        return update

    # -- Create ----------------------------------------------------------------

    def create_mission(
        self,
        workflow_id: str,
        program_id: str,
        tenant_id: UUID | None = None,
        mission_name: str = "",
        execution_mode: str = "live",
        selector_inputs: dict[str, Any] | None = None,
        persona_contract: dict[str, Any] | None = None,
        agent_specs: dict[str, dict[str, Any]] | None = None,
        agent_callables: dict[str, Callable[[dict[str, Any]], dict[str, Any]] | None] | None = None,
        graph_spec: MissionGraphSpec | None = None,
    ) -> MissionHandle:
        """
        Create a mission: build topology, compile graph, prepare initial state.

        agent_specs: {agent_id: langgraph_node_spec_dict} for topology building.
          If None, uses minimal specs sufficient for graph_only execution.
        agent_callables: {node_id: callable} for real agent execution.
          If None, nodes run in graph_only mode (returns stub updates).
        graph_spec: Pre-built MissionGraphSpec. If None, builds standard bug bounty topology.
        """
        mission_id = str(uuid.uuid4())
        resolved_tenant_id = tenant_id or uuid.uuid4()

        custom_graph_spec_supplied = graph_spec is not None

        # Build topology
        if graph_spec is None:
            specs = agent_specs or _make_minimal_agent_specs()
            graph_spec = PraisonTopology.build_standard_bug_bounty(
                workflow_id=workflow_id,
                program_id=program_id,
                agent_specs=specs,
            )
        provided_callable_keys = set(agent_callables.keys()) if agent_callables else set()

        # Build node callables
        # For default topology, always wrap through the standard node executor
        # layer so node telemetry/events/artifact IDs are emitted consistently.
        # For explicit custom graph specs, preserve direct callables as provided.
        if custom_graph_spec_supplied and agent_callables:
            node_callables = dict(agent_callables)
        else:
            node_callables = build_standard_node_callables(agent_callables)

        # Always provide a safe graph-only fallback executor for any node not
        # mapped by the standard callable set.
        for node_id in graph_spec.nodes.keys():
            if node_id not in node_callables:
                node_callables[node_id] = make_node_executor(node_id, None)

        # Compile LangGraph
        builder = PraisonLangGraphBuilder(graph_spec, node_callables)
        scaffold = builder.build_scaffold_spec()
        partial_callable_override = bool(agent_callables) and provided_callable_keys != set(graph_spec.nodes.keys())
        compiled = None if partial_callable_override else builder.compile(checkpointer_dsn=self._checkpointer_dsn)

        # Build initial state
        initial = make_initial_state(
            tenant_id=resolved_tenant_id,
            workflow_id=workflow_id,
            program_id=program_id,
            mission_name=mission_name,
            execution_mode=execution_mode,
            mission_id=mission_id,
        )
        initial["selector_inputs"] = normalize_selector_inputs(selector_inputs or {})
        if persona_contract:
            initial["persona_contract"] = dict(persona_contract)

        handle = MissionHandle(
            mission_id=mission_id,
            tenant_id=resolved_tenant_id,
            workflow_id=workflow_id,
            program_id=program_id,
            graph_spec=graph_spec,
            compiled_graph=compiled,
            initial_state=initial,
            scaffold_spec=scaffold,
            node_callables=node_callables,
            execution_mode=execution_mode,
        )

        self._missions[(resolved_tenant_id, mission_id)] = handle
        self._states[mission_id] = dict(initial)
        self._statuses[mission_id] = "created"

        logger.info(
            "Mission created: id=%s workflow=%s mode=%s executable=%s",
            mission_id, workflow_id, execution_mode, handle.is_executable,
        )

        # Persist mission row (non-blocking)
        _fire_and_forget_db(
            _upsert_mission_row,
            mission_id=mission_id,
            workflow_id=workflow_id,
            program_id=program_id,
            tenant_id=str(resolved_tenant_id),
            mission_name=mission_name,
            execution_mode=execution_mode,
            status="created",
        )

        return handle

    # -- Start -----------------------------------------------------------------

    def start_mission(self, mission_id: str, tenant_id: UUID | None = None) -> dict[str, Any]:
        """
        Start mission execution. Returns final state dict.
        For graph_only mode: executes stub nodes synchronously.
        For live mode with LangGraph: invokes the compiled graph.
        For live mode without LangGraph: executes nodes via fallback path.
        """
        resolved_tenant_id = self._resolve_tenant_id(mission_id, tenant_id)
        handle = self._get_handle(mission_id, resolved_tenant_id)
        self._statuses[mission_id] = "running"
        current_state = dict(self._states.get(mission_id, {}))
        mission_started_monotonic = time.monotonic()
        mission_started_at = datetime.now(timezone.utc).isoformat()
        self._refresh_selector_performance_profile()

        contract_validation = self._validate_persona_contract(current_state)
        current_state["persona_contract_validation"] = contract_validation
        if contract_validation.get("blocked"):
            current_state["error"] = (
                "Persona/agent contract validation blocked mission deployment: "
                + ", ".join(contract_validation.get("block_reasons", []))
            )
            self._finalize_runtime_metrics(current_state, mission_started_monotonic=mission_started_monotonic)
            self._states[mission_id] = current_state
            self._statuses[mission_id] = "failed"
            persist_benchmark_run(
                mission_benchmark_record_from_state(
                    mission_id=mission_id,
                    workflow_id=handle.workflow_id,
                    program_id=handle.program_id,
                    execution_mode=handle.execution_mode,
                    terminal_status="failed",
                    state=current_state,
                )
            )
            return current_state

        selector_inputs = self._merge_selector_inputs(
            current_state,
            handle,
            stage_id="mission_start",
            node_id="mission_dispatch",
        )
        selector_decision_start = time.monotonic()
        selector_artifact = selector_artifact_for_stage(
            stage_id="mission_start",
            node_id="mission_dispatch",
            selector_inputs=selector_inputs,
        )
        selector_decision_latency_ms = (time.monotonic() - selector_decision_start) * 1000.0
        metrics = self._ensure_runtime_metrics(current_state)
        metrics["mission_started_at"] = mission_started_at
        metrics["selected_substrate"] = selector_artifact.get("selected_substrate", "")
        metrics["fallback_substrate"] = selector_artifact.get("fallback_substrate", "")
        metrics["selector_decision_latency_ms"] = round(selector_decision_latency_ms, 2)
        metrics["selector_decision_count"] = self._safe_int(metrics.get("selector_decision_count"), 0) + 1
        current_state["runtime_metrics"] = metrics
        current_state = _merge_state(
            current_state,
            {
                "selector_policy_artifacts": [selector_artifact],
                "policy_events": [self._selector_policy_event_from_artifact(selector_artifact)],
            },
        )
        self._states[mission_id] = current_state

        if selector_artifact.get("denied"):
            current_state["error"] = "Execution selector denied mission start."
            self._finalize_runtime_metrics(current_state, mission_started_monotonic=mission_started_monotonic)
            self._states[mission_id] = current_state
            self._statuses[mission_id] = "failed"
            persist_benchmark_run(
                mission_benchmark_record_from_state(
                    mission_id=mission_id,
                    workflow_id=handle.workflow_id,
                    program_id=handle.program_id,
                    execution_mode=handle.execution_mode,
                    terminal_status="failed",
                    state=current_state,
                )
            )
            return current_state

        emit(mission_started_event(
            mission_id=mission_id,
            workflow_id=handle.workflow_id,
            program_id=handle.program_id,
            execution_mode=handle.execution_mode,
            mission_name=handle.initial_state.get("mission_name", ""),
            correlation={
                "stage_id": selector_artifact.get("stage_id", "mission_start"),
                "node_id": selector_artifact.get("node_id", "mission_dispatch"),
                "selected_substrate": selector_artifact.get("selected_substrate", ""),
                "fallback_substrate": selector_artifact.get("fallback_substrate", ""),
                "risk_band": selector_inputs.get("risk_band"),
                "tenant_id": str(handle.tenant_id),
            },
        ))

        try:
            selected_substrate = str(selector_artifact.get("selected_substrate") or "")
            final_state: dict[str, Any] | None = None
            if selected_substrate == ExecutionSubstrate.PRAISON_EXTERNAL.value:
                try:
                    adapter_update = self._try_praison_adapter(handle, current_state)
                except Exception as exc:
                    adapter_update = {
                        "events": [{
                            "event_type": "praison_adapter_failed",
                            "error": str(exc),
                        }],
                        "policy_events": [{
                            "type": "execution_selector_policy",
                            "decision": "PRAISON_EXTERNAL_FAILED",
                            "reason": str(exc),
                        }],
                    }
                if adapter_update:
                    current_state = _merge_state(current_state, adapter_update)
                    self._states[mission_id] = current_state
                    if current_state.get("completed") or current_state.get("error"):
                        final_state = current_state
                    else:
                        selected_substrate = str(selector_artifact.get("fallback_substrate") or "")
                else:
                    selected_substrate = str(selector_artifact.get("fallback_substrate") or "")

            if final_state is None and selected_substrate == ExecutionSubstrate.MISSIONRUNTIME_CUSTOM.value:
                final_state = self._execute_fallback(handle, resume_state=current_state)
            elif final_state is None and selected_substrate in {
                    ExecutionSubstrate.LANGGRAPH_PRIMARY.value,
                    ExecutionSubstrate.DEEPAGENTS_SPECIALIST.value,
                    ExecutionSubstrate.PRAISON_EXTERNAL.value,
            }:
                if handle.is_executable:
                    final_state = self._execute_langgraph(handle, start_state=current_state)
                else:
                    final_state = self._execute_fallback(handle, resume_state=current_state)
            elif final_state is None:
                # Safe fallback for unknown substrate labels.
                if handle.is_executable:
                    final_state = self._execute_langgraph(handle, start_state=current_state)
                else:
                    final_state = self._execute_fallback(handle, resume_state=current_state)

            self._states[mission_id] = final_state
            success = not final_state.get("error")
            terminal_status = "completed" if success else "failed"
            self._statuses[mission_id] = terminal_status
            self._finalize_runtime_metrics(final_state, mission_started_monotonic=mission_started_monotonic)

            emit(mission_completed_event(
                mission_id=mission_id,
                workflow_id=handle.workflow_id,
                program_id=handle.program_id,
                success=success,
                final_report_id=final_state.get("final_report_id", ""),
                metrics=self._runtime_metrics_summary(final_state),
            ))

            benchmark_record = mission_benchmark_record_from_state(
                mission_id=mission_id,
                workflow_id=handle.workflow_id,
                program_id=handle.program_id,
                execution_mode=handle.execution_mode,
                terminal_status=terminal_status,
                state=final_state,
            )
            persist_benchmark_run(benchmark_record)

            # Persist completion (non-blocking)
            tools_run = len(final_state.get("tool_results", []))
            artifacts_count = len(final_state.get("artifacts", []))
            _fire_and_forget_db(
                _upsert_mission_row,
                mission_id=mission_id,
                workflow_id=handle.workflow_id,
                program_id=handle.program_id,
                tenant_id=str(handle.tenant_id),
                mission_name=handle.initial_state.get("mission_name", ""),
                execution_mode=handle.execution_mode,
                status=terminal_status,
                completed_at=datetime.now(timezone.utc),
                tools_executed=tools_run,
                artifacts_written=artifacts_count,
                final_state_summary={
                    "phase": final_state.get("phase", ""),
                    "final_report_id": final_state.get("final_report_id", ""),
                    "summary": final_state.get("summary", ""),
                    "error": final_state.get("error", ""),
                },
                error=final_state.get("error") or None,
            )

            return final_state

        except Exception as exc:
            logger.error("Mission %s execution failed: %s", mission_id, exc, exc_info=True)
            self._statuses[mission_id] = "failed"
            state = dict(self._states.get(mission_id, {}))
            state["error"] = str(exc)
            self._finalize_runtime_metrics(state, mission_started_monotonic=mission_started_monotonic)
            self._states[mission_id] = state
            benchmark_record = mission_benchmark_record_from_state(
                mission_id=mission_id,
                workflow_id=handle.workflow_id,
                program_id=handle.program_id,
                execution_mode=handle.execution_mode,
                terminal_status="failed",
                state=state,
            )
            persist_benchmark_run(benchmark_record)

            # Persist failure (non-blocking)
            _fire_and_forget_db(
                _upsert_mission_row,
                mission_id=mission_id,
                workflow_id=handle.workflow_id,
                program_id=handle.program_id,
                tenant_id=str(handle.tenant_id),
                mission_name=handle.initial_state.get("mission_name", ""),
                execution_mode=handle.execution_mode,
                status="failed",
                completed_at=datetime.now(timezone.utc),
                error=str(exc),
            )

            return state

    # -- Resume ----------------------------------------------------------------

    def resume_mission(
        self,
        mission_id: str,
        tenant_id: UUID | None = None,
        approval_data: dict[str, Any] | None = None,
    ) -> dict[str, Any] | Awaitable[dict[str, Any]]:
        """
        Resume mission from checkpoint after approval, timeout, or controlled stop.

        approval_data: If resuming after an approval gate, provide the approval decision.
        """
        resolved_tenant_id = self._resolve_tenant_id(mission_id, tenant_id)

        async def _runner() -> dict[str, Any]:
            async with self._get_lock(mission_id):
                return self._resume_mission_locked(mission_id, resolved_tenant_id, approval_data)

        return self._run_sync_or_async(_runner())

    def _resume_mission_locked(
        self,
        mission_id: str,
        tenant_id: UUID,
        approval_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Internal: execute resume logic with lock already held."""
        handle = self._get_handle(mission_id, tenant_id)

        if approval_data:
            current = self._states.get(mission_id, {})
            current_approvals = list(current.get("approvals_resolved", []))
            current_approvals.append({
                "approval_id": approval_data.get("approval_id", ""),
                "decision": approval_data.get("decision", "approved"),
                "resolved_by": approval_data.get("resolved_by", "operator"),
                "resolved_at": datetime.now(timezone.utc).isoformat(),
            })
            current["approvals_resolved"] = current_approvals
            current["governance_decision"] = approval_data.get("decision", "approved")
            self._states[mission_id] = current

            emit(approval_resolved_event(
                mission_id=mission_id,
                workflow_id=handle.workflow_id,
                program_id=handle.program_id,
                approval_id=approval_data.get("approval_id", ""),
                decision=approval_data.get("decision", "approved"),
                resolved_by=approval_data.get("resolved_by", "operator"),
            ))

        self._statuses[mission_id] = "running"

        # Clear stop/pause error so fallback loop doesn't exit immediately
        current = self._states.get(mission_id, {})
        if current.get("error", "").startswith("Mission stopped:"):
            current["error"] = ""
            self._states[mission_id] = current

        if handle.is_executable and _LANGGRAPH_AVAILABLE:
            return self._resume_langgraph(handle)

        # Fallback: re-execute from current state
        final = self._execute_fallback(handle, resume_state=self._states.get(mission_id))
        self._states[mission_id] = final
        success = not final.get("error")
        self._statuses[mission_id] = "completed" if success else "failed"
        return final

    # -- Status ----------------------------------------------------------------

    def get_status(self, mission_id: str, tenant_id: UUID | None = None) -> MissionStatus:
        """Return current mission status."""
        resolved_tenant_id = self._resolve_tenant_id(mission_id, tenant_id)
        handle = self._get_handle(mission_id, resolved_tenant_id)
        state = self._states.get(mission_id, {})
        return MissionStatus(
            mission_id=mission_id,
            tenant_id=resolved_tenant_id,
            workflow_id=handle.workflow_id,
            program_id=handle.program_id,
            state=self._statuses.get(mission_id, "unknown"),
            execution_mode=handle.execution_mode,
            phase=state.get("phase", ""),
            active_node=state.get("active_node", ""),
            progress=state.get("progress", 0.0),
            error=state.get("error", ""),
            snapshot=state_snapshot(state),
        )

    def get_state(self, mission_id: str) -> dict[str, Any]:
        """Return full current state for a mission."""
        return dict(self._states.get(mission_id, {}))

    # -- Stop ------------------------------------------------------------------

    def stop_mission(
        self,
        mission_id: str,
        tenant_id: UUID | None = None,
        reason: str = "operator_stop",
    ) -> dict[str, Any] | Awaitable[dict[str, Any]]:
        """Gracefully stop and checkpoint a mission."""
        if isinstance(tenant_id, str) and reason == "operator_stop":
            # Backward compatibility for old call shape:
            # stop_mission(mission_id, reason)
            reason = tenant_id
            tenant_id = None
        resolved_tenant_id = self._resolve_tenant_id(mission_id, tenant_id)

        async def _runner() -> dict[str, Any]:
            async with self._get_lock(mission_id):
                # Ensure mission exists and belongs to tenant
                self._get_handle(mission_id, resolved_tenant_id)
                self._statuses[mission_id] = "paused"
                state = self._states.get(mission_id, {})
                state["error"] = f"Mission stopped: {reason}"
                self._states[mission_id] = state
                logger.info("Mission %s stopped: %s", mission_id, reason)
                return state

        return self._run_sync_or_async(_runner())

    # -- Cancel ----------------------------------------------------------------

    def cancel_mission(
        self,
        mission_id: str,
        tenant_id: UUID | None = None,
        reason: str = "operator_cancel",
    ) -> dict[str, Any] | Awaitable[dict[str, Any]]:
        """
        Permanently cancel a mission. Cannot be resumed after cancel.
        """
        if isinstance(tenant_id, str) and reason == "operator_cancel":
            # Backward compatibility for old call shape:
            # cancel_mission(mission_id, reason)
            reason = tenant_id
            tenant_id = None
        resolved_tenant_id = self._resolve_tenant_id(mission_id, tenant_id)

        async def _runner() -> dict[str, Any]:
            async with self._get_lock(mission_id):
                self._get_handle(mission_id, resolved_tenant_id)  # Ensure mission belongs to tenant
                self._statuses[mission_id] = "cancelled"
                state = self._states.get(mission_id, {})
                state["error"] = f"Mission cancelled: {reason}"
                state["completed"] = True
                self._states[mission_id] = state

                emit(mission_completed_event(
                    mission_id=mission_id,
                    workflow_id=state.get("workflow_id", ""),
                    program_id=state.get("program_id", ""),
                    success=False,
                    final_report_id="",
                ))

                logger.info("Mission %s cancelled: %s", mission_id, reason)
                return state

        return self._run_sync_or_async(_runner())

    # -- Inspect ---------------------------------------------------------------

    def inspect_state(self, mission_id: str, tenant_id: UUID | None = None) -> dict[str, Any]:
        """
        Return detailed state inspection for debugging and time-travel analysis.

        Includes full state, mission handle metadata, and lifecycle status.
        Unlike get_state() which returns raw state, this includes contextual
        metadata useful for debugging interrupted or failed missions.
        """
        resolved_tenant_id = self._resolve_tenant_id(mission_id, tenant_id)
        handle = self._get_handle(mission_id, resolved_tenant_id)
        state = self._states.get(mission_id, {})

        return {
            "mission_id": mission_id,
            "workflow_id": handle.workflow_id,
            "program_id": handle.program_id,
            "lifecycle_state": self._statuses.get(mission_id, "unknown"),
            "execution_mode": handle.execution_mode,
            "is_executable": handle.is_executable,
            "created_at": handle.created_at,
            "snapshot": state_snapshot(state),
            "node_history": state.get("node_history", []),
            "pending_approvals": state.get("approvals_required", []),
            "resolved_approvals": state.get("approvals_resolved", []),
            "errors": state.get("errors", []),
            "patches_applied": state.get("adaptive_plan_patches_applied", []),
            "patches_rejected": state.get("adaptive_plan_patches_rejected", []),
            "profiles_used": state.get("strategy_profiles_used", []),
            "lessons_generated": state.get("knowledge_lessons_generated", []),
            "selector_policy_artifacts": state.get("selector_policy_artifacts", []),
            "persona_contract_validation": state.get("persona_contract_validation", {}),
            "scaffold_spec": {
                "node_count": len(handle.scaffold_spec.get("nodes", [])),
                "edge_count": len(handle.scaffold_spec.get("edges", [])),
                "interrupt_before": handle.scaffold_spec.get("interrupt_before", []),
                "interrupt_after": handle.scaffold_spec.get("interrupt_after", []),
            },
        }

    # -- List ------------------------------------------------------------------

    def list_missions(self, tenant_id: UUID | None = None) -> list[MissionStatus]:
        """Return status summaries for all tracked missions for a given tenant."""
        results = []
        for (tid, mid), handle in self._missions.items():
            if tenant_id is None or tid == tenant_id:
                try:
                    results.append(self.get_status(mid, tid))
                except ValueError:
                    pass
        return results

    def tenant_for_mission(self, mission_id: str) -> UUID | None:
        """Resolve tenant ownership for a mission id."""
        for tenant_id, current_mission_id in self._missions.keys():
            if current_mission_id == mission_id:
                return tenant_id
        return None

    # -- Approve ---------------------------------------------------------------

    def approve_pending(
        self,
        mission_id: str,
        approval_id: str,
        tenant_id: UUID | None = None,
        decision: str = "approved",
        resolved_by: str = "operator",
    ) -> MissionStatus | Awaitable[MissionStatus]:
        """
        Resolve a pending approval and resume execution.
        """
        resolved_tenant_id = self._resolve_tenant_id(mission_id, tenant_id)

        async def _runner() -> MissionStatus:
            async with self._get_lock(mission_id):
                return await self._approve_pending_locked(
                    mission_id=mission_id,
                    tenant_id=resolved_tenant_id,
                    approval_id=approval_id,
                    decision=decision,
                    resolved_by=resolved_by,
                )

        return self._run_sync_or_async(_runner())

    async def _approve_pending_locked(
        self,
        mission_id: str,
        tenant_id: UUID,
        approval_id: str,
        decision: str = "approved",
        resolved_by: str = "operator",
    ) -> MissionStatus:
        """Internal: execute approval with lock already held."""
        handle = self._get_handle(mission_id, tenant_id)
        current = self._states.get(mission_id, {})

        # Record the approval resolution
        resolution = {
            "approval_id": approval_id,
            "decision": decision,
            "resolved_by": resolved_by,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
        }
        current_approvals = list(current.get("approvals_resolved", []))
        current_approvals.append(resolution)
        current["approvals_resolved"] = current_approvals
        current["governance_decision"] = decision
        self._states[mission_id] = current

        emit(approval_resolved_event(
            mission_id=mission_id,
            workflow_id=handle.workflow_id,
            program_id=handle.program_id,
            approval_id=approval_id,
            decision=decision,
            resolved_by=resolved_by,
        ))

        logger.info(
            "Approval %s resolved for mission %s: decision=%s by=%s",
            approval_id, mission_id, decision, resolved_by,
        )

        # Auto-resume if mission was paused.
        # Lock is already held — call the internal method directly to avoid deadlock.
        status = self._statuses.get(mission_id, "")
        if status == "paused" and decision == "approved":
            self._resume_mission_locked(mission_id, tenant_id=tenant_id)

        return self.get_status(mission_id, tenant_id=tenant_id)

    # -- Internal execution ----------------------------------------------------

    def _execute_langgraph(
        self,
        handle: MissionHandle,
        start_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute via compiled LangGraph. Synchronous invoke."""
        config = {"configurable": {"thread_id": handle.mission_id}}
        seed = dict(start_state or handle.initial_state)
        started_at = datetime.now(timezone.utc).isoformat()
        started = time.monotonic()
        last_selector = (
            seed.get("selector_policy_artifacts", [{}])[-1]
            if isinstance(seed.get("selector_policy_artifacts", []), list) and seed.get("selector_policy_artifacts")
            else {}
        )
        selected_substrate = str(last_selector.get("selected_substrate") or ExecutionSubstrate.LANGGRAPH_PRIMARY.value)
        emit(MissionEvent(
            event_type="stage_execution_started",
            mission_id=handle.mission_id,
            workflow_id=handle.workflow_id,
            program_id=handle.program_id,
            node_id="langgraph_graph",
            phase=str(seed.get("phase", "")),
            detail={
                "stage_id": str(seed.get("phase") or "mission"),
                "selected_substrate": selected_substrate,
            },
        ))
        try:
            result = handle.compiled_graph.invoke(seed, config)
            final = dict(result) if result else seed
            stage_status = "completed" if not final.get("error") else "failed"
            duration_ms = (time.monotonic() - started) * 1000.0
            self._append_stage_timing(
                final,
                stage_id=str(final.get("phase") or "mission"),
                node_id="langgraph_graph",
                selected_substrate=selected_substrate,
                status=stage_status,
                duration_ms=duration_ms,
                started_at=started_at,
            )
            emit(MissionEvent(
                event_type="stage_execution_completed",
                mission_id=handle.mission_id,
                workflow_id=handle.workflow_id,
                program_id=handle.program_id,
                node_id="langgraph_graph",
                phase=str(final.get("phase", "")),
                detail={
                    "stage_id": str(final.get("phase") or "mission"),
                    "selected_substrate": selected_substrate,
                    "duration_ms": round(duration_ms, 2),
                    "status": stage_status,
                },
            ))
            return final
        except Exception:
            duration_ms = (time.monotonic() - started) * 1000.0
            self._append_stage_timing(
                seed,
                stage_id=str(seed.get("phase") or "mission"),
                node_id="langgraph_graph",
                selected_substrate=selected_substrate,
                status="failed",
                duration_ms=duration_ms,
                started_at=started_at,
            )
            emit(MissionEvent(
                event_type="stage_execution_completed",
                mission_id=handle.mission_id,
                workflow_id=handle.workflow_id,
                program_id=handle.program_id,
                node_id="langgraph_graph",
                phase=str(seed.get("phase", "")),
                detail={
                    "stage_id": str(seed.get("phase") or "mission"),
                    "selected_substrate": selected_substrate,
                    "duration_ms": round(duration_ms, 2),
                    "status": "failed",
                },
            ))
            raise

    def _resume_langgraph(self, handle: MissionHandle) -> dict[str, Any]:
        """Resume LangGraph execution from checkpoint."""
        config = {"configurable": {"thread_id": handle.mission_id}}
        current = self._states.get(handle.mission_id, {})
        try:
            result = handle.compiled_graph.invoke(current, config)
            final = dict(result) if result else current
            self._states[handle.mission_id] = final
            success = not final.get("error")
            self._statuses[handle.mission_id] = "completed" if success else "failed"
            return final
        except Exception as exc:
            logger.error("Resume failed for mission %s: %s", handle.mission_id, exc)
            self._statuses[handle.mission_id] = "failed"
            current["error"] = str(exc)
            self._states[handle.mission_id] = current
            return current

    def _execute_fallback(
        self,
        handle: MissionHandle,
        resume_state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Fallback execution when LangGraph is not available.
        Executes nodes in topological order using the scaffold spec.

        This path exists for graph_only simulation and environments
        where LangGraph is not installed.
        """
        state = dict(resume_state or handle.initial_state)
        callables = handle.node_callables or build_standard_node_callables()

        # Execute nodes in scaffold order
        node_order = _resolve_execution_order(handle.graph_spec)

        for node_id in node_order:
            if state.get("completed") or state.get("error"):
                break

            stage_id = str(state.get("phase") or "mission")
            selector_inputs = self._merge_selector_inputs(
                state,
                handle,
                stage_id=stage_id,
                node_id=node_id,
            )
            stage_artifact = selector_artifact_for_stage(
                stage_id=stage_id,
                node_id=node_id,
                selector_inputs=selector_inputs,
            )
            state = _merge_state(
                state,
                {
                    "selector_policy_artifacts": [stage_artifact],
                    "policy_events": [self._selector_policy_event_from_artifact(stage_artifact)],
                },
            )
            if stage_artifact.get("denied"):
                state["error"] = f"Execution selector denied node {node_id}"
                break

            executor = callables.get(node_id)
            if not executor:
                continue

            stage_started_at = datetime.now(timezone.utc).isoformat()
            stage_started = time.monotonic()
            selected_substrate = str(stage_artifact.get("selected_substrate") or ExecutionSubstrate.MISSIONRUNTIME_CUSTOM.value)
            emit(MissionEvent(
                event_type="stage_execution_started",
                mission_id=str(state.get("mission_id", "")),
                workflow_id=str(state.get("workflow_id", "")),
                program_id=str(state.get("program_id", "")),
                node_id=node_id,
                phase=stage_id,
                detail={
                    "stage_id": stage_id,
                    "node_id": node_id,
                    "selected_substrate": selected_substrate,
                    "fallback_substrate": str(stage_artifact.get("fallback_substrate") or ""),
                },
            ))

            update = executor(state)
            if isinstance(update, dict):
                state = _merge_state(state, update)
            duration_ms = (time.monotonic() - stage_started) * 1000.0
            stage_status = "completed" if not state.get("error") else "failed"
            self._append_stage_timing(
                state,
                stage_id=stage_id,
                node_id=node_id,
                selected_substrate=selected_substrate,
                status=stage_status,
                duration_ms=duration_ms,
                started_at=stage_started_at,
            )
            emit(MissionEvent(
                event_type="stage_execution_completed",
                mission_id=str(state.get("mission_id", "")),
                workflow_id=str(state.get("workflow_id", "")),
                program_id=str(state.get("program_id", "")),
                node_id=node_id,
                phase=stage_id,
                detail={
                    "stage_id": stage_id,
                    "node_id": node_id,
                    "selected_substrate": selected_substrate,
                    "duration_ms": round(duration_ms, 2),
                    "status": stage_status,
                },
            ))

        return state

    def _get_handle(self, mission_id: str, tenant_id: UUID) -> MissionHandle:
        handle = self._missions.get((tenant_id, mission_id))
        if not handle:
            raise ValueError(f"Mission {mission_id} not found")
        return handle


# -- Helpers -------------------------------------------------------------------

# Canonical implementations live in praison_topology (topo sort) and
# praison_state (state merge).  Re-exported here so existing callers
# (including tests that import ``_merge_state`` from this module) continue
# to work without changes.
from apps.backend.src.core.praison_topology import resolve_execution_order as _resolve_execution_order  # noqa: E402
_merge_state = merge_state  # re-export from praison_state (imported above)


def _make_minimal_agent_specs() -> dict[str, dict[str, Any]]:
    """Minimal agent specs for graph_only execution."""
    agents = [
        # Governance & coordination
        "GovernanceDirector", "MissionDirector", "PhaseCoordinator",
        # Wave 4 crew agents (parallel from start)
        "SurfaceMapper", "OSINTIntelligenceAgent", "DarkWebIntelAgent", "SecretScannerAgent",
        # Wave 4 content discovery (after phase 1-2)
        "ContentDiscoveryAgent",
        # Wave 4 vulnerability & API testing (after content discovery)
        "VulnerabilityAgent", "APISecurityAgent",
        # Wave 4 aggregation & analysis (final)
        "FaradayCoordinatorAgent",
        # Standard agents (existing)
        "ReconSpecialist", "EvidenceAnalyst",
        "ReportSynthesisAgent", "HandoffLiaison",
    ]
    specs = {}
    for agent_id in agents:
        specs[agent_id] = {
            "node_id": agent_id,
            "node_type": "agent",
            "agent_class": "specialist",
            "risk_profile": "standard",
            "review_policy": "standard",
            "memory_scope": "session",
            "allowed_tools": [],
            "system_prompt": f"Agent {agent_id}",
        }
    # Governance nodes
    for gid in ("GovernanceDirector",):
        specs[gid]["node_type"] = "governance"
        specs[gid]["agent_class"] = "governor"
    specs["MissionDirector"]["node_type"] = "coordinator"
    specs["MissionDirector"]["agent_class"] = "director"
    specs["PhaseCoordinator"]["node_type"] = "coordinator"
    specs["PhaseCoordinator"]["agent_class"] = "coordinator"
    return specs


# -- Module convenience --------------------------------------------------------

_RUNTIME: MissionRuntime | None = None


def get_mission_runtime(checkpointer_dsn: str | None = None) -> MissionRuntime:
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = MissionRuntime(checkpointer_dsn=checkpointer_dsn)
    return _RUNTIME
