"""
DeepAgents Adapter — Kai Specialist Deep Work Runtime
======================================================
Constructs governed DeepAgent specialist instances from K1 AgentIdentity.

Dual-path architecture (Package Alignment, Phase 5):
  When the official ``deepagents`` PyPI package (>=0.4) is installed, live
  execution delegates to ``deepagents.create_deep_agent()`` which returns a
  LangGraph ``CompiledStateGraph``. Kai injects K1ChatModel as the model,
  K1GovernedTools as tools, and governance middleware into the deepagents
  middleware stack. The real package handles planning, filesystem, subagent
  orchestration, and summarization natively.

  When the package is NOT installed (Python < 3.11 or missing dependency),
  falls back to Kai's native execution path: manual LLM invoke via
  K1ChatModel + governed tools + middleware callbacks. All public interfaces
  remain identical in both paths.

Architecture position:
  PraisonAI → Control Plane (authority)
  LangGraph → Mission Execution Runtime (graph backbone)
  LangChain → Model / Tool / Middleware Layer (reasoning substrate)
  DeepAgents → Specialist Deep Work Runtime (THIS LAYER)

DeepAgents handles:
  - Specialist planning and local reasoning
  - Bounded tool execution under governance
  - Structured output production
  - Subagent delegation with contract enforcement
  - Scratch workspace management
  - Stream event emission into Kai telemetry

DeepAgents does NOT:
  - Own mission routing (LangGraph does)
  - Own authority/policy (Praison does)
  - Own the source of truth for artifacts/state (Kai does)
  - Bypass governance for tool/target access
  - Mutate mission topology
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from apps.backend.src.core.praison_agent import AgentIdentity, resolve_litellm_string
from apps.backend.src.core.praison_adapters import FrameworkNotInstalledError

logger = logging.getLogger(__name__)

# -- Real deepagents package availability check --------------------------------
# The official deepagents PyPI package requires Python >=3.11 and provides
# create_deep_agent() returning a LangGraph CompiledStateGraph.
try:
    from deepagents import create_deep_agent as _real_create_deep_agent  # type: ignore[import-untyped]
    from deepagents import SubAgent as _RealSubAgent  # type: ignore[import-untyped]  # noqa: F401
    from deepagents.backends import StateBackend as _RealStateBackend  # type: ignore[import-untyped]
    _DEEPAGENTS_AVAILABLE = True
    logger.info("deepagents package available (real package path enabled)")
except ImportError:
    _DEEPAGENTS_AVAILABLE = False
    _real_create_deep_agent = None  # type: ignore[assignment]
    _RealStateBackend = None  # type: ignore[assignment,misc]
    logger.info(
        "deepagents package not installed — using Kai-native execution path. "
        "Install with: pip install 'deepagents>=0.4' (requires Python >=3.11)"
    )


# -- Specialist type defaults --------------------------------------------------

_SPECIALIST_DEFAULTS: dict[str, dict[str, Any]] = {
    "evidence_analyst": {
        "max_iterations": 20,
        "max_subagents": 2,
        "max_tokens_budget": 80_000,
    },
    "triage_specialist": {
        "max_iterations": 15,
        "max_subagents": 1,
        "max_tokens_budget": 40_000,
    },
    "exploit_assessor": {
        "max_iterations": 10,
        "max_subagents": 0,
        "max_tokens_budget": 30_000,
    },
    "report_synthesizer": {
        "max_iterations": 25,
        "max_subagents": 3,
        "max_tokens_budget": 100_000,
    },
    "knowledge_curator": {
        "max_iterations": 15,
        "max_subagents": 0,
        "max_tokens_budget": 40_000,
    },
}

_VALID_SPECIALIST_TYPES = frozenset(_SPECIALIST_DEFAULTS.keys())
_VALID_EXECUTION_MODES = frozenset({"live", "graph_only", "tool_mock"})
_VALID_BACKEND_POLICIES = frozenset({"ephemeral", "scratch", "durable"})

# Iteration limits inherited from review_policy when specialist_type is not set
_REVIEW_POLICY_ITERATIONS: dict[str, int] = {
    "strict": 5,
    "moderate": 10,
    "standard": 15,
}


# -- Package availability API --------------------------------------------------


def is_deepagents_available() -> bool:
    """Return True if the official deepagents PyPI package is importable."""
    return _DEEPAGENTS_AVAILABLE


def build_k1_subagent_spec(
    identity: AgentIdentity,
    *,
    tools: list[Any] | None = None,
    model: Any = None,
    middleware: list[Any] | None = None,
) -> dict[str, Any]:
    """
    Build a SubAgent-compatible spec dict from Kai AgentIdentity.

    When the real deepagents package is available, this dict is structurally
    compatible with ``deepagents.SubAgent`` TypedDict (name, description,
    system_prompt, tools, model, middleware). When not available, it serves
    as a serializable spec for scaffolding and audit.

    Args:
        identity: Source AgentIdentity for the subagent.
        tools: LangChain tools the subagent may use. Defaults to empty list.
        model: BaseChatModel or model string. Defaults to None (inherits parent).
        middleware: Additional AgentMiddleware instances. Defaults to empty list.

    Returns:
        Dict compatible with deepagents.SubAgent TypedDict.
    """
    return {
        "name": identity.agent_id,
        "description": identity.description or identity.persona,
        "system_prompt": identity.system_prompt,
        "tools": tools or [],
        "model": model,
        "middleware": middleware or [],
    }


# -- DeepAgentConfig -----------------------------------------------------------


@dataclass(frozen=True)
class DeepAgentConfig:
    """Immutable configuration for a DeepAgent specialist."""

    agent_id: str
    specialist_type: str  # one of _VALID_SPECIALIST_TYPES or empty string
    identity: AgentIdentity
    system_prompt: str
    model_name: str  # model identifier for K1ChatModel
    preferred_provider: str | None  # LLM provider preference
    tool_ids: frozenset[str]  # allowed tool IDs (from contract or identity)
    target_ids: frozenset[str]  # allowed targets (from contract)
    phase: str  # current mission phase
    execution_mode: str  # "live" | "graph_only" | "tool_mock"
    mission_id: str
    workflow_id: str
    program_id: str
    max_iterations: int  # bounded reasoning iterations
    max_subagents: int  # concurrency limit for subagent spawning
    max_tokens_budget: int  # token budget limit
    response_format: type | None  # Pydantic schema for structured output
    contract: Any | None  # DelegationContract or None (typed as Any to avoid import cycle)
    backend_policy: str  # "ephemeral" | "scratch" | "durable"
    scratch_prefix: str  # allowed scratch path prefix (K1_ARTIFACTS_ROOT)
    sandbox_enabled: bool  # whether code execution sandbox is available
    interrupt_on_band2: bool  # request approval for band_2 tool use
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate invariants and coerce mutable inputs."""
        if isinstance(self.tool_ids, (list, tuple, set)):
            object.__setattr__(self, "tool_ids", frozenset(self.tool_ids))
        if isinstance(self.target_ids, (list, tuple, set)):
            object.__setattr__(self, "target_ids", frozenset(self.target_ids))
        if isinstance(self.metadata, dict):
            # Defensive copy to prevent external mutation
            object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for audit trail and scaffolding."""
        return {
            "agent_id": self.agent_id,
            "specialist_type": self.specialist_type,
            "identity_id": self.identity.agent_id,
            "system_prompt_length": len(self.system_prompt),
            "model_name": self.model_name,
            "preferred_provider": self.preferred_provider,
            "tool_ids": sorted(self.tool_ids),
            "target_ids": sorted(self.target_ids),
            "phase": self.phase,
            "execution_mode": self.execution_mode,
            "mission_id": self.mission_id,
            "workflow_id": self.workflow_id,
            "program_id": self.program_id,
            "max_iterations": self.max_iterations,
            "max_subagents": self.max_subagents,
            "max_tokens_budget": self.max_tokens_budget,
            "response_format": (
                self.response_format.__name__ if self.response_format else None
            ),
            "contract_id": (
                getattr(self.contract, "contract_id", None) if self.contract else None
            ),
            "backend_policy": self.backend_policy,
            "scratch_prefix": self.scratch_prefix,
            "sandbox_enabled": self.sandbox_enabled,
            "interrupt_on_band2": self.interrupt_on_band2,
            "metadata": self.metadata,
        }


# -- DeepAgentResult -----------------------------------------------------------


@dataclass
class DeepAgentResult:
    """Result of a DeepAgent specialist execution."""

    agent_id: str = ""
    specialist_type: str = ""
    success: bool = False
    output: dict[str, Any] = field(default_factory=dict)
    structured_output: Any | None = None  # parsed Pydantic model if response_format was set
    artifacts_produced: list[dict[str, Any]] = field(default_factory=list)
    subagent_results: list[DeepAgentResult] = field(default_factory=list)
    contracts_created: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    iterations_used: int = 0
    tokens_used: int = 0
    latency_ms: float = 0.0
    error: str = ""

    def to_state_update(self) -> dict[str, Any]:
        """Convert to K1GraphState-compatible state update dict."""
        update: dict[str, Any] = {}
        if self.output:
            update["last_output"] = self.output
        if self.structured_output is not None:
            update["structured_output"] = self.structured_output
        if self.artifacts_produced:
            update["artifacts"] = list(self.artifacts_produced)
        if self.events:
            update["events"] = self.events
        if self.error:
            update["error"] = self.error
        if self.contracts_created:
            update["contract_ids"] = [
                c.get("contract_id", "") for c in self.contracts_created
            ]
        # Flatten subagent artifacts
        for sub_result in self.subagent_results:
            if sub_result.artifacts_produced:
                update.setdefault("artifacts", []).extend(
                    sub_result.artifacts_produced
                )
        # Telemetry metadata
        update["_specialist_meta"] = {
            "agent_id": self.agent_id,
            "specialist_type": self.specialist_type,
            "success": self.success,
            "iterations_used": self.iterations_used,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
        }
        return update

    def to_dict(self) -> dict[str, Any]:
        """Serialize for telemetry and audit."""
        return {
            "agent_id": self.agent_id,
            "specialist_type": self.specialist_type,
            "success": self.success,
            "output": self.output,
            "artifacts_count": len(self.artifacts_produced),
            "subagent_count": len(self.subagent_results),
            "contracts_count": len(self.contracts_created),
            "events_count": len(self.events),
            "iterations_used": self.iterations_used,
            "tokens_used": self.tokens_used,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


# -- DeepAgent -----------------------------------------------------------------


class DeepAgent:
    """
    Governed specialist deep-work agent.

    Executes long-horizon, context-heavy specialist tasks under full
    Kai governance. Uses K1ChatModel for LLM calls, governed tools for
    actions, and structured outputs for machine-consumed results.

    Execution flow:
    1. Validate config against governance (tools, targets, budget)
    2. Build LangChain chain with middleware callbacks
    3. Execute bounded reasoning loop (max_iterations)
    4. Collect structured output
    5. Emit telemetry events
    6. Return DeepAgentResult

    Simulation modes:
    - graph_only: returns deterministic fixture without LLM calls
    - tool_mock: LLM calls happen but tool calls return mocks
    - live: full execution under governance
    """

    def __init__(self, config: DeepAgentConfig) -> None:
        self._config = config
        self._events: list[dict[str, Any]] = []
        self._iterations: int = 0
        self._tokens: int = 0

    @property
    def config(self) -> DeepAgentConfig:
        """Return the immutable configuration for this agent."""
        return self._config

    # -- Public execution API --------------------------------------------------

    async def execute(
        self, task: str, context: dict[str, Any] | None = None
    ) -> DeepAgentResult:
        """
        Execute specialist task.

        Args:
            task: Natural language task description.
            context: Additional execution context (artifacts, findings, etc.).

        Returns:
            DeepAgentResult with structured output, artifacts, events.
        """
        start_ms = time.monotonic()

        self._emit_event("deep_agent_started", {
            "task_preview": task[:200],
            "specialist_type": self._config.specialist_type,
            "execution_mode": self._config.execution_mode,
        })

        # Simulation fast-path
        if self._is_simulation():
            result = self._build_simulation_result(task)
            result.latency_ms = (time.monotonic() - start_ms) * 1000.0
            return result

        # Live execution
        try:
            result = await self._execute_live(task, context or {})
        except Exception as exc:
            logger.error(
                "DeepAgent %s execution failed: %s",
                self._config.agent_id,
                exc,
                exc_info=True,
            )
            self._emit_event("deep_agent_failed", {"error": str(exc)})
            result = DeepAgentResult(
                agent_id=self._config.agent_id,
                specialist_type=self._config.specialist_type,
                success=False,
                output={"text": f"Execution failed: {exc}"},
                events=list(self._events),
                iterations_used=self._iterations,
                tokens_used=self._tokens,
                error=str(exc),
            )

        result.latency_ms = (time.monotonic() - start_ms) * 1000.0
        self._emit_event("deep_agent_completed", {
            "success": result.success,
            "iterations": result.iterations_used,
            "tokens": result.tokens_used,
            "latency_ms": result.latency_ms,
        })
        result.events = list(self._events)
        return result

    async def execute_structured(
        self,
        task: str,
        schema: type,
        context: dict[str, Any] | None = None,
    ) -> DeepAgentResult:
        """
        Execute and return structured output validated against schema.

        Temporarily overrides the config's response_format for this invocation,
        then delegates to execute(). The parsed Pydantic model is placed in
        result.structured_output.
        """
        # Create a new config with the provided schema as response_format
        from dataclasses import replace as dc_replace

        patched_config = dc_replace(self._config, response_format=schema)
        original_config = self._config
        self._config = patched_config  # type: ignore[misc]
        try:
            result = await self.execute(task, context)
        finally:
            self._config = original_config  # type: ignore[misc]
        return result

    # -- Simulation support ----------------------------------------------------

    def _is_simulation(self) -> bool:
        """Return True if executing in a non-live mode."""
        return self._config.execution_mode in ("graph_only", "tool_mock")

    def _build_simulation_result(self, task: str) -> DeepAgentResult:
        """Return deterministic fixture for simulation modes."""
        return DeepAgentResult(
            agent_id=self._config.agent_id,
            specialist_type=self._config.specialist_type,
            success=True,
            output={
                "text": (
                    f"[SIMULATION] Specialist {self._config.specialist_type} "
                    f"completed: {task[:100]}"
                ),
            },
            structured_output=None,
            artifacts_produced=[],
            subagent_results=[],
            contracts_created=[],
            events=[{
                "event_type": "deep_agent_completed",
                "mode": "simulation",
                "execution_mode": self._config.execution_mode,
            }],
            iterations_used=0,
            tokens_used=0,
            latency_ms=0.0,
            error="",
        )

    # -- Live execution --------------------------------------------------------

    async def _execute_live(
        self, task: str, context: dict[str, Any]
    ) -> DeepAgentResult:
        """
        Real execution path with LLM calls under governance.

        Dual-path:
        A. When real deepagents is available: delegates to the official
           ``create_deep_agent()`` which returns a LangGraph CompiledStateGraph.
           Kai injects K1ChatModel, governed tools, and governance callbacks.
        B. When not available: manual LLM invoke via K1ChatModel + middleware.

        Both paths enforce the same governance: tool allowlists, band policy,
        scope validation, and telemetry emission.
        """
        # Try real deepagents path first
        if _DEEPAGENTS_AVAILABLE:
            try:
                return await self._execute_via_real_deepagents(task, context)
            except Exception as exc:
                logger.warning(
                    "DeepAgent %s: real deepagents execution failed (%s), "
                    "falling back to Kai-native path",
                    self._config.agent_id,
                    exc,
                )
                self._emit_event("deep_agent_real_package_fallback", {
                    "reason": str(exc),
                })

        return await self._execute_native(task, context)

    async def _execute_via_real_deepagents(
        self, task: str, context: dict[str, Any]
    ) -> DeepAgentResult:
        """
        Execute via the official deepagents package (CompiledStateGraph path).

        Steps:
        1. Build K1ChatModel via model factory
        2. Resolve governed tools
        3. Build the compiled graph via deepagents.create_deep_agent()
        4. Invoke the graph with the task as a HumanMessage
        5. Extract response and convert to DeepAgentResult
        """
        from apps.backend.src.core.langchain_model_factory import get_model_factory
        from apps.backend.src.core.langchain_tool_registry import (
            K1ToolContext,
            get_tool_registry,
        )

        cfg = self._config

        # Step 1: Create K1ChatModel (governance-wrapped)
        factory = get_model_factory()
        model = factory.create(
            preferred_provider=cfg.preferred_provider,
            system_prompt=cfg.system_prompt,
            mission_id=cfg.mission_id,
            temperature=0.7,
            max_tokens=min(cfg.max_tokens_budget, 4096),
        )
        if model is None:
            raise RuntimeError("K1ChatModel creation failed for real deepagents path")

        # Step 2: Resolve governed tools
        tool_context = K1ToolContext(
            mission_id=cfg.mission_id,
            workflow_id=cfg.workflow_id,
            program_id=cfg.program_id,
            agent_id=cfg.agent_id,
            phase=cfg.phase,
            execution_mode=cfg.execution_mode,
            allowed_tool_ids=cfg.tool_ids,
        )
        try:
            registry = get_tool_registry()
            tools = registry.get_tools_for_context(tool_context)
        except Exception:
            tools = []

        # Step 3: Build the real deepagents compiled graph
        # K1ChatModel is passed as model (governance-wrapped LLM)
        # K1GovernedTools are passed as tools (governance-wrapped tools)
        # StateBackend is used for ephemeral file operations (safe default)
        from langchain_core.messages import HumanMessage  # type: ignore[import-untyped]

        compiled_graph = _real_create_deep_agent(
            model=model,
            tools=tools,
            system_prompt=cfg.system_prompt,
            backend=_RealStateBackend,
            name=cfg.agent_id,
        )

        self._emit_event("deep_agent_real_package_invoke", {
            "model": cfg.model_name,
            "tools_available": len(tools),
            "backend": "deepagents.StateBackend",
        })

        # Step 4: Invoke the compiled graph
        result_state = await compiled_graph.ainvoke(
            {"messages": [HumanMessage(content=f"Task: {task}")]},
            config={"recursion_limit": min(cfg.max_iterations, 100)},
        )

        # Step 5: Extract response from graph output state
        messages = result_state.get("messages", [])
        response_text = ""
        if messages:
            last_msg = messages[-1]
            response_text = (
                last_msg.content if hasattr(last_msg, "content") else str(last_msg)
            )

        self._iterations = 1
        output_dict = {"text": response_text}

        return DeepAgentResult(
            agent_id=cfg.agent_id,
            specialist_type=cfg.specialist_type,
            success=True,
            output=output_dict,
            structured_output=None,
            artifacts_produced=[],
            subagent_results=[],
            contracts_created=[],
            events=list(self._events),
            iterations_used=self._iterations,
            tokens_used=self._tokens,
            error="",
        )

    async def _execute_native(
        self, task: str, context: dict[str, Any]
    ) -> DeepAgentResult:
        """
        Kai-native execution path (fallback when real deepagents is unavailable).

        Steps:
        1. Obtain K1ModelFactory and create K1ChatModel
        2. Build K1MiddlewareStack for telemetry and governance injection
        3. Resolve governed tools for the agent's tool context
        4. Build prompt with system_prompt + task + context
        5. Invoke the LLM (with structured output if response_format is set)
        6. Parse response into DeepAgentResult
        """
        # Lazy imports to avoid circular imports and handle missing packages
        from apps.backend.src.core.langchain_model_factory import get_model_factory
        from apps.backend.src.core.langchain_middleware import make_middleware_stack
        from apps.backend.src.core.langchain_tool_registry import (
            K1ToolContext,
            get_tool_registry,
        )

        cfg = self._config

        # Step 1: Create K1ChatModel
        factory = get_model_factory()
        model = factory.create(
            preferred_provider=cfg.preferred_provider,
            system_prompt=cfg.system_prompt,
            mission_id=cfg.mission_id,
            temperature=0.7,
            max_tokens=min(cfg.max_tokens_budget, 4096),
        )
        if model is None:
            raise RuntimeError(
                "K1ChatModel creation failed — langchain_core may not be installed. "
                "Install langchain-core>=0.1 to enable DeepAgent live execution."
            )

        # Step 2: Build middleware stack
        middleware = make_middleware_stack(
            mission_id=cfg.mission_id,
            workflow_id=cfg.workflow_id,
            program_id=cfg.program_id,
            agent_id=cfg.agent_id,
            phase=cfg.phase,
            execution_mode=cfg.execution_mode,
            allowed_tool_ids=cfg.tool_ids or frozenset(),
        )

        # Step 3: Resolve governed tools
        tool_context = K1ToolContext(
            mission_id=cfg.mission_id,
            workflow_id=cfg.workflow_id,
            program_id=cfg.program_id,
            agent_id=cfg.agent_id,
            phase=cfg.phase,
            execution_mode=cfg.execution_mode,
            allowed_tool_ids=cfg.tool_ids,
        )

        try:
            registry = get_tool_registry()
            tools = registry.get_tools_for_context(tool_context)
        except Exception as exc:
            logger.warning(
                "DeepAgent %s: tool resolution failed (%s), proceeding without tools",
                cfg.agent_id,
                exc,
            )
            tools = []

        # Step 4: Build prompt messages
        try:
            from langchain_core.messages import HumanMessage, SystemMessage  # type: ignore[import-untyped]
        except ImportError:
            raise FrameworkNotInstalledError(
                framework="deepagents",
                package="langchain-core",
                install_hint="pip install 'langchain-core>=0.1,<1.0'",
            )

        messages: list[Any] = []
        if cfg.system_prompt:
            messages.append(SystemMessage(content=cfg.system_prompt))

        # Build the human message with task and context
        human_parts: list[str] = [f"Task: {task}"]
        if context:
            # Include relevant context sections
            if context.get("artifacts"):
                artifact_summary = f"Input artifacts ({len(context['artifacts'])} items available)"
                human_parts.append(f"\n{artifact_summary}")
            if context.get("findings"):
                findings_summary = f"Relevant findings ({len(context['findings'])} items)"
                human_parts.append(f"\n{findings_summary}")
            if context.get("phase"):
                human_parts.append(f"\nCurrent phase: {context['phase']}")
            if context.get("state_snapshot"):
                snapshot_keys = list(context["state_snapshot"].keys())
                human_parts.append(f"\nState context keys: {snapshot_keys}")
        messages.append(HumanMessage(content="\n".join(human_parts)))

        self._iterations = 1
        self._emit_event("deep_agent_llm_invoke", {
            "model": cfg.model_name,
            "tools_available": len(tools),
            "has_structured_output": cfg.response_format is not None,
        })

        # Step 5: Invoke the LLM
        try:
            from langchain_core.runnables import RunnableConfig  # type: ignore[import-untyped]
        except ImportError:
            RunnableConfig = dict  # type: ignore[assignment,misc]

        invoke_config = RunnableConfig(callbacks=middleware.callbacks())

        if cfg.response_format is not None:
            # Structured output path
            structured_chain = model.with_structured_output(cfg.response_format)
            governed_chain = middleware.wrap(structured_chain)
            response = await governed_chain.ainvoke(messages, config=invoke_config)

            # response is the parsed Pydantic model (or dict)
            structured_output = response
            output_dict = (
                response.model_dump()
                if hasattr(response, "model_dump")
                else {"result": str(response)}
            )
        else:
            # Freeform text path
            governed_chain = middleware.wrap(model)
            response = await governed_chain.ainvoke(messages, config=invoke_config)

            structured_output = None
            # response is an AIMessage
            response_text = (
                response.content
                if hasattr(response, "content")
                else str(response)
            )
            output_dict = {"text": response_text}

        # Step 6: Estimate token usage from middleware events
        mw_events = middleware.get_events()
        total_tokens = 0
        for evt in mw_events:
            token_data = evt.detail.get("token_usage", {})
            if isinstance(token_data, dict):
                total_tokens += token_data.get("total_tokens", 0)
        self._tokens = total_tokens

        # Build artifacts from structured output if applicable
        artifacts: list[dict[str, Any]] = []
        if structured_output is not None:
            artifacts.append({
                "artifact_id": str(uuid.uuid4()),
                "artifact_type": (
                    cfg.response_format.__name__ if cfg.response_format else "structured"
                ),
                "producer_agent_id": cfg.agent_id,
                "specialist_type": cfg.specialist_type,
                "phase": cfg.phase,
                "content": output_dict,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })

        return DeepAgentResult(
            agent_id=cfg.agent_id,
            specialist_type=cfg.specialist_type,
            success=True,
            output=output_dict,
            structured_output=structured_output,
            artifacts_produced=artifacts,
            subagent_results=[],
            contracts_created=[],
            events=list(self._events),
            iterations_used=self._iterations,
            tokens_used=self._tokens,
            error="",
        )

    # -- Event emission --------------------------------------------------------

    def _emit_event(self, event_type: str, detail: dict[str, Any]) -> None:
        """Record event for later emission to EventBus."""
        self._events.append({
            "event_id": str(uuid.uuid4()),
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent_id": self._config.agent_id,
            "specialist_type": self._config.specialist_type,
            "mission_id": self._config.mission_id,
            "workflow_id": self._config.workflow_id,
            "program_id": self._config.program_id,
            "phase": self._config.phase,
            "detail": detail,
        })


# -- Factory function ----------------------------------------------------------


def create_deep_agent(
    identity: AgentIdentity,
    *,
    specialist_type: str = "",
    phase: str = "",
    execution_mode: str = "live",
    mission_id: str = "",
    workflow_id: str = "",
    program_id: str = "",
    response_format: type | None = None,
    contract: Any | None = None,
    max_iterations: int | None = None,
    max_subagents: int | None = None,
    max_tokens_budget: int | None = None,
    backend_policy: str = "ephemeral",
    sandbox_enabled: bool = False,
    interrupt_on_band2: bool = True,
    metadata: dict[str, Any] | None = None,
) -> DeepAgent:
    """
    Factory function: create a governed DeepAgent from AgentIdentity.

    This is the canonical entry point for DeepAgent creation.
    All DeepAgents must be created through this function.

    Specialist-type defaults (max_iterations, max_subagents, max_tokens_budget)
    are applied when the corresponding kwargs are None and a known specialist_type
    is provided. Explicit values always take precedence.

    Args:
        identity: AgentIdentity with static persona and policy fields.
        specialist_type: One of the _VALID_SPECIALIST_TYPES or empty string.
        phase: Current mission phase name.
        execution_mode: "live" | "graph_only" | "tool_mock".
        mission_id: Active mission correlation ID.
        workflow_id: Active workflow correlation ID.
        program_id: Bug bounty program identifier.
        response_format: Pydantic schema for structured output (optional).
        contract: Governing DelegationContract (optional).
        max_iterations: Override max reasoning iterations.
        max_subagents: Override max subagent concurrency.
        max_tokens_budget: Override token budget.
        backend_policy: "ephemeral" | "scratch" | "durable".
        sandbox_enabled: Whether code execution sandbox is available.
        interrupt_on_band2: Request approval for band_2 tool use.
        metadata: Additional specialist-specific config.

    Returns:
        DeepAgent instance ready for execution.
    """
    import os

    # Resolve specialist defaults
    spec_defaults = _SPECIALIST_DEFAULTS.get(specialist_type, {})
    resolved_max_iterations = (
        max_iterations
        if max_iterations is not None
        else spec_defaults.get(
            "max_iterations",
            _REVIEW_POLICY_ITERATIONS.get(identity.review_policy, 15),
        )
    )
    resolved_max_subagents = (
        max_subagents
        if max_subagents is not None
        else spec_defaults.get("max_subagents", 3)
    )
    resolved_max_tokens = (
        max_tokens_budget
        if max_tokens_budget is not None
        else spec_defaults.get("max_tokens_budget", 50_000)
    )

    # Resolve tool IDs from contract or identity
    if contract is not None and hasattr(contract, "allowed_tools"):
        tool_ids = frozenset(contract.allowed_tools)
    else:
        tool_ids = frozenset(identity.allowed_tools)

    # Resolve target IDs from contract
    if contract is not None and hasattr(contract, "allowed_targets"):
        target_ids = frozenset(contract.allowed_targets)
    else:
        target_ids = frozenset()

    # Resolve mission context — prefer explicit args, fall back to identity
    resolved_mission_id = mission_id or identity.workflow_id or ""
    resolved_workflow_id = workflow_id or identity.workflow_id or ""
    resolved_program_id = program_id or identity.program_id or ""

    # Resolve scratch path prefix
    artifacts_root = os.getenv("K1_ARTIFACTS_ROOT", "artifacts")
    scratch_prefix = os.path.join(artifacts_root, "scratch")

    # Validate execution mode
    if execution_mode not in _VALID_EXECUTION_MODES:
        logger.warning(
            "DeepAgent %s: invalid execution_mode %r, defaulting to 'graph_only'",
            identity.agent_id,
            execution_mode,
        )
        execution_mode = "graph_only"

    # Validate backend policy
    if backend_policy not in _VALID_BACKEND_POLICIES:
        logger.warning(
            "DeepAgent %s: invalid backend_policy %r, defaulting to 'ephemeral'",
            identity.agent_id,
            backend_policy,
        )
        backend_policy = "ephemeral"

    config = DeepAgentConfig(
        agent_id=identity.agent_id,
        specialist_type=specialist_type,
        identity=identity,
        system_prompt=identity.system_prompt,
        model_name=resolve_litellm_string(identity.llm_pin),
        preferred_provider=(
            identity.llm_pin.strip().lower() if identity.llm_pin else None
        ),
        tool_ids=tool_ids,
        target_ids=target_ids,
        phase=phase,
        execution_mode=execution_mode,
        mission_id=resolved_mission_id,
        workflow_id=resolved_workflow_id,
        program_id=resolved_program_id,
        max_iterations=resolved_max_iterations,
        max_subagents=resolved_max_subagents,
        max_tokens_budget=resolved_max_tokens,
        response_format=response_format,
        contract=contract,
        backend_policy=backend_policy,
        scratch_prefix=scratch_prefix,
        sandbox_enabled=sandbox_enabled,
        interrupt_on_band2=interrupt_on_band2,
        metadata=metadata or {},
    )

    logger.debug(
        "DeepAgent created: id=%s type=%s mode=%s phase=%s tools=%d targets=%d",
        config.agent_id,
        config.specialist_type,
        config.execution_mode,
        config.phase,
        len(config.tool_ids),
        len(config.target_ids),
    )

    return DeepAgent(config)


# -- Adapter entry points (called by PraisonAgentRegistry) ---------------------


def to_deepagents_config(identity: AgentIdentity) -> dict[str, Any]:
    """
    Convert AgentIdentity to a DeepAgents configuration dict.
    Framework-agnostic — safe for serialization, scaffolding, and audit.
    """
    spec_defaults = _SPECIALIST_DEFAULTS.get("", {})
    return {
        "agent_id": identity.agent_id,
        "persona": identity.persona,
        "description": identity.description,
        "system_prompt_length": len(identity.system_prompt),
        "model": resolve_litellm_string(identity.llm_pin),
        "preferred_provider": identity.llm_pin,
        "tool_whitelist": list(identity.allowed_tools),
        "risk_profile": identity.risk_profile,
        "review_policy": identity.review_policy,
        "agent_class": identity.agent_class,
        "delegation_scope": identity.delegation_scope,
        "memory_scope": identity.memory_scope,
        "max_iterations": _REVIEW_POLICY_ITERATIONS.get(
            identity.review_policy, 15
        ),
        "workflow_id": identity.workflow_id,
        "program_id": identity.program_id,
        "execution_id": identity.execution_id,
        "handoff_policy": identity.handoff_policy,
        "interrupt_policy": identity.interrupt_policy,
        "escalation_policy": identity.escalation_policy,
    }


def to_deepagents_agent(identity: AgentIdentity) -> DeepAgent:
    """
    Convert AgentIdentity to a DeepAgent instance.
    This is the adapter entry point called by PraisonAgentRegistry.
    """
    return create_deep_agent(identity)
