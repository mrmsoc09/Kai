"""
LangChain Tool Registry for K1 / Kai Platform
================================================
Converts Kai's ToolCatalogEntry objects into LangChain StructuredTool wrappers
with full governance enforcement at every invocation boundary.

Governance pipeline for each tool call:
  1. Execution-mode fast-path  (graph_only / tool_mock)
  2. Allowed-tool-ids allowlist check
  3. Safety band enforcement   (band_3 always denied)
  4. Scope validation          (scope_validator from authorization_gate)
  5. Telemetry emission        (MissionEvent via praison_execution_events)
  6. Dispatch signal           (real execution deferred to Celery worker)

IMPORTANT: This layer does NOT run tools directly. Real execution goes through
the Celery worker pipeline (tool_runner.enqueue → worker run_tool_task). The
_run / _arun methods validate, emit telemetry, and return a structured dispatch
signal dict that callers use to trigger the async worker path.

Phase-to-category mapping drives get_tools_for_phase(); categories match the
``category`` field in tool_registry.yaml.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional LangChain import — degrade gracefully if not installed
# ---------------------------------------------------------------------------
try:
    from langchain_core.tools import BaseTool
    from langchain_core.callbacks import (
        AsyncCallbackManagerForToolRun,
        CallbackManagerForToolRun,
    )
    from pydantic import BaseModel, ConfigDict, Field

    _LANGCHAIN_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LANGCHAIN_AVAILABLE = False
    BaseTool = object  # type: ignore[assignment,misc]
    logger.warning(
        "langchain_core is not installed — K1GovernedTool and K1LangChainToolRegistry "
        "will not be available. Install langchain-core>=0.1 to enable LangChain integration."
    )


# ---------------------------------------------------------------------------
# Internal platform imports (all lazy-safe: no circular risk at module level)
# ---------------------------------------------------------------------------
from apps.backend.src.core.tool_registry_catalog import ToolCatalogEntry, get_tool_catalog
from apps.backend.src.core.authorization_gate import (
    AuthorizationGateError,
    scope_validator,
)
from apps.backend.src.core.praison_execution_events import (
    MissionEvent,
    emit,
)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class ToolNotPermittedError(PermissionError):
    """Raised when a tool is not in the agent's allowed_tool_ids allowlist."""


class ToolBandViolationError(PermissionError):
    """Raised when a tool's safety_classification band is denied in this layer (band_3)."""


class ToolScopeViolationError(PermissionError):
    """Raised when the target fails scope validation via scope_validator."""


class ToolWrapperBypassError(PermissionError):
    """Raised when a caller attempts to bypass wrapper-only execution policy."""


# Explicitly blocked argument keys that imply direct substrate execution
_BYPASS_ARG_KEYS: frozenset[str] = frozenset({
    "bypass_wrappers",
    "bypass_governance",
    "direct_execute",
    "raw_command",
    "shell_command",
    "subprocess_cmd",
    "execution_backend",
    "execution_substrate",
})


def _contains_wrapper_bypass(args: dict[str, Any]) -> bool:
    if not isinstance(args, dict):
        return False
    for key in _BYPASS_ARG_KEYS:
        if key not in args:
            continue
        value = args.get(key)
        if value in (None, False, "", 0):
            continue
        if key in {"execution_backend", "execution_substrate"}:
            normalized = str(value).strip().lower()
            if normalized in {"wrapper", "celery", "celery_dispatch", "governed"}:
                continue
        return True
    return False


# ---------------------------------------------------------------------------
# K1ToolContext — immutable per-invocation governance context
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class K1ToolContext:
    """
    Immutable governance context bound to a single agent for the duration of a
    mission node execution.  Passed to every K1GovernedTool at construction time.

    execution_mode values:
      "live"       — real tool dispatch through Celery worker pipeline
      "graph_only" — no execution; returns structural mock immediately
      "tool_mock"  — returns formatted mock output suitable for LLM consumption
    """

    mission_id: str
    workflow_id: str
    program_id: str
    agent_id: str
    phase: str
    execution_mode: str  # "live" | "graph_only" | "tool_mock"
    allowed_tool_ids: frozenset[str]  # tools explicitly allowed for this agent
    node_id: str = ""
    stage_id: str = ""
    selected_substrate: str = ""
    risk_band: str = ""
    tenant_id: str = ""


# ---------------------------------------------------------------------------
# Phase → tool category mapping
# ---------------------------------------------------------------------------

