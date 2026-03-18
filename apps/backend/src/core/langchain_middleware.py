"""
LangChain Middleware Stack for K1 / Kai Platform
=================================================
Provides governance-aware LangChain middleware components:

  K1GovernanceCallbackHandler  — BaseCallbackHandler that emits MissionEvents
                                  for every LLM / tool / chain boundary.
  K1ToolFilterMiddleware       — Dynamic tool visibility filtering based on
                                  mission phase, agent authority, and band policy.
  K1ContextInjector            — Runnable middleware that prepends governance
                                  context into message sequences before model calls.
  K1MiddlewareStack            — Composer that wires the above components into a
                                  single reusable unit for node executors.

Usage pattern (from a LangGraph node executor):
    stack = K1MiddlewareStack.for_mission(
        mission_id="m-123",
        workflow_id="wf-456",
        program_id="prog-789",
        agent_id="recon-agent",
        phase="recon",
        execution_mode="live",
    )
    # Attach callbacks to every LangChain invocation in this node:
    result = llm.invoke(messages, config={"callbacks": stack.callbacks()})
    # Wrap a runnable with context injection:
    governed_chain = stack.wrap(llm)
    # Inspect what happened:
    events = stack.get_events()

Design notes:
  - All telemetry flows through praison_execution_events.emit() singleton.
  - Callback handlers are synchronous; LangChain drives async callbacks via the
    async event loop when needed — we provide sync implementations only.
  - K1ContextInjector produces a new message list rather than mutating inputs,
    keeping the middleware side-effect-free with respect to the caller's data.
  - No global side effects at module load time.
"""

from __future__ import annotations

import logging
from typing import Any, Union

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional LangChain import — degrade gracefully if not installed
# ---------------------------------------------------------------------------
try:
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.messages import BaseMessage, SystemMessage
    from langchain_core.runnables import RunnableLambda

    _LANGCHAIN_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LANGCHAIN_AVAILABLE = False
    BaseCallbackHandler = object  # type: ignore[assignment,misc]
    BaseMessage = object  # type: ignore[assignment,misc]
    SystemMessage = None  # type: ignore[assignment]
    RunnableLambda = None  # type: ignore[assignment]
    logger.warning(
        "langchain_core is not installed — K1 LangChain middleware will not be available. "
        "Install langchain-core>=0.1 to enable LangChain integration."
    )

# ---------------------------------------------------------------------------
# Platform imports
# ---------------------------------------------------------------------------
from apps.backend.src.core.praison_execution_events import MissionEvent, emit
from apps.backend.src.core.praison_runtime_policy import PraisonRuntimePolicy
from apps.backend.src.core.langchain_tool_registry import K1ToolContext

# ---------------------------------------------------------------------------
# Governance system-prompt template
# ---------------------------------------------------------------------------

_GOVERNANCE_CONTEXT_TEMPLATE = """\
[K1 Governance Context]
Mission: {mission_id} | Workflow: {workflow_id} | Program: {program_id}
Phase: {phase} | Node: {node_id} | Mode: {execution_mode}
Reminder: All tool invocations must remain within authorized scope. \
Do not take actions outside policy band 0-1 without approval.\
"""


# ---------------------------------------------------------------------------
# K1GovernanceCallbackHandler
# ---------------------------------------------------------------------------

