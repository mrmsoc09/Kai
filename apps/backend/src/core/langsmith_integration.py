"""
LangSmith Integration Layer for K1 / Kai Platform
====================================================
Canonical integration point between Kai's mission runtime and LangSmith
observability, evaluation, and experiment services.

Architecture doctrine:
  - LangSmith is the QUALITY / OBSERVABILITY plane only
  - Kai remains authoritative for: mission state, governance, artifacts, policy
  - LangSmith owns: traces, spans, experiments, datasets, evaluations
  - EventBus is the internal telemetry plane; LangSmith is the external one
  - Both planes receive events but NEVER depend on each other

Capabilities:
  1. Trace correlation — every LLM/tool/chain call tagged with mission context
  2. Run hierarchy — mission → phase → node → specialist → LLM call
  3. Redaction — secrets, credentials, PII stripped before export
  4. Evaluation datasets — mission outcomes feed evaluation pipelines
  5. Experiments — A/B prompt/tool/strategy comparison runs
  6. Replay/debug — full trace replay for failed missions

Environment:
  LANGSMITH_API_KEY        — API key (required for remote tracing)
  LANGSMITH_PROJECT        — Project name (default: "kai-missions")
  LANGSMITH_ENDPOINT       — API endpoint (default: https://api.smith.langchain.com)
  LANGSMITH_TRACING_V2     — Enable v2 tracing protocol ("true")
  K1_LANGSMITH_ENABLED     — Master switch ("true" / "false", default: "false")
  K1_LANGSMITH_REDACT_MODE — "strict" | "moderate" | "none" (default: "strict")
  K1_LANGSMITH_SAMPLE_RATE — Trace sampling rate 0.0-1.0 (default: 1.0)
"""

from __future__ import annotations

import functools
import logging
import os
import random
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Generator

logger = logging.getLogger(__name__)

# -- LangSmith availability detection -----------------------------------------

try:
    from langsmith import Client as _LangSmithClient
    from langsmith import traceable as _ls_traceable
    from langsmith.run_trees import RunTree as _RunTree

    _LANGSMITH_AVAILABLE = True
except ImportError:
    _LANGSMITH_AVAILABLE = False
    _LangSmithClient = None  # type: ignore[assignment,misc]
    _ls_traceable = None  # type: ignore[assignment]
    _RunTree = None  # type: ignore[assignment]
    logger.info(
        "langsmith package not installed — LangSmith integration disabled. "
        "Install with: pip install 'langsmith>=0.1'"
    )


# -- Configuration -------------------------------------------------------------


@dataclass(frozen=True)
class LangSmithConfig:
    """Immutable configuration for LangSmith integration."""

    enabled: bool = False
    api_key: str = ""
    project: str = "kai-missions"
    endpoint: str = "https://api.smith.langchain.com"
    tracing_v2: bool = True
    redact_mode: str = "strict"  # "strict" | "moderate" | "none"
    sample_rate: float = 1.0  # 0.0 = no traces, 1.0 = all traces
    tags: tuple[str, ...] = ("kai", "k1")

    def is_operational(self) -> bool:
        """Return True if LangSmith is both enabled and has required config."""
        return (
            self.enabled
            and _LANGSMITH_AVAILABLE
            and bool(self.api_key)
        )


def load_langsmith_config() -> LangSmithConfig:
    """Load LangSmith configuration from environment variables."""
    enabled_str = os.getenv("K1_LANGSMITH_ENABLED", "false").lower()
    enabled = enabled_str in ("true", "1", "yes")

    sample_rate_str = os.getenv("K1_LANGSMITH_SAMPLE_RATE", "1.0")
    try:
        sample_rate = max(0.0, min(1.0, float(sample_rate_str)))
    except (ValueError, TypeError):
        sample_rate = 1.0

    return LangSmithConfig(
        enabled=enabled,
        api_key=os.getenv("LANGSMITH_API_KEY", ""),
        project=os.getenv("LANGSMITH_PROJECT", "kai-missions"),
        endpoint=os.getenv(
            "LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"
        ),
        tracing_v2=os.getenv("LANGSMITH_TRACING_V2", "true").lower() == "true",
        redact_mode=os.getenv("K1_LANGSMITH_REDACT_MODE", "strict"),
        sample_rate=sample_rate,
    )


