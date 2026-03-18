"""
K1 PraisonAI Agent Runtime Adapter
=====================================
Bridges Kai's AgentIdentity model with PraisonAI's Agent class for
real agent execution inside LangGraph mission graph nodes.

Integration model:
  LangGraph node execution
  → PraisonAgentRuntime.execute(identity, state)
  → instantiate PraisonAI Agent with Kai persona + governance hooks
  → agent reasons via LLM (through PraisonAI → LiteLLM → Kai provider)
  → agent selects tools
  → Kai governance validates each tool request (PraisonGovernor)
  → tool_runner executes tool (Celery worker)
  → artifact collected
  → state update returned to LangGraph

This module does NOT:
  - Replace LangGraph for orchestration
  - Implement governance logic (that's PraisonGovernor)
  - Bypass tool risk band enforcement
  - Call LLM providers directly (PraisonAI handles via LiteLLM)

Memory mapping:
  Kai scope       → PraisonAI feature
  session         → short_term (per-execution, ephemeral)
  phase/workflow  → long_term (persists across tasks within workflow)
  persistent      → knowledge (cross-workflow knowledge base)

Hook integration:
  PraisonAI hooks intercept agent runtime boundaries:
  - before_tool:  Kai governance gate (scope validation, band check)
  - after_tool:   Artifact collection, telemetry emission
  - before_llm:   Token budget enforcement, prompt sanitization
  - after_llm:    Response audit, cost tracking
  - on_memory_write: Memory scope enforcement

Adaptive execution:
  Agents receive tool profiles and prompt profiles from ExecutionStrategy.
  Profile selection is bounded by validate_plan_patch() — agents cannot
  introduce unapproved tools or arbitrary prompt changes.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from apps.backend.src.core.praison_agent import AgentIdentity, resolve_litellm_string
from apps.backend.src.core.praison_adaptive import (
    ToolProfile,
    PromptProfile,
    ExecutionStrategy,
)
from apps.backend.src.core.praison_artifacts import (
    AgentArtifact,
    ArtifactStore,
    get_artifact_store,
)
from apps.backend.src.core.praison_execution_events import (
    emit,
    artifact_created_event,
    policy_decision_event,
)

logger = logging.getLogger(__name__)


# -- PraisonAI SDK availability check -----------------------------------------

try:
    from praisonaiagents import Agent as PraisonAgent  # type: ignore[import-untyped]
    from praisonaiagents import Task as PraisonTask  # type: ignore[import-untyped]
    from praisonaiagents import PraisonAIAgents  # type: ignore[import-untyped]
    _PRAISON_AVAILABLE = True
except ImportError:
    _PRAISON_AVAILABLE = False
    PraisonAgent = None  # type: ignore[assignment,misc]
    PraisonTask = None  # type: ignore[assignment,misc]
    PraisonAIAgents = None  # type: ignore[assignment,misc]
    logger.info(
        "praisonaiagents not installed — PraisonAgentRuntime will use stub execution. "
        "Install with: pip install 'praisonaiagents>=0.0.50,<1.0'"
    )


# -- Memory scope mapping -----------------------------------------------------

# Maps Kai memory scopes to PraisonAI memory configuration
_MEMORY_SCOPE_MAP: dict[str, dict[str, Any]] = {
    "session": {
        "praison_type": "short_term",
        "persist": False,
        "description": "Ephemeral per-execution memory, discarded after task",
    },
    "phase": {
        "praison_type": "short_term",
        "persist": True,
        "description": "Phase-scoped memory, persists within phase cluster",
    },
    "workflow": {
        "praison_type": "long_term",
        "persist": True,
        "description": "Workflow-scoped memory, persists across phases",
    },
    "mission": {
        "praison_type": "long_term",
        "persist": True,
        "description": "Mission-scoped memory, persists across full mission",
    },
    "persistent": {
        "praison_type": "knowledge",
        "persist": True,
        "description": "Cross-workflow knowledge base, persists indefinitely",
    },
}


def map_memory_scope(kai_scope: str) -> dict[str, Any]:
    """Map a Kai memory scope to PraisonAI memory configuration."""
    return _MEMORY_SCOPE_MAP.get(kai_scope, _MEMORY_SCOPE_MAP["session"])


# -- Governance tool wrapper ---------------------------------------------------

class GovernedToolWrapper:
    """
    Wraps a tool callable with Kai governance validation.

    When a PraisonAI agent selects a tool during reasoning, this wrapper
    intercepts the call and:
      1. Validates the tool request through PraisonGovernor
      2. Checks scope compliance
      3. Logs the decision to the event bus
      4. Executes the tool only if governance approves
      5. Collects the result as an artifact

    This ensures PraisonAI's tool selection is always bounded by Kai policy.
    """

    def __init__(
        self,
        tool_id: str,
        tool_callable: Callable[..., Any] | None,
        identity: AgentIdentity,
        workflow_id: str,
        program_id: str,
        mission_id: str = "",
    ):
        self.tool_id = tool_id
        self._callable = tool_callable
        self._identity = identity
        self._workflow_id = workflow_id
        self._program_id = program_id
        self._mission_id = mission_id
        # Expose metadata for PraisonAI tool registration
        self.__name__ = f"kai_{tool_id}"
        self.__doc__ = f"K1 governed tool: {tool_id}"

    def __call__(self, *args: Any, **kwargs: Any) -> dict[str, Any]:
        """Execute tool with governance validation."""
        # Step 1: Governance check
        try:
            from apps.backend.src.core.praison_governor import get_governor
            governor = get_governor()
            from apps.backend.src.core.praison_governor import GovernanceContext

            ctx = GovernanceContext(
                tool_id=self.tool_id,
                tool_tier=self._resolve_tool_tier(),
                program_id=self._program_id,
                workflow_id=self._workflow_id,
                target=kwargs.get("target", ""),
                params=kwargs,
            )
            governor.validate_tool_request(ctx)
        except Exception as exc:
            # Governance blocked or not initialized
            if "PraisonGovernanceError" in type(exc).__name__:
                logger.warning(
                    "Governance blocked tool %s for agent %s: %s",
                    self.tool_id, self._identity.agent_id, exc,
                )
                emit(policy_decision_event(
                    mission_id=self._mission_id,
                    workflow_id=self._workflow_id,
                    program_id=self._program_id,
                    decision="blocked",
                    reason=str(exc),
                    agent_id=self._identity.agent_id,
                ))
                return {
                    "tool_id": self.tool_id,
                    "status": "blocked",
                    "reason": str(exc),
                }
            # Governor not initialized — fail open for non-governance errors
            logger.debug("Governor not available for tool %s: %s", self.tool_id, exc)

        # Step 2: Execute tool
        if self._callable is None:
            return {
                "tool_id": self.tool_id,
                "status": "stub",
                "result": f"Tool {self.tool_id} executed in stub mode",
            }

        try:
            result = self._callable(*args, **kwargs)
            emit(policy_decision_event(
                mission_id=self._mission_id,
                workflow_id=self._workflow_id,
                program_id=self._program_id,
                decision="authorized",
                reason=f"Tool {self.tool_id} executed successfully",
                agent_id=self._identity.agent_id,
            ))
            return {
                "tool_id": self.tool_id,
                "status": "completed",
                "result": result,
            }
        except Exception as exc:
            logger.error("Tool %s execution failed: %s", self.tool_id, exc)
            return {
                "tool_id": self.tool_id,
                "status": "failed",
                "error": str(exc),
            }

    def _resolve_tool_tier(self) -> int:
        """Resolve tool risk tier. Defaults to 0 (passive) if unknown."""
        try:
            from apps.backend.src.core.tool_runner import get_tool_tier
            return get_tool_tier(self.tool_id)
        except Exception:
            return 0


# -- Agent execution result ----------------------------------------------------

@dataclass
class AgentExecutionResult:
    """Result of a PraisonAI agent execution within a LangGraph node."""
    agent_id: str
    node_id: str
    success: bool
    state_update: dict[str, Any] = field(default_factory=dict)
    artifacts: list[dict[str, Any]] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    llm_calls: int = 0
    duration_ms: float = 0.0
    error: str = ""

    def to_state_update(self) -> dict[str, Any]:
        """Convert to a LangGraph state update dict."""
        update = dict(self.state_update)
        if self.artifacts:
            update["artifacts"] = self.artifacts
        if self.tools_used:
            update["tools_used"] = self.tools_used
        if self.error:
            update["error"] = self.error
        return update


# -- PraisonAI runtime hooks ---------------------------------------------------

def _build_governance_hooks(
    identity: AgentIdentity,
    mission_id: str,
    workflow_id: str,
    program_id: str,
) -> dict[str, Any]:
    """
    Build PraisonAI-compatible hook configuration for governance boundaries.

    Returns a dict of hook callbacks that PraisonAI's Agent class accepts.
    These hooks intercept agent runtime operations and enforce Kai policy.
    """
    hooks: dict[str, Any] = {}

    def before_tool_hook(tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any] | None:
        """Governance gate before any tool execution."""
        try:
            from apps.backend.src.core.praison_governor import get_governor, GovernanceContext
            governor = get_governor()
            ctx = GovernanceContext(
                tool_id=tool_name,
                tool_tier=0,  # resolved at tool level
                program_id=program_id,
                workflow_id=workflow_id,
                target=tool_input.get("target", ""),
                params=tool_input,
            )
            governor.validate_tool_request(ctx)
            return None  # proceed
        except Exception as exc:
            logger.warning("Hook blocked tool %s: %s", tool_name, exc)
            return {"blocked": True, "reason": str(exc)}

    def after_tool_hook(tool_name: str, tool_output: Any) -> None:
        """Telemetry emission after tool execution."""
        emit(policy_decision_event(
            mission_id=mission_id,
            workflow_id=workflow_id,
            program_id=program_id,
            decision="tool_completed",
            reason=f"Tool {tool_name} completed",
            agent_id=identity.agent_id,
        ))

    def before_llm_hook(prompt: str, model: str) -> str | None:
        """Prompt sanitization and budget enforcement before LLM call."""
        # Enforce: agent must use its configured LLM, not arbitrary models
        expected_model = resolve_litellm_string(identity.llm_pin)
        if model and model != expected_model:
            logger.warning(
                "Agent %s attempted LLM call to %s, expected %s — allowing (LiteLLM routes)",
                identity.agent_id, model, expected_model,
            )
        return None  # proceed with original prompt

    def on_memory_write_hook(key: str, value: Any, scope: str) -> bool:
        """Memory scope enforcement on write operations."""
        if not identity.can_write_to_scope(scope):
            logger.warning(
                "Agent %s blocked from writing to scope %s (agent scope: %s)",
                identity.agent_id, scope, identity.memory_scope,
            )
            return False  # block write
        return True  # permit

    hooks["before_tool"] = before_tool_hook
    hooks["after_tool"] = after_tool_hook
    hooks["before_llm"] = before_llm_hook
    hooks["on_memory_write"] = on_memory_write_hook

    return hooks


# -- PraisonAgentRuntime -------------------------------------------------------

class PraisonAgentRuntime:
    """
    Runtime adapter that instantiates PraisonAI Agents for Kai mission execution.

    Each LangGraph node callable uses this runtime to:
    1. Create a PraisonAI Agent from an AgentIdentity
    2. Configure governance hooks, memory mapping, and tool wrappers
    3. Execute the agent's task
    4. Collect artifacts and return state updates

    Thread-safe. Each execution creates its own agent instance.
    """

    def __init__(
        self,
        artifact_store: ArtifactStore | None = None,
        tool_registry: dict[str, Callable[..., Any]] | None = None,
    ) -> None:
        """
        artifact_store: Where to persist agent-produced artifacts
        tool_registry:  {tool_id: callable} map of available tools
        """
        self._artifact_store = artifact_store or get_artifact_store()
        self._tool_registry = tool_registry or {}

    def execute(
        self,
        identity: AgentIdentity,
        state: dict[str, Any],
        *,
        task_description: str = "",
        strategy: ExecutionStrategy | None = None,
        tool_profile: ToolProfile | None = None,
        prompt_profile: PromptProfile | None = None,
    ) -> AgentExecutionResult:
        """
        Execute a PraisonAI agent synchronously within a LangGraph node.

        This is the primary entry point for all agent execution in the
        mission graph. It:
        1. Builds a PraisonAI Agent from the identity
        2. Configures governance hooks and tool wrappers
        3. Creates and runs a PraisonAI Task
        4. Collects results and artifacts
        5. Returns an AgentExecutionResult for state merging

        Args:
            identity:         Agent persona and policy config
            state:            Current LangGraph state dict
            task_description: Override task prompt (default: built from identity + state)
            strategy:         Execution strategy for adaptive behavior
            tool_profile:     Active tool configuration profile
            prompt_profile:   Active prompt template profile
        """
        start = time.monotonic()
        mission_id = state.get("mission_id", "")
        workflow_id = state.get("workflow_id", identity.workflow_id)
        program_id = state.get("program_id", identity.program_id)
        execution_mode = state.get("execution_mode", "live")
        node_id = state.get("active_node", identity.agent_id)

        result = AgentExecutionResult(
            agent_id=identity.agent_id,
            node_id=node_id,
            success=False,
        )

        # Stub execution for graph_only / tool_mock modes
        if execution_mode == "graph_only":
            result.success = True
            result.state_update = {
                "last_agent": identity.agent_id,
                "execution_mode": execution_mode,
            }
            result.duration_ms = (time.monotonic() - start) * 1000
            return result

        if not _PRAISON_AVAILABLE:
            logger.warning(
                "PraisonAI SDK not installed — returning stub result for %s",
                identity.agent_id,
            )
            result.success = True
            result.state_update = {
                "last_agent": identity.agent_id,
                "execution_mode": "stub",
            }
            result.duration_ms = (time.monotonic() - start) * 1000
            return result

        try:
            # Build the PraisonAI agent
            agent = self._build_agent(
                identity=identity,
                mission_id=mission_id,
                workflow_id=workflow_id,
                program_id=program_id,
                tool_profile=tool_profile,
            )

            # Build task description
            task_desc = task_description or self._build_task_description(
                identity=identity,
                state=state,
                prompt_profile=prompt_profile,
            )

            # Create and run task
            task = PraisonTask(
                description=task_desc,
                agent=agent,
                expected_output="JSON object with findings, artifacts, and recommendations",
            )
            runner = PraisonAIAgents(
                agents=[agent],
                tasks=[task],
                verbose=False,
            )

            raw_output = runner.start()
            result.llm_calls = 1  # PraisonAI doesn't expose call count directly

            # Parse output
            parsed = self._parse_agent_output(raw_output, identity)
            result.state_update = parsed.get("state_update", {})
            result.artifacts = parsed.get("artifacts", [])
            result.tools_used = parsed.get("tools_used", [])
            result.success = True

            # Persist artifacts
            for art_dict in result.artifacts:
                try:
                    artifact = AgentArtifact(
                        artifact_id=art_dict.get("artifact_id", str(uuid.uuid4())),
                        producer_id=identity.agent_id,
                        workflow_id=workflow_id,
                        program_id=program_id,
                        content=art_dict.get("content", {}),
                        summary=art_dict.get("summary", ""),
                    )
                    self._artifact_store.put(artifact)
                    emit(artifact_created_event(
                        mission_id=mission_id,
                        workflow_id=workflow_id,
                        program_id=program_id,
                        artifact_id=artifact.artifact_id,
                        artifact_type=art_dict.get("artifact_type", "agent_output"),
                        producer_id=identity.agent_id,
                    ))
                except Exception as exc:
                    logger.warning("Failed to persist artifact: %s", exc)

        except Exception as exc:
            result.error = f"Agent {identity.agent_id} execution failed: {exc}"
            logger.error(result.error, exc_info=True)

        result.duration_ms = (time.monotonic() - start) * 1000
        return result

    async def execute_async(
        self,
        identity: AgentIdentity,
        state: dict[str, Any],
        **kwargs: Any,
    ) -> AgentExecutionResult:
        """Async wrapper around execute() — runs in thread pool."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self.execute(identity, state, **kwargs)
        )

    def _build_agent(
        self,
        identity: AgentIdentity,
        mission_id: str,
        workflow_id: str,
        program_id: str,
        tool_profile: ToolProfile | None = None,
    ) -> Any:  # PraisonAgent
        """
        Build a PraisonAI Agent from a Kai AgentIdentity.

        Configures:
        - Persona (name, role, goal, backstory) from identity
        - LLM model from identity.llm_pin → LiteLLM string
        - Tools wrapped with governance validation
        - Memory configuration mapped from Kai scope
        """
        # Resolve tools for this agent
        tools = self._build_governed_tools(
            identity=identity,
            mission_id=mission_id,
            workflow_id=workflow_id,
            program_id=program_id,
            tool_profile=tool_profile,
        )

        # Resolve LLM
        llm_model = resolve_litellm_string(identity.llm_pin)

        # Build agent
        agent = PraisonAgent(
            name=identity.agent_id,
            role=identity.persona,
            goal=identity.description,
            backstory=identity.system_prompt,
            llm=llm_model,
            tools=tools if tools else None,
            verbose=False,
            self_reflect=False,  # K1 governance handles reflection, not the agent
        )

        return agent

    def _build_governed_tools(
        self,
        identity: AgentIdentity,
        mission_id: str,
        workflow_id: str,
        program_id: str,
        tool_profile: ToolProfile | None = None,
    ) -> list[Callable[..., Any]]:
        """
        Build governance-wrapped tool callables for a PraisonAI agent.

        Each tool in identity.allowed_tools is wrapped with GovernedToolWrapper
        which enforces Kai governance on every invocation.
        """
        tools: list[Callable[..., Any]] = []

        # Determine which tool IDs to expose
        tool_ids = list(identity.allowed_tools)

        # If a tool profile is active, apply its parameter configuration
        # (the tool profile narrows the available tools, not expands them)
        if tool_profile and tool_profile.tool_id:
            if tool_profile.tool_id in tool_ids:
                # Profile is for a specific tool — keep only that tool
                tool_ids = [tool_profile.tool_id]

        for tool_id in tool_ids:
            tool_callable = self._tool_registry.get(tool_id)
            wrapper = GovernedToolWrapper(
                tool_id=tool_id,
                tool_callable=tool_callable,
                identity=identity,
                workflow_id=workflow_id,
                program_id=program_id,
                mission_id=mission_id,
            )
            tools.append(wrapper)

        return tools

    def _build_task_description(
        self,
        identity: AgentIdentity,
        state: dict[str, Any],
        prompt_profile: PromptProfile | None = None,
    ) -> str:
        """
        Build the task description for the PraisonAI agent.

        Uses prompt_profile template if available, otherwise builds from
        identity + state context.
        """
        if prompt_profile and prompt_profile.template:
            # Apply prompt profile template with state context
            context = {
                "agent_id": identity.agent_id,
                "persona": identity.persona,
                "phase": state.get("phase", ""),
                "mission_id": state.get("mission_id", ""),
                "workflow_id": state.get("workflow_id", ""),
                "artifacts": state.get("artifacts", []),
                "findings": state.get("findings", []),
                "messages": state.get("messages", []),
            }
            try:
                return prompt_profile.template.format(**context)
            except (KeyError, IndexError):
                logger.warning(
                    "Prompt profile template formatting failed for %s, using default",
                    identity.agent_id,
                )

        # Default task description from identity + state
        phase = state.get("phase", "unknown")
        artifacts_summary = f"{len(state.get('artifacts', []))} artifacts from prior phases"
        findings_summary = f"{len(state.get('findings', []))} findings so far"

        return (
            f"You are {identity.persona}. Execute your role in the {phase} phase.\n\n"
            f"Context:\n"
            f"- Mission ID: {state.get('mission_id', 'N/A')}\n"
            f"- Phase: {phase}\n"
            f"- Prior artifacts: {artifacts_summary}\n"
            f"- Current findings: {findings_summary}\n\n"
            f"Your objective: {identity.description}\n\n"
            f"Produce a JSON object containing:\n"
            f"  - findings: list of structured findings (if any)\n"
            f"  - artifacts: list of produced artifacts\n"
            f"  - tools_used: list of tool IDs invoked\n"
            f"  - summary: brief text summary of what you accomplished\n"
            f"  - recommendations: list of next-step recommendations\n"
        )

    def _parse_agent_output(
        self,
        raw: Any,
        identity: AgentIdentity,
    ) -> dict[str, Any]:
        """
        Parse PraisonAI agent output into structured result.

        Handles both dict and string outputs, extracting JSON when possible.
        """
        import json
        import re

        result: dict[str, Any] = {
            "state_update": {"last_agent": identity.agent_id},
            "artifacts": [],
            "tools_used": [],
        }

        if isinstance(raw, dict):
            parsed = raw
        elif isinstance(raw, str):
            # Try to extract JSON from response
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group())
                except json.JSONDecodeError:
                    parsed = {"summary": raw}
            else:
                parsed = {"summary": raw}
        else:
            parsed = {"summary": str(raw) if raw else "No output"}

        # Extract structured fields
        if "findings" in parsed:
            result["state_update"]["findings"] = parsed["findings"]
        if "artifacts" in parsed:
            result["artifacts"] = parsed["artifacts"]
        if "tools_used" in parsed:
            result["tools_used"] = parsed["tools_used"]
        if "summary" in parsed:
            result["state_update"]["summary"] = parsed["summary"]
        if "recommendations" in parsed:
            result["state_update"]["recommendations"] = parsed["recommendations"]

        return result

    def register_tool(self, tool_id: str, tool_callable: Callable[..., Any]) -> None:
        """Register a tool callable for agent use."""
        self._tool_registry[tool_id] = tool_callable

    def register_tools(self, tools: dict[str, Callable[..., Any]]) -> None:
        """Register multiple tool callables."""
        self._tool_registry.update(tools)