_PHASE_TOOL_CATEGORIES: dict[str, frozenset[str]] = {
    # Generic spec values (band_0/band_1 passive and active recon)
    "recon": frozenset(
        {
            "recon",
            "osint",
            "passive",
            # Actual tool_registry.yaml categories
            "recon_asset_discovery",
            "intelligence_osint",
            "secret_leak_detection",
        }
    ),
    "scan": frozenset(
        {
            "scan",
            "recon",
            "active",
            # Actual tool_registry.yaml categories
            "network_service_scanning",
            "http_live_host",
            "crawling_url_discovery",
            "fuzzing_content_discovery",
            "vulnerability_scanning",
        }
    ),
    "exploit": frozenset(
        {
            "exploit",
            "active",
            # Actual tool_registry.yaml categories
            "vulnerability_scanning",
        }
    ),
    "report": frozenset(
        {
            "report",
            "analysis",
            # Actual tool_registry.yaml categories
            "validation_support",
        }
    ),
    "governance": frozenset(
        {
            "governance",
            # Actual tool_registry.yaml categories
            "manual_hil_integrations",
        }
    ),
}

# Default allowed bands when no override is provided
_DEFAULT_ALLOWED_BANDS: frozenset[str] = frozenset({"band_0", "band_1"})

# band_3 is unconditionally denied at the LangChain layer
_DENIED_BANDS: frozenset[str] = frozenset({"band_3"})

# ---------------------------------------------------------------------------
# Safety classification normalisation
# ---------------------------------------------------------------------------
# The tool_registry.yaml stores descriptive classification names (e.g. "passive",
# "active", "intrusive", "manual_only") rather than the policy band labels used
# by this module's API surface.  This mapping normalises catalog values to the
# canonical band names used by the governance layer so callers always work with
# a uniform vocabulary.
#
# Unmapped values default to "band_2" (requires approval) rather than silently
# being allowed or denied, enforcing an explicit safe default for unknown tools.
_CLASSIFICATION_TO_BAND: dict[str, str] = {
    # Band 0 — passive / benign, always autonomous
    "passive": "band_0",
    "safe": "band_0",
    # Band 1 — active but low-risk, autonomous within scope
    "active": "band_1",
    # Band 2 — state-modifying / alert-tripping, requires approval
    "intrusive": "band_2",
    # Band 3 — never autonomous in LangChain layer
    "manual_only": "band_3",
    # Explicit band labels pass through unchanged (forward compat)
    "band_0": "band_0",
    "band_1": "band_1",
    "band_2": "band_2",
    "band_3": "band_3",
}
_UNKNOWN_CLASSIFICATION_DEFAULT_BAND = "band_2"


def _resolve_band(safety_classification: str) -> str:
    """
    Normalise a catalog safety_classification string to a policy band label.

    Unknown classifications map to band_2 (approval required) rather than
    defaulting to permissive, following the deny-unknown security principle.
    """
    return _CLASSIFICATION_TO_BAND.get(
        (safety_classification or "").strip().lower(),
        _UNKNOWN_CLASSIFICATION_DEFAULT_BAND,
    )


# ---------------------------------------------------------------------------
# Telemetry event factories
# ---------------------------------------------------------------------------


def _tool_invocation_started_event(
    context: K1ToolContext,
    tool_id: str,
    target: str,
    tool_execution_id: str = "",
) -> MissionEvent:
    """Create a tool_invocation_started MissionEvent from the current K1ToolContext."""
    return MissionEvent(
        event_type="tool_invocation_started",
        mission_id=context.mission_id,
        workflow_id=context.workflow_id,
        program_id=context.program_id,
        agent_id=context.agent_id,
        node_id="",  # node_id is not available at the tool invocation level
        phase=context.phase,
        detail={
            "tool_id": tool_id,
            "target": target,
            "execution_mode": context.execution_mode,
            "tool_execution_id": tool_execution_id,
            "node_id": context.node_id,
            "stage_id": context.stage_id,
            "selected_substrate": context.selected_substrate,
            "risk_band": context.risk_band,
            "tenant_id": context.tenant_id,
        },
    )