# -- Trace naming conventions -------------------------------------------------


def mission_run_name(mission_id: str, mission_name: str = "") -> str:
    """Canonical LangSmith run name for a mission."""
    label = mission_name or mission_id[:12]
    return f"mission:{label}"


def phase_run_name(phase: str) -> str:
    """Canonical LangSmith run name for a mission phase."""
    return f"phase:{phase}"


def node_run_name(node_id: str, agent_id: str = "") -> str:
    """Canonical LangSmith run name for a graph node execution."""
    if agent_id:
        return f"node:{node_id}[{agent_id}]"
    return f"node:{node_id}"


def specialist_run_name(specialist_type: str, agent_id: str = "") -> str:
    """Canonical LangSmith run name for a DeepAgent specialist."""
    if agent_id:
        return f"specialist:{specialist_type}[{agent_id}]"
    return f"specialist:{specialist_type}"


def llm_run_name(model_name: str = "", provider: str = "") -> str:
    """Canonical LangSmith run name for an LLM invocation."""
    parts = ["llm"]
    if provider:
        parts.append(provider)
    if model_name:
        parts.append(model_name)
    return ":".join(parts)


def tool_run_name(tool_name: str, band: str = "") -> str:
    """Canonical LangSmith run name for a tool invocation."""
    if band:
        return f"tool:{tool_name}[band_{band}]"
    return f"tool:{tool_name}"


# -- Trace correlation context -------------------------------------------------


@dataclass
class TraceCorrelation:
    """
    Carries LangSmith trace correlation through Kai's execution stack.

    Maps Kai's existing correlation IDs (mission_id, workflow_id, program_id)
    to LangSmith's run hierarchy (parent_run_id, run_id, trace_id).
    """

    # Kai correlation IDs
    mission_id: str = ""
    workflow_id: str = ""
    program_id: str = ""
    phase: str = ""
    node_id: str = ""
    agent_id: str = ""

    # LangSmith run hierarchy
    trace_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    parent_run_id: str = ""
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Metadata carried on every span
    execution_mode: str = "live"
    specialist_type: str = ""

    def to_metadata(self) -> dict[str, Any]:
        """Build LangSmith metadata dict from correlation context."""
        meta: dict[str, str] = {
            "kai_mission_id": self.mission_id,
            "kai_workflow_id": self.workflow_id,
            "kai_program_id": self.program_id,
            "kai_phase": self.phase,
            "kai_node_id": self.node_id,
            "kai_agent_id": self.agent_id,
            "kai_execution_mode": self.execution_mode,
        }
        if self.specialist_type:
            meta["kai_specialist_type"] = self.specialist_type
        return {k: v for k, v in meta.items() if v}

    def to_tags(self) -> list[str]:
        """Build LangSmith tags list from correlation context."""
        tags = ["kai"]
        if self.mission_id:
            tags.append(f"mission:{self.mission_id[:12]}")
        if self.phase:
            tags.append(f"phase:{self.phase}")
        if self.execution_mode:
            tags.append(f"mode:{self.execution_mode}")
        if self.specialist_type:
            tags.append(f"specialist:{self.specialist_type}")
        return tags

    def child(
        self,
        *,
        node_id: str = "",
        agent_id: str = "",
        phase: str = "",
        specialist_type: str = "",
    ) -> TraceCorrelation:
        """Create a child correlation preserving parent context."""
        return TraceCorrelation(
            mission_id=self.mission_id,
            workflow_id=self.workflow_id,
            program_id=self.program_id,
            phase=phase or self.phase,
            node_id=node_id or self.node_id,
            agent_id=agent_id or self.agent_id,
            trace_id=self.trace_id,
            parent_run_id=self.run_id,
            run_id=str(uuid.uuid4()),
            execution_mode=self.execution_mode,
            specialist_type=specialist_type or self.specialist_type,
        )