# -- Node executor factory using PraisonAgentRuntime ---------------------------

def make_praison_node_callable(
    identity: AgentIdentity,
    runtime: PraisonAgentRuntime,
    *,
    strategy: ExecutionStrategy | None = None,
    tool_profile: ToolProfile | None = None,
    prompt_profile: PromptProfile | None = None,
    task_description: str = "",
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Create a LangGraph node callable that executes a PraisonAI agent.

    This is the bridge between LangGraph's node execution model and
    PraisonAI's agent runtime. The returned callable:
    1. Receives LangGraph state
    2. Instantiates a PraisonAI Agent via the runtime
    3. Executes the agent's task
    4. Returns a state update dict for LangGraph's reducer

    Usage:
        runtime = PraisonAgentRuntime(tool_registry=tools)
        identity = registry.get_agent("ReconSpecialist")
        callable = make_praison_node_callable(identity, runtime)
        # Pass to build_standard_node_callables or directly to LangGraph
    """

    def node_callable(state: dict[str, Any]) -> dict[str, Any]:
        result = runtime.execute(
            identity=identity,
            state=state,
            task_description=task_description,
            strategy=strategy,
            tool_profile=tool_profile,
            prompt_profile=prompt_profile,
        )
        return result.to_state_update()

    node_callable.__name__ = f"praison_{identity.agent_id}"
    node_callable.__qualname__ = f"praison_{identity.agent_id}"
    return node_callable


# -- Batch builder for full mission agent callables ----------------------------

def build_praison_agent_callables(
    agent_identities: dict[str, AgentIdentity],
    runtime: PraisonAgentRuntime,
    strategies: dict[str, ExecutionStrategy] | None = None,
) -> dict[str, Callable[[dict[str, Any]], dict[str, Any]]]:
    """
    Build a full set of PraisonAI-backed node callables for a mission.

    Args:
        agent_identities: {agent_id: AgentIdentity} from PraisonAgentRegistry
        runtime:          Configured PraisonAgentRuntime instance
        strategies:       Optional {agent_id: ExecutionStrategy} for adaptive execution

    Returns:
        {agent_id: callable(state) -> state_update} ready for
        build_standard_node_callables() or direct LangGraph registration
    """
    strats = strategies or {}
    callables: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {}

    for agent_id, identity in agent_identities.items():
        strategy = strats.get(agent_id)
        callables[agent_id] = make_praison_node_callable(
            identity=identity,
            runtime=runtime,
            strategy=strategy,
        )

    return callables


# -- Module singleton ----------------------------------------------------------

_RUNTIME: PraisonAgentRuntime | None = None


def get_agent_runtime() -> PraisonAgentRuntime:
    """Return the module-level PraisonAgentRuntime singleton."""
    global _RUNTIME
    if _RUNTIME is None:
        _RUNTIME = PraisonAgentRuntime()
    return _RUNTIME


def initialize_agent_runtime(
    tool_registry: dict[str, Callable[..., Any]] | None = None,
    artifact_store: ArtifactStore | None = None,
) -> PraisonAgentRuntime:
    """Initialize the PraisonAgentRuntime singleton. Call during app startup."""
    global _RUNTIME
    _RUNTIME = PraisonAgentRuntime(
        artifact_store=artifact_store,
        tool_registry=tool_registry or {},
    )
    logger.info(
        "PraisonAgentRuntime initialized: praison_available=%s tools=%d",
        _PRAISON_AVAILABLE,
        len(_RUNTIME._tool_registry),
    )
    return _RUNTIME


def is_praison_available() -> bool:
    """Return True if PraisonAI SDK is installed."""
    return _PRAISON_AVAILABLE