def _tool_invocation_completed_event(
    context: K1ToolContext,
    tool_id: str,
    status: str,
    tool_execution_id: str = "",
    duration_ms: float = 0.0,
    estimated_tokens: int = 0,
    estimated_cost_cents: float = 0.0,
    retry_count: int = 0,
) -> MissionEvent:
    """Create a tool_invocation_completed MissionEvent from the current K1ToolContext."""
    return MissionEvent(
        event_type="tool_invocation_completed",
        mission_id=context.mission_id,
        workflow_id=context.workflow_id,
        program_id=context.program_id,
        agent_id=context.agent_id,
        node_id="",
        phase=context.phase,
        detail={
            "tool_id": tool_id,
            "status": status,
            "execution_mode": context.execution_mode,
            "tool_execution_id": tool_execution_id,
            "duration_ms": round(float(duration_ms), 2),
            "estimated_tokens": int(estimated_tokens),
            "estimated_cost_cents": round(float(estimated_cost_cents), 6),
            "retry_count": int(retry_count),
            "node_id": context.node_id,
            "stage_id": context.stage_id,
            "selected_substrate": context.selected_substrate,
            "risk_band": context.risk_band,
            "tenant_id": context.tenant_id,
        },
    )


def _extract_dispatch_usage(args: dict[str, Any]) -> tuple[int, float, int]:
    """
    Extract optional usage/cost/retry metadata from dispatch args.

    Keys are best-effort and remain backward-compatible with existing callers.
    """
    if not isinstance(args, dict):
        return 0, 0.0, 0

    estimated_tokens = 0
    estimated_cost_cents = 0.0
    retry_count = 0

    for token_key in ("estimated_tokens", "total_tokens", "tokens"):
        try:
            estimated_tokens = int(args.get(token_key, 0) or 0)
        except (TypeError, ValueError):
            estimated_tokens = 0
        if estimated_tokens > 0:
            break

    try:
        token_usage = args.get("token_usage", {})
        if estimated_tokens <= 0 and isinstance(token_usage, dict):
            estimated_tokens = int(
                token_usage.get("total_tokens")
                or token_usage.get("total")
                or token_usage.get("tokens")
                or 0
            )
    except (TypeError, ValueError):
        estimated_tokens = 0

    for cost_key in ("estimated_cost_cents", "cost_cents"):
        try:
            estimated_cost_cents = float(args.get(cost_key, 0.0) or 0.0)
        except (TypeError, ValueError):
            estimated_cost_cents = 0.0
        if estimated_cost_cents > 0.0:
            break

    for retry_key in ("retry_count", "retries", "attempt"):
        try:
            retry_count = int(args.get(retry_key, 0) or 0)
        except (TypeError, ValueError):
            retry_count = 0
        if retry_count > 0:
            break

    return max(0, estimated_tokens), max(0.0, estimated_cost_cents), max(0, retry_count)


# ---------------------------------------------------------------------------
# K1GovernedToolInput — Pydantic v2 input schema
# ---------------------------------------------------------------------------