# -- LangSmithBridge -----------------------------------------------------------


class LangSmithBridge:
    """
    Bridge between Kai's mission runtime and LangSmith services.

    Responsibilities:
    1. Client lifecycle management (lazy init, connection validation)
    2. Run creation / update with Kai correlation metadata
    3. Trace sampling enforcement
    4. Redaction pipeline coordination (delegates to langsmith_redaction)
    5. EventBus subscriber that forwards selected events to LangSmith
    6. Evaluation dataset management (delegates to langsmith_evaluations)

    Thread-safe: the underlying LangSmith Client handles thread safety.
    The bridge itself is stateless except for config and client reference.
    """

    def __init__(self, config: LangSmithConfig | None = None) -> None:
        self._config = config or load_langsmith_config()
        self._client: _LangSmithClient | None = None  # type: ignore[assignment]
        self._initialized = False

    @property
    def config(self) -> LangSmithConfig:
        return self._config

    @property
    def is_operational(self) -> bool:
        """True if LangSmith is enabled, available, and configured."""
        return self._config.is_operational()

    # -- Client lifecycle ------------------------------------------------------

    def _ensure_client(self) -> _LangSmithClient | None:  # type: ignore[name-defined]
        """Lazily initialize the LangSmith client."""
        if not self.is_operational:
            return None

        if self._client is None:
            try:
                self._client = _LangSmithClient(
                    api_key=self._config.api_key,
                    api_url=self._config.endpoint,
                )
                self._initialized = True
                logger.info(
                    "LangSmithBridge: client initialized (project=%s, endpoint=%s)",
                    self._config.project,
                    self._config.endpoint,
                )
            except Exception as exc:
                logger.warning(
                    "LangSmithBridge: client initialization failed: %s", exc
                )
                self._client = None

        return self._client

    def get_client(self) -> _LangSmithClient | None:  # type: ignore[name-defined]
        """Return the LangSmith client (may be None if not operational)."""
        return self._ensure_client()

    # -- Sampling --------------------------------------------------------------

    def should_trace(self) -> bool:
        """Determine if this execution should be traced based on sample rate."""
        if not self.is_operational:
            return False
        if self._config.sample_rate >= 1.0:
            return True
        if self._config.sample_rate <= 0.0:
            return False
        return random.random() < self._config.sample_rate

    # -- Run management --------------------------------------------------------

    def create_run(
        self,
        name: str,
        run_type: str = "chain",
        correlation: TraceCorrelation | None = None,
        inputs: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> str | None:
        """
        Create a LangSmith run with Kai correlation metadata.

        Args:
            name: Run name (use naming convention helpers).
            run_type: "chain" | "llm" | "tool" | "retriever".
            correlation: Trace correlation context.
            inputs: Run inputs (will be redacted).
            extra: Additional metadata.

        Returns:
            Run ID string, or None if tracing is disabled/failed.
        """
        if not self.should_trace():
            return None

        client = self._ensure_client()
        if client is None:
            return None

        # Build metadata
        metadata = {}
        tags = list(self._config.tags)
        parent_run_id = None
        run_id = str(uuid.uuid4())

        if correlation:
            metadata.update(correlation.to_metadata())
            tags.extend(correlation.to_tags())
            parent_run_id = correlation.parent_run_id or None
            run_id = correlation.run_id

        if extra:
            metadata.update(extra)

        # Apply redaction to inputs
        safe_inputs = self._redact(inputs or {})

        try:
            client.create_run(
                name=name,
                run_type=run_type,
                run_id=run_id,
                parent_run_id=parent_run_id,
                project_name=self._config.project,
                inputs=safe_inputs,
                extra={"metadata": metadata},
                tags=tags,
                start_time=datetime.now(timezone.utc),
            )
            return run_id
        except Exception as exc:
            logger.warning("LangSmithBridge: create_run failed: %s", exc)
            return None

    def end_run(
        self,
        run_id: str,
        outputs: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """
        End a LangSmith run with outputs or error.

        Args:
            run_id: The run ID returned by create_run.
            outputs: Run outputs (will be redacted).
            error: Error string if the run failed.
        """
        if not self.is_operational:
            return

        client = self._ensure_client()
        if client is None:
            return

        safe_outputs = self._redact(outputs or {})

        try:
            client.update_run(
                run_id=run_id,
                outputs=safe_outputs,
                error=error,
                end_time=datetime.now(timezone.utc),
            )
        except Exception as exc:
            logger.warning("LangSmithBridge: end_run failed for %s: %s", run_id, exc)

    # -- Context manager for run lifecycle ------------------------------------

    @contextmanager
    def trace_run(
        self,
        name: str,
        run_type: str = "chain",
        correlation: TraceCorrelation | None = None,
        inputs: dict[str, Any] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> Generator[str | None, None, None]:
        """
        Context manager for LangSmith run lifecycle.

        Usage::

            with bridge.trace_run("mission:recon", correlation=corr) as run_id:
                # ... do work ...
                pass
            # run is automatically ended
        """
        run_id = self.create_run(
            name=name,
            run_type=run_type,
            correlation=correlation,
            inputs=inputs,
            extra=extra,
        )
        error_msg: str | None = None
        try:
            yield run_id
        except Exception as exc:
            error_msg = str(exc)
            raise
        finally:
            if run_id:
                self.end_run(run_id, error=error_msg)

    # -- Traceable decorator ---------------------------------------------------

    def traceable(
        self,
        name: str | None = None,
        run_type: str = "chain",
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
    ) -> Callable:
        """
        Decorator that wraps a function with LangSmith tracing.

        When LangSmith is not operational, returns the function unchanged.

        Args:
            name: Run name (defaults to function name).
            run_type: "chain" | "llm" | "tool".
            metadata: Additional metadata.
            tags: Additional tags.

        Returns:
            Decorated function (or original if tracing disabled).
        """
        def decorator(fn: Callable) -> Callable:
            if not self.is_operational or _ls_traceable is None:
                return fn

            run_name = name or fn.__name__
            all_tags = list(self._config.tags) + (tags or [])
            all_metadata = dict(metadata or {})

            return _ls_traceable(
                name=run_name,
                run_type=run_type,
                metadata=all_metadata,
                tags=all_tags,
                project_name=self._config.project,
            )(fn)

        return decorator

    # -- EventBus integration --------------------------------------------------

    def create_event_subscriber(self) -> Callable:
        """
        Return an EventBus subscriber callback that forwards events to LangSmith.

        The subscriber converts MissionEvents to LangSmith run updates,
        mapping event_type to run operations:
          - mission_started → create top-level chain run
          - node_entered → create child chain run
          - node_completed → end chain run
          - llm_invocation_started → create child llm run
          - llm_invocation_completed → end llm run
          - tool_invocation_started → create child tool run
          - tool_invocation_completed → end tool run
        """
        # Track active runs by event correlation
        active_runs: dict[str, str] = {}  # key → run_id

        def _subscriber(event: Any) -> None:
            if not self.should_trace():
                return

            event_type = getattr(event, "event_type", "")
            mission_id = getattr(event, "mission_id", "")
            node_id = getattr(event, "node_id", "")
            agent_id = getattr(event, "agent_id", "")
            detail = getattr(event, "detail", {})

            if event_type == "mission_started":
                correlation = TraceCorrelation(
                    mission_id=mission_id,
                    workflow_id=getattr(event, "workflow_id", ""),
                    program_id=getattr(event, "program_id", ""),
                )
                run_id = self.create_run(
                    name=mission_run_name(mission_id),
                    run_type="chain",
                    correlation=correlation,
                    inputs={"mission_id": mission_id, **detail},
                )
                if run_id:
                    active_runs[f"mission:{mission_id}"] = run_id

            elif event_type == "mission_completed":
                key = f"mission:{mission_id}"
                run_id = active_runs.pop(key, None)
                if run_id:
                    self.end_run(
                        run_id,
                        outputs=detail,
                        error=detail.get("error"),
                    )

            elif event_type == "node_entered":
                parent_key = f"mission:{mission_id}"
                parent_run_id = active_runs.get(parent_key, "")
                correlation = TraceCorrelation(
                    mission_id=mission_id,
                    node_id=node_id,
                    agent_id=agent_id,
                    parent_run_id=parent_run_id,
                    phase=getattr(event, "phase", ""),
                )
                run_id = self.create_run(
                    name=node_run_name(node_id, agent_id),
                    run_type="chain",
                    correlation=correlation,
                    inputs=detail,
                )
                if run_id:
                    active_runs[f"node:{mission_id}:{node_id}"] = run_id

            elif event_type == "node_completed":
                key = f"node:{mission_id}:{node_id}"
                run_id = active_runs.pop(key, None)
                if run_id:
                    self.end_run(run_id, outputs=detail)

            elif event_type == "node_failed":
                key = f"node:{mission_id}:{node_id}"
                run_id = active_runs.pop(key, None)
                if run_id:
                    self.end_run(
                        run_id,
                        error=detail.get("error", "unknown error"),
                    )

        return _subscriber

    # -- Redaction pipeline ----------------------------------------------------

    def _redact(self, data: dict[str, Any]) -> dict[str, Any]:
        """Apply redaction policy to data before sending to LangSmith."""
        if self._config.redact_mode == "none":
            return data

        try:
            from apps.backend.src.core.langsmith_redaction import redact_for_langsmith

            return redact_for_langsmith(data, mode=self._config.redact_mode)
        except ImportError:
            # Redaction module not available — apply basic redaction
            return _basic_redact(data)

    # -- Mission trace helpers -------------------------------------------------

    def start_mission_trace(
        self,
        mission_id: str,
        workflow_id: str,
        program_id: str,
        execution_mode: str = "live",
        mission_name: str = "",
    ) -> TraceCorrelation | None:
        """
        Create a top-level trace for a mission execution.

        Returns a TraceCorrelation that should be passed down through
        the execution stack, or None if tracing is disabled.
        """
        if not self.should_trace():
            return None

        correlation = TraceCorrelation(
            mission_id=mission_id,
            workflow_id=workflow_id,
            program_id=program_id,
            execution_mode=execution_mode,
        )

        run_id = self.create_run(
            name=mission_run_name(mission_id, mission_name),
            run_type="chain",
            correlation=correlation,
            inputs={
                "mission_id": mission_id,
                "workflow_id": workflow_id,
                "program_id": program_id,
                "execution_mode": execution_mode,
            },
        )

        if run_id:
            correlation = TraceCorrelation(
                mission_id=mission_id,
                workflow_id=workflow_id,
                program_id=program_id,
                execution_mode=execution_mode,
                trace_id=correlation.trace_id,
                run_id=run_id,
            )
            return correlation

        return None

    def end_mission_trace(
        self,
        correlation: TraceCorrelation,
        success: bool = True,
        error: str = "",
        summary: dict[str, Any] | None = None,
    ) -> None:
        """End a mission-level trace."""
        outputs: dict[str, Any] = {"success": success}
        if summary:
            outputs.update(summary)
        self.end_run(
            correlation.run_id,
            outputs=outputs,
            error=error if not success else None,
        )

    def trace_specialist(
        self,
        parent_correlation: TraceCorrelation | None,
        specialist_type: str,
        agent_id: str,
        task: str,
    ) -> TraceCorrelation | None:
        """
        Create a trace for a DeepAgent specialist execution.

        Returns child TraceCorrelation, or None if tracing disabled.
        """
        if parent_correlation is None or not self.should_trace():
            return None

        child = parent_correlation.child(
            agent_id=agent_id,
            specialist_type=specialist_type,
        )

        run_id = self.create_run(
            name=specialist_run_name(specialist_type, agent_id),
            run_type="chain",
            correlation=child,
            inputs={"task": task[:500], "specialist_type": specialist_type},
        )

        if run_id:
            return TraceCorrelation(
                mission_id=child.mission_id,
                workflow_id=child.workflow_id,
                program_id=child.program_id,
                phase=child.phase,
                node_id=child.node_id,
                agent_id=agent_id,
                trace_id=child.trace_id,
                parent_run_id=child.parent_run_id,
                run_id=run_id,
                execution_mode=child.execution_mode,
                specialist_type=specialist_type,
            )
        return None

    def end_specialist_trace(
        self,
        correlation: TraceCorrelation,
        result: dict[str, Any] | None = None,
        error: str = "",
    ) -> None:
        """End a specialist-level trace."""
        self.end_run(
            correlation.run_id,
            outputs=result or {},
            error=error or None,
        )

    # -- LangChain callback integration ----------------------------------------

    def get_langchain_callbacks(
        self, correlation: TraceCorrelation | None = None
    ) -> list[Any]:
        """
        Return LangChain callback handlers that forward to LangSmith.

        When LangSmith is operational, returns a LangChainTracer configured
        with the correct project and run context. When not, returns empty list.
        """
        if not self.is_operational or correlation is None:
            return []

        try:
            from langsmith import LangChainTracer

            tracer = LangChainTracer(
                project_name=self._config.project,
                client=self._ensure_client(),
            )
            return [tracer]
        except (ImportError, Exception) as exc:
            logger.debug("LangSmithBridge: LangChainTracer unavailable: %s", exc)
            return []


# -- Basic redaction fallback --------------------------------------------------


_REDACT_KEYS = frozenset({
    "api_key", "apikey", "api_secret", "secret", "password", "passwd",
    "token", "auth_token", "access_token", "refresh_token", "bearer",
    "credential", "credentials", "private_key", "secret_key",
    "vault_token", "pgp_key", "ssh_key", "aws_secret",
})


def _basic_redact(data: dict[str, Any], _depth: int = 0) -> dict[str, Any]:
    """
    Basic key-based redaction when the full redaction module is unavailable.

    Recursively walks dicts and redacts values whose keys match known
    secret patterns. Maximum recursion depth of 10 to prevent stack overflow.
    """
    if _depth > 10:
        return data

    result: dict[str, Any] = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(secret in key_lower for secret in _REDACT_KEYS):
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = _basic_redact(value, _depth + 1)
        elif isinstance(value, list):
            result[key] = [
                _basic_redact(item, _depth + 1)
                if isinstance(item, dict)
                else item
                for item in value
            ]
        else:
            result[key] = value
    return result


# -- Module singleton ----------------------------------------------------------

_bridge: LangSmithBridge | None = None


def get_langsmith_bridge() -> LangSmithBridge:
    """
    Return the module-level LangSmithBridge singleton.

    Auto-initializes with environment config on first call.
    For explicit configuration, call initialize_langsmith_bridge() first.
    """
    global _bridge
    if _bridge is None:
        _bridge = LangSmithBridge()
    return _bridge


def initialize_langsmith_bridge(
    config: LangSmithConfig | None = None,
) -> LangSmithBridge:
    """
    Create (or replace) the module-level LangSmithBridge singleton.

    Should be called once during application startup, typically inside the
    FastAPI lifespan manager.

    Args:
        config: Optional explicit configuration. If None, loads from env.

    Returns:
        The newly created LangSmithBridge singleton.
    """
    global _bridge
    cfg = config or load_langsmith_config()
    _bridge = LangSmithBridge(config=cfg)
    logger.info(
        "LangSmithBridge initialized (enabled=%s, project=%s, operational=%s)",
        cfg.enabled,
        cfg.project,
        _bridge.is_operational,
    )
    return _bridge


def is_langsmith_available() -> bool:
    """Return True if the langsmith package is importable."""
    return _LANGSMITH_AVAILABLE


def is_langsmith_operational() -> bool:
    """Return True if LangSmith is both available and properly configured."""
    return get_langsmith_bridge().is_operational