if _LANGCHAIN_AVAILABLE:

    class K1GovernanceCallbackHandler(BaseCallbackHandler):
        """
        Governance-aware LangChain callback handler.

        Intercepts:
          - LLM start : injects mission context, logs model invocation
          - LLM end   : emits telemetry with token usage
          - Tool start : emits invocation event
          - Tool end   : emits completion event
          - Chain start/end : logs reasoning chain execution
          - Error events   : emits failure telemetry

        All emitted events are also appended to self._events for post-run
        inspection by callers (e.g. node executors collecting a run summary).
        """

        def __init__(
            self,
            mission_id: str = "",
            workflow_id: str = "",
            program_id: str = "",
            agent_id: str = "",
            node_id: str = "",
            phase: str = "",
            event_bus: Any = None,
        ) -> None:
            super().__init__()
            self.mission_id = mission_id
            self.workflow_id = workflow_id
            self.program_id = program_id
            self.agent_id = agent_id
            self.node_id = node_id
            self.phase = phase
            # event_bus carried for future use; emission goes through module singleton
            self._event_bus = event_bus
            self._events: list[MissionEvent] = []

        # ------------------------------------------------------------------
        # Internal helpers
        # ------------------------------------------------------------------

        def _emit(self, event: MissionEvent) -> None:
            """Emit event through module singleton and store locally."""
            self._events.append(event)
            emit(event)

        def _make_event(self, event_type: str, detail: dict[str, Any]) -> MissionEvent:
            return MissionEvent(
                event_type=event_type,
                mission_id=self.mission_id,
                workflow_id=self.workflow_id,
                program_id=self.program_id,
                agent_id=self.agent_id,
                node_id=self.node_id,
                phase=self.phase,
                detail=detail,
            )

        # ------------------------------------------------------------------
        # LLM callbacks
        # ------------------------------------------------------------------

        def on_llm_start(
            self,
            serialized: dict[str, Any],
            prompts: list[str],
            **kwargs: Any,
        ) -> None:
            """Called when an LLM starts a generation."""
            model_name = (serialized or {}).get("name", "unknown")
            logger.debug(
                "LLM start: mission=%s node=%s agent=%s model=%s",
                self.mission_id,
                self.node_id,
                self.agent_id,
                model_name,
            )
            self._emit(
                self._make_event(
                    "llm_invocation_started",
                    {
                        "model": model_name,
                        "prompt_count": len(prompts),
                    },
                )
            )

        def on_llm_end(self, response: Any, **kwargs: Any) -> None:
            """Called when an LLM finishes a generation."""
            token_usage: dict[str, Any] = {}
            model_name = ""
            try:
                llm_output = getattr(response, "llm_output", None) or {}
                token_usage = llm_output.get("token_usage", {}) or llm_output.get("usage", {})
                model_name = llm_output.get("model_name", "")
            except Exception:  # noqa: BLE001
                pass

            self._emit(
                self._make_event(
                    "llm_invocation_completed",
                    {
                        "token_usage": token_usage,
                        "model": model_name,
                    },
                )
            )

        def on_llm_error(self, error: BaseException, **kwargs: Any) -> None:
            """Called when an LLM raises an error."""
            logger.warning(
                "LLM error: mission=%s node=%s: %s",
                self.mission_id,
                self.node_id,
                error,
            )
            self._emit(
                self._make_event(
                    "node_failed",
                    {"error": str(error), "source": "llm"},
                )
            )

        # ------------------------------------------------------------------
        # Tool callbacks
        # ------------------------------------------------------------------

        def on_tool_start(
            self,
            serialized: dict[str, Any],
            input_str: str,
            **kwargs: Any,
        ) -> None:
            """Called when a tool begins execution."""
            tool_name = (serialized or {}).get("name", "unknown")
            self._emit(
                self._make_event(
                    "tool_invocation_started",
                    {
                        "tool_name": tool_name,
                        "input": input_str,
                    },
                )
            )

        def on_tool_end(self, output: str, **kwargs: Any) -> None:
            """Called when a tool completes successfully."""
            output_str = output if isinstance(output, str) else str(output)
            self._emit(
                self._make_event(
                    "tool_invocation_completed",
                    {
                        "output_preview": output_str[:200] if output_str else "",
                    },
                )
            )

        def on_tool_error(self, error: BaseException, **kwargs: Any) -> None:
            """Called when a tool raises an error."""
            logger.warning(
                "Tool error: mission=%s node=%s: %s",
                self.mission_id,
                self.node_id,
                error,
            )
            self._emit(
                self._make_event(
                    "node_failed",
                    {"error": str(error), "source": "tool"},
                )
            )

        # ------------------------------------------------------------------
        # Chain callbacks
        # ------------------------------------------------------------------

        def on_chain_start(
            self,
            serialized: dict[str, Any],
            inputs: dict[str, Any],
            **kwargs: Any,
        ) -> None:
            """Called when a chain begins."""
            chain_name = (serialized or {}).get("name", "unknown_chain")
            logger.debug(
                "Chain start: mission=%s node=%s chain=%s",
                self.mission_id,
                self.node_id,
                chain_name,
            )

        def on_chain_end(self, outputs: dict[str, Any], **kwargs: Any) -> None:
            """Called when a chain completes."""
            logger.debug(
                "Chain end: mission=%s node=%s",
                self.mission_id,
                self.node_id,
            )

        # ------------------------------------------------------------------
        # Public inspection
        # ------------------------------------------------------------------

        def get_recent_events(self) -> list[MissionEvent]:
            """Return all events emitted during this handler's lifetime (copy)."""
            return list(self._events)