if _LANGCHAIN_AVAILABLE:

    class K1GovernedToolInput(BaseModel):
        """
        Input schema for all K1-governed LangChain tools.

        'target'  — the host / domain / IP the tool will act against.
        'args'    — tool-specific key/value arguments forwarded to the worker.
        """

        model_config = ConfigDict(extra="forbid")

        target: str = Field(description="Target host/domain/IP to run tool against")
        args: dict[str, Any] = Field(
            default_factory=dict,
            description="Tool-specific arguments forwarded to the Celery worker",
        )

    # -----------------------------------------------------------------------
    # K1GovernedTool — governed LangChain BaseTool wrapper
    # -----------------------------------------------------------------------

    class K1GovernedTool(BaseTool):
        """
        LangChain BaseTool wrapper that enforces Kai's full governance stack
        before signalling that a tool should be dispatched.

        Governance checks (in order):
          1. execution_mode fast-path  (graph_only returns immediately)
          2. Allowed-tool-ids check    (ToolNotPermittedError if not in set)
          3. Safety band check         (ToolBandViolationError for band_3)
          4. Scope validation          (ToolScopeViolationError on failure)
          5. Telemetry emitted and dispatch signal returned

        Real execution is deferred — the return value instructs callers to
        enqueue via tool_runner/Celery, never executed inline.
        """

        # --- LangChain BaseTool required fields ---
        name: str
        description: str
        args_schema: type = K1GovernedToolInput  # type: ignore[assignment]

        # --- K1-specific fields stored as class-level attributes ---
        # Pydantic v2 + LangChain: use model_config to allow arbitrary types
        model_config = ConfigDict(arbitrary_types_allowed=True)

        catalog_entry: ToolCatalogEntry
        context: K1ToolContext

        # ------------------------------------------------------------------
        # Internal governance logic
        # ------------------------------------------------------------------

        def _enforce_governance(self, target: str, args: dict[str, Any]) -> str | None:
            """
            Run all governance checks.  Returns a pre-built result string for
            fast-path modes (graph_only / tool_mock), or None to proceed to
            the dispatch path.

            Raises ToolNotPermittedError, ToolBandViolationError, or
            ToolScopeViolationError on policy violations.
            """
            # Step 1: graph_only — structural representation only, no execution
            if self.context.execution_mode == "graph_only":
                return json.dumps(
                    {
                        "status": "graph_only",
                        "tool_id": self.name,
                        "target": target,
                        "args": args,
                        "note": "graph_only mode — tool not executed",
                    }
                )

            # Step 1b: explicit wrapper-bypass attempts are blocked.
            if _contains_wrapper_bypass(args):
                raise ToolWrapperBypassError(
                    "Tool invocation attempted direct substrate execution. "
                    "Wrapper-only execution is mandatory."
                )

            # Step 2: allowlist check
            if self.context.allowed_tool_ids and self.name not in self.context.allowed_tool_ids:
                raise ToolNotPermittedError(
                    f"Tool '{self.name}' is not in the allowed_tool_ids for agent "
                    f"'{self.context.agent_id}' in mission '{self.context.mission_id}'"
                )

            # Step 3: band check — band_3 unconditionally denied
            resolved_band = _resolve_band(self.catalog_entry.safety_classification)
            if resolved_band in _DENIED_BANDS:
                raise ToolBandViolationError(
                    f"Tool '{self.name}' has safety_classification="
                    f"'{self.catalog_entry.safety_classification}' (resolved band: "
                    f"'{resolved_band}') which is denied in the LangChain orchestration "
                    "layer (band_3 requires direct human approval)"
                )

            # Step 4: tool_mock — return after band check (mock honours band policy)
            if self.context.execution_mode == "tool_mock":
                return json.dumps(
                    {
                        "status": "mock",
                        "tool_id": self.name,
                        "result": "mock_output",
                    }
                )

            # Step 5: scope validation
            try:
                scope_ok = scope_validator(
                    target,
                    self.context.program_id,
                    self.catalog_entry.name,
                    self.context.workflow_id or None,
                )
            except AuthorizationGateError as exc:
                raise ToolScopeViolationError(
                    f"Scope validation raised AuthorizationGateError for tool "
                    f"'{self.name}' target '{target}': {exc}"
                ) from exc

            if not scope_ok:
                raise ToolScopeViolationError(
                    f"Target '{target}' is outside authorized scope for tool "
                    f"'{self.name}' (program_id='{self.context.program_id}', "
                    f"workflow_id='{self.context.workflow_id}')"
                )

            # All checks passed — signal live dispatch
            return None

        # ------------------------------------------------------------------
        # Sync _run
        # ------------------------------------------------------------------

        def _run(
            self,
            target: str,
            args: dict[str, Any] | None = None,
            run_manager: CallbackManagerForToolRun | None = None,
        ) -> str:
            """
            Validate governance and return a dispatch signal JSON string.

            In live mode returns:
              {"status": "dispatched", "tool_id": ..., "target": ...,
               "args": ..., "validation": "passed"}

            In tool_mock mode returns:
              {"status": "mock", "tool_id": ..., "result": "mock_output"}

            In graph_only mode returns a graph_only sentinel without emitting
            telemetry (no real work is implied).
            """
            resolved_args = args or {}
            dispatch_started = time.monotonic()

            fast_path_result = self._enforce_governance(target, resolved_args)
            if fast_path_result is not None:
                return fast_path_result

            # Telemetry: invocation started
            tool_execution_id = str(uuid.uuid4())
            emit(_tool_invocation_started_event(
                self.context, self.name, target, tool_execution_id=tool_execution_id
            ))

            # Build dispatch signal — real execution goes through Celery worker
            result_payload: dict[str, Any] = {
                "status": "dispatched",
                "tool_id": self.name,
                "target": target,
                "args": resolved_args,
                "validation": "passed",
            }
            result_str = json.dumps(result_payload)
            duration_ms = (time.monotonic() - dispatch_started) * 1000.0
            estimated_tokens, estimated_cost_cents, retry_count = _extract_dispatch_usage(resolved_args)

            # Telemetry: invocation completed
            emit(_tool_invocation_completed_event(
                self.context,
                self.name,
                "dispatched",
                tool_execution_id=tool_execution_id,
                duration_ms=duration_ms,
                estimated_tokens=estimated_tokens,
                estimated_cost_cents=estimated_cost_cents,
                retry_count=retry_count,
            ))

            return result_str

        # ------------------------------------------------------------------
        # Async _arun
        # ------------------------------------------------------------------

        async def _arun(
            self,
            target: str,
            args: dict[str, Any] | None = None,
            run_manager: AsyncCallbackManagerForToolRun | None = None,
        ) -> str:
            """
            Async counterpart to _run.  Runs governance checks in an executor to
            keep the event loop unblocked for IO-heavy orchestration pipelines.
            """
            resolved_args = args or {}
            dispatch_started = time.monotonic()

            # Fast-path checks are CPU-bound and synchronous — run inline since
            # they are sub-millisecond and safe from blocking concerns.
            fast_path_result = self._enforce_governance(target, resolved_args)
            if fast_path_result is not None:
                return fast_path_result

            # Telemetry: invocation started (synchronous emit is thread-safe)
            tool_execution_id = str(uuid.uuid4())
            emit(_tool_invocation_started_event(
                self.context, self.name, target, tool_execution_id=tool_execution_id
            ))

            result_payload: dict[str, Any] = {
                "status": "dispatched",
                "tool_id": self.name,
                "target": target,
                "args": resolved_args,
                "validation": "passed",
            }
            result_str = json.dumps(result_payload)
            duration_ms = (time.monotonic() - dispatch_started) * 1000.0
            estimated_tokens, estimated_cost_cents, retry_count = _extract_dispatch_usage(resolved_args)

            emit(_tool_invocation_completed_event(
                self.context,
                self.name,
                "dispatched",
                tool_execution_id=tool_execution_id,
                duration_ms=duration_ms,
                estimated_tokens=estimated_tokens,
                estimated_cost_cents=estimated_cost_cents,
                retry_count=retry_count,
            ))

            return result_str

else:
    # Degenerate stubs when langchain_core is absent -------------------------

    class K1GovernedToolInput:  # type: ignore[no-redef]
        """Stub — langchain_core not installed."""

    class K1GovernedTool:  # type: ignore[no-redef]
        """Stub — langchain_core not installed."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError(
                "K1GovernedTool requires langchain_core. "
                "Install langchain-core>=0.1 to enable LangChain integration."
            )


# ---------------------------------------------------------------------------
# K1LangChainToolRegistry
# ---------------------------------------------------------------------------


class K1LangChainToolRegistry:
    """
    Registry that converts Kai ToolCatalogEntry objects into K1GovernedTool
    instances scoped to a specific K1ToolContext.

    Thread-safe: catalog lookups delegate to ToolCatalog which holds its own
    internal lock.  No mutable state is held at the registry level beyond the
    optional event_bus reference.
    """

    def __init__(self, event_bus: Any = None) -> None:
        # event_bus is carried for future pub/sub use; currently telemetry
        # flows through praison_execution_events.emit() module singleton.
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Primary factory
    # ------------------------------------------------------------------

    def get_tools_for_context(
        self,
        context: K1ToolContext,
        include_bands: frozenset[str] | None = None,
    ) -> list[K1GovernedTool]:
        """
        Return a list of K1GovernedTool instances for the given context.

        Only catalog entries whose safety_classification is in include_bands
        are returned.  band_3 tools are excluded unconditionally regardless of
        the include_bands argument.

        Args:
            context: Mission/agent governance context.
            include_bands: Set of band names to include.  Defaults to
                           {"band_0", "band_1"}.

        Returns:
            List of K1GovernedTool instances ready for LangChain consumption.
        """
        if not _LANGCHAIN_AVAILABLE:
            logger.warning("get_tools_for_context: langchain_core unavailable, returning []")
            return []

        effective_bands = (include_bands or _DEFAULT_ALLOWED_BANDS) - _DENIED_BANDS

        catalog = get_tool_catalog()
        all_entries = catalog.entries()

        tools: list[K1GovernedTool] = []
        for entry in all_entries.values():
            # Resolve catalog classification to canonical band label and filter
            resolved_band = _resolve_band(entry.safety_classification)
            if resolved_band not in effective_bands:
                continue
            # Only include enabled entries
            if not entry.enabled_by_default:
                continue
            tool = self._build_governed_tool(entry, context)
            tools.append(tool)

        # Apply explicit allowlist if the context carries one
        return self.filter_by_authority(tools, context.allowed_tool_ids or None)

    def get_tools_for_phase(
        self,
        context: K1ToolContext,
        phase: str,
    ) -> list[K1GovernedTool]:
        """
        Return the phase-appropriate subset of governed tools.

        Uses _PHASE_TOOL_CATEGORIES to map phase name to tool categories.
        Falls back to an empty list for unknown phase names so callers can
        handle unknown phases gracefully rather than receiving all tools.

        Args:
            context: Mission/agent governance context.
            phase: One of "recon" | "scan" | "exploit" | "report" | "governance".

        Returns:
            List of K1GovernedTool instances whose catalog category matches the
            phase and whose band is within the default allowed set.
        """
        if not _LANGCHAIN_AVAILABLE:
            logger.warning("get_tools_for_phase: langchain_core unavailable, returning []")
            return []

        allowed_categories = _PHASE_TOOL_CATEGORIES.get(phase)
        if allowed_categories is None:
            logger.warning(
                "get_tools_for_phase: unknown phase '%s' — known phases: %s",
                phase,
                sorted(_PHASE_TOOL_CATEGORIES.keys()),
            )
            return []

        all_tools = self.get_tools_for_context(context)
        return [t for t in all_tools if t.catalog_entry.category in allowed_categories]

    # ------------------------------------------------------------------
    # Filtering helpers
    # ------------------------------------------------------------------

    def filter_by_authority(
        self,
        tools: list[K1GovernedTool],
        allowed_tool_ids: frozenset[str] | None,
    ) -> list[K1GovernedTool]:
        """
        If allowed_tool_ids is provided and non-empty, return only tools whose
        name is in that set.  An empty frozenset is treated as "no restriction"
        so that callers can pass context.allowed_tool_ids directly without
        needing to special-case the empty case.

        Args:
            tools: Full candidate tool list.
            allowed_tool_ids: Explicit allowlist, or None / empty to allow all.

        Returns:
            Filtered tool list.
        """
        if not allowed_tool_ids:
            return tools
        return [t for t in tools if t.name in allowed_tool_ids]

    def as_tool_names(self, tools: list[K1GovernedTool]) -> list[str]:
        """Return a sorted list of tool names from a governed tool list."""
        return sorted(t.name for t in tools)

    # ------------------------------------------------------------------
    # Internal builder
    # ------------------------------------------------------------------

    def _build_governed_tool(
        self,
        entry: ToolCatalogEntry,
        context: K1ToolContext,
    ) -> K1GovernedTool:
        """Construct a K1GovernedTool from a catalog entry and context."""
        # Build a human-readable description combining name and category for
        # LLM tool-selection quality.
        description = (
            f"[{entry.category}] {entry.name} — "
            f"band={entry.safety_classification}, "
            f"timeout={entry.timeout_seconds}s"
        )
        return K1GovernedTool(
            name=entry.name,
            description=description,
            catalog_entry=entry,
            context=context,
        )


# ---------------------------------------------------------------------------
# Module singletons
# ---------------------------------------------------------------------------

_registry: K1LangChainToolRegistry | None = None


def get_tool_registry() -> K1LangChainToolRegistry:
    """
    Return the module-level K1LangChainToolRegistry singleton.

    Raises RuntimeError if initialize_tool_registry() has not been called yet.
    Callers in the Kai startup sequence should call initialize_tool_registry()
    during the lifespan setup; test code can call it directly.
    """
    global _registry
    if _registry is None:
        # Auto-initialize with no event_bus for convenience in tests / scripts
        _registry = K1LangChainToolRegistry()
    return _registry


def initialize_tool_registry(event_bus: Any = None) -> K1LangChainToolRegistry:
    """
    Initialize (or re-initialize) the module-level registry singleton.

    Safe to call multiple times — subsequent calls replace the existing singleton.
    Intended to be called from the FastAPI lifespan manager after the event bus
    is available.

    Args:
        event_bus: Optional EventBus instance for future pub/sub support.

    Returns:
        The newly created K1LangChainToolRegistry instance.
    """
    global _registry
    _registry = K1LangChainToolRegistry(event_bus=event_bus)
    logger.info("K1LangChainToolRegistry initialized (event_bus=%s)", event_bus is not None)
    return _registry