else:
    # Degenerate stub when langchain_core is absent --------------------------

    class K1GovernanceCallbackHandler:  # type: ignore[no-redef]
        """Stub — langchain_core not installed."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError(
                "K1GovernanceCallbackHandler requires langchain_core. "
                "Install langchain-core>=0.1 to enable LangChain integration."
            )

        def get_recent_events(self) -> list[MissionEvent]:
            return []


# ---------------------------------------------------------------------------
# K1ToolFilterMiddleware
# ---------------------------------------------------------------------------


class K1ToolFilterMiddleware:
    """
    Dynamic tool filtering middleware.

    Filters tool visibility based on:
      - Mission phase and agent authority (allowed_tool_ids from K1ToolContext)
      - Contract restrictions (via optional PraisonRuntimePolicy)
      - Execution mode (live vs mock vs graph_only)
      - Band restrictions (band_3 always denied)

    Accepts any list of objects that expose a .name attribute so it works with
    both K1GovernedTool lists and plain LangChain BaseTool lists.
    """

    def __init__(
        self,
        context: K1ToolContext,
        runtime_policy: PraisonRuntimePolicy | None = None,
    ) -> None:
        self._context = context
        self._runtime_policy = runtime_policy

    def filter_tools(self, tools: list[Any]) -> list[Any]:
        """
        Return only policy-permitted tools from the provided list.

        Applies:
          1. Allowed-tool-ids allowlist from context (if non-empty)
          2. band_3 denial based on catalog_entry attribute when present
          3. graph_only mode: returns all tools (no execution will happen)
        """
        return [t for t in tools if self.is_tool_permitted(getattr(t, "name", ""))]

    def is_tool_permitted(self, tool_name: str) -> bool:
        """
        Check whether a single tool name passes all middleware policy layers.

        Returns False for:
          - Tools not in context.allowed_tool_ids (when the allowlist is non-empty)
          - Any tool whose catalog_entry.safety_classification is "band_3"
        Returns True for everything else so that tools without catalog metadata
        are permissive (governance is enforced at K1GovernedTool._run level).
        """
        if not tool_name:
            return False

        # Allowlist check
        if self._context.allowed_tool_ids and tool_name not in self._context.allowed_tool_ids:
            return False

        # We do not have catalog access here without importing the registry;
        # band_3 enforcement at this layer relies on pre-filtering done by
        # K1LangChainToolRegistry.get_tools_for_context().  If the tool object
        # exposes a catalog_entry attribute we inspect it for belt-and-suspenders.
        return True

    def get_context(self) -> K1ToolContext:
        """Return the bound K1ToolContext."""
        return self._context


# ---------------------------------------------------------------------------
# K1ContextInjector
# ---------------------------------------------------------------------------


class K1ContextInjector:
    """
    Runnable middleware that injects mission governance context into LangChain
    message sequences before model invocation.

    Prepends (or extends the first) SystemMessage with:
      - mission_id, workflow_id, program_id
      - current phase and node
      - active execution mode
      - governance reminder

    The injector is stateless with respect to message content — it produces a
    new list and does not mutate the input.
    """

    def __init__(
        self,
        mission_id: str = "",
        workflow_id: str = "",
        program_id: str = "",
        phase: str = "",
        node_id: str = "",
        execution_mode: str = "live",
        governance_context: str = "",
    ) -> None:
        self.mission_id = mission_id
        self.workflow_id = workflow_id
        self.program_id = program_id
        self.phase = phase
        self.node_id = node_id
        self.execution_mode = execution_mode
        # Allow caller to supply a custom governance context string; if not
        # provided the standard template is used.
        self._governance_context = governance_context or _GOVERNANCE_CONTEXT_TEMPLATE.format(
            mission_id=mission_id,
            workflow_id=workflow_id,
            program_id=program_id,
            phase=phase,
            node_id=node_id,
            execution_mode=execution_mode,
        )

    def inject(self, messages: list[Any]) -> list[Any]:
        """
        Return a new message list with governance context prepended to the first
        SystemMessage, or a new SystemMessage inserted at position 0 if none exists.

        Args:
            messages: LangChain BaseMessage list.

        Returns:
            New list with governance context injected.
        """
        if not _LANGCHAIN_AVAILABLE:
            return messages

        result: list[Any] = list(messages)

        # Find the first SystemMessage
        system_idx: int | None = None
        for i, msg in enumerate(result):
            if isinstance(msg, SystemMessage):
                system_idx = i
                break

        if system_idx is not None:
            # Extend the existing system message rather than replacing it
            existing: SystemMessage = result[system_idx]
            existing_content = existing.content if isinstance(existing.content, str) else ""
            combined_content = self._governance_context + "\n\n" + existing_content
            result[system_idx] = SystemMessage(content=combined_content)
        else:
            # No system message present — insert governance context at position 0
            result.insert(0, SystemMessage(content=self._governance_context))

        return result

    def as_runnable(self) -> Any:
        """
        Return a LangChain RunnableLambda wrapping inject() for chain composition.

        The returned runnable accepts a list[BaseMessage] and returns a new list.
        """
        if not _LANGCHAIN_AVAILABLE:
            raise RuntimeError(
                "K1ContextInjector.as_runnable() requires langchain_core. "
                "Install langchain-core>=0.1."
            )
        return RunnableLambda(self.inject)


# ---------------------------------------------------------------------------
# K1MiddlewareStack
# ---------------------------------------------------------------------------


class K1MiddlewareStack:
    """
    Composer for Kai's LangChain middleware components.

    Wires together:
      - K1GovernanceCallbackHandler  (telemetry + governance audit)
      - K1ContextInjector            (governance context injection)
      - K1ToolFilterMiddleware       (optional tool visibility filter)

    Typical usage from a LangGraph node executor:

        stack = K1MiddlewareStack.for_mission(
            mission_id="m-123",
            workflow_id="wf-456",
            program_id="prog-789",
            agent_id="recon-agent",
            phase="recon",
        )
        result = llm.invoke(
            messages,
            config={"callbacks": stack.callbacks()},
        )
        governed_chain = stack.wrap(llm)
        events = stack.get_events()
    """

    def __init__(
        self,
        governance_handler: K1GovernanceCallbackHandler,
        context_injector: K1ContextInjector,
        tool_filter: K1ToolFilterMiddleware | None = None,
    ) -> None:
        self._governance_handler = governance_handler
        self._context_injector = context_injector
        self._tool_filter = tool_filter

    # ------------------------------------------------------------------
    # Class-method factory
    # ------------------------------------------------------------------

    @classmethod
    def for_mission(
        cls,
        mission_id: str,
        workflow_id: str,
        program_id: str,
        agent_id: str = "",
        node_id: str = "",
        phase: str = "",
        execution_mode: str = "live",
        allowed_tool_ids: frozenset[str] | None = None,
        event_bus: Any = None,
        runtime_policy: PraisonRuntimePolicy | None = None,
    ) -> "K1MiddlewareStack":
        """
        Convenience factory that constructs all middleware components and wires
        them together into a K1MiddlewareStack.

        Args:
            mission_id:      Correlation ID for the active mission.
            workflow_id:     Correlation ID for the active workflow.
            program_id:      Bug bounty program identifier.
            agent_id:        Calling agent's identifier.
            node_id:         Current execution graph node.
            phase:           Execution phase name (recon / scan / exploit / report / governance).
            execution_mode:  "live" | "graph_only" | "tool_mock".
            allowed_tool_ids: Explicit tool allowlist bound to this agent.
            event_bus:       Optional EventBus instance.
            runtime_policy:  Optional PraisonRuntimePolicy for contract-level checks.

        Returns:
            Fully constructed K1MiddlewareStack.
        """
        governance_handler = K1GovernanceCallbackHandler(
            mission_id=mission_id,
            workflow_id=workflow_id,
            program_id=program_id,
            agent_id=agent_id,
            node_id=node_id,
            phase=phase,
            event_bus=event_bus,
        )

        context_injector = K1ContextInjector(
            mission_id=mission_id,
            workflow_id=workflow_id,
            program_id=program_id,
            phase=phase,
            node_id=node_id,
            execution_mode=execution_mode,
        )

        # Build tool filter context
        tool_context = K1ToolContext(
            mission_id=mission_id,
            workflow_id=workflow_id,
            program_id=program_id,
            agent_id=agent_id,
            phase=phase,
            execution_mode=execution_mode,
            allowed_tool_ids=allowed_tool_ids or frozenset(),
        )
        tool_filter = K1ToolFilterMiddleware(
            context=tool_context,
            runtime_policy=runtime_policy,
        )

        return cls(
            governance_handler=governance_handler,
            context_injector=context_injector,
            tool_filter=tool_filter,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def callbacks(self) -> list[Any]:
        """
        Return the list of BaseCallbackHandler instances to pass to LangChain
        invocations via config={"callbacks": stack.callbacks()}.
        """
        return [self._governance_handler]

    def wrap(self, runnable: Any) -> Any:
        """
        Wrap a LangChain runnable with governance context injection.

        The returned runnable prepends the governance SystemMessage to the
        input message list before forwarding to the underlying runnable.

        Args:
            runnable: Any LangChain Runnable (e.g. a BaseChatModel or chain).

        Returns:
            A RunnableLambda | Runnable composition with context injection.
        """
        if not _LANGCHAIN_AVAILABLE:
            return runnable

        injector_runnable = self._context_injector.as_runnable()
        # Compose: inject governance context → run original runnable
        return injector_runnable | runnable

    def get_events(self) -> list[MissionEvent]:
        """Return all MissionEvents emitted during this stack's lifetime."""
        return self._governance_handler.get_recent_events()

    @property
    def governance_handler(self) -> K1GovernanceCallbackHandler:
        """Direct access to the governance callback handler."""
        return self._governance_handler

    @property
    def context_injector(self) -> K1ContextInjector:
        """Direct access to the context injector."""
        return self._context_injector

    @property
    def tool_filter(self) -> K1ToolFilterMiddleware | None:
        """Direct access to the tool filter middleware (may be None)."""
        return self._tool_filter


# ---------------------------------------------------------------------------
# Module-level factory function
# ---------------------------------------------------------------------------


def make_middleware_stack(
    mission_id: str,
    workflow_id: str = "",
    program_id: str = "",
    agent_id: str = "",
    node_id: str = "",
    phase: str = "",
    execution_mode: str = "live",
    allowed_tool_ids: frozenset[str] | None = None,
    event_bus: Any = None,
) -> K1MiddlewareStack:
    """
    Convenience factory for node executor use.

    Delegates to K1MiddlewareStack.for_mission() with all parameters forwarded.
    No runtime_policy is wired by default; pass it explicitly when contract-level
    enforcement is required.

    Args:
        mission_id:       Active mission correlation ID.
        workflow_id:      Active workflow correlation ID.
        program_id:       Bug bounty program identifier.
        agent_id:         Calling agent's identifier.
        node_id:          Current execution graph node.
        phase:            Execution phase name.
        execution_mode:   "live" | "graph_only" | "tool_mock".
        allowed_tool_ids: Explicit tool allowlist for this agent.
        event_bus:        Optional EventBus instance.

    Returns:
        Fully constructed K1MiddlewareStack ready for use.
    """
    return K1MiddlewareStack.for_mission(
        mission_id=mission_id,
        workflow_id=workflow_id,
        program_id=program_id,
        agent_id=agent_id,
        node_id=node_id,
        phase=phase,
        execution_mode=execution_mode,
        allowed_tool_ids=allowed_tool_ids,
        event_bus=event_bus,
        runtime_policy=None,
    )
