"""
LangChain Reasoning Helpers (Phase 5)
=======================================
Node-local reasoning primitives powered by LangChain.

These helpers are invoked from within LangGraph node executors to perform
short-horizon cognitive tasks: summarizing artifacts, classifying findings,
generating evidence digests, ranking tools, and producing structured outputs.

Design principles:
  - Never mutate global mission state directly
  - Never bypass plan patch validation
  - Always return typed structured outputs (via langchain_schemas)
  - Simulation-ready: execution_mode="tool_mock" returns deterministic fixtures
  - All calls are correlated to mission/node via middleware callbacks
  - Graceful fallback if LangChain unavailable
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional LangChain import — degrade gracefully if not installed
# ---------------------------------------------------------------------------
try:
    from langchain_core.messages import HumanMessage, SystemMessage
    from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_core.runnables import RunnableConfig

    _LANGCHAIN_AVAILABLE = True
except ImportError:  # pragma: no cover
    _LANGCHAIN_AVAILABLE = False
    logger.warning(
        "langchain_core is not installed — K1ReasoningEngine will not be available. "
        "Install langchain-core>=0.1 to enable LangChain reasoning integration."
    )

# ---------------------------------------------------------------------------
# Platform imports
# ---------------------------------------------------------------------------
from apps.backend.src.core.langchain_model_factory import (
    K1ModelFactory,
    get_model_factory,
)
from apps.backend.src.core.langchain_middleware import K1MiddlewareStack, make_middleware_stack
from apps.backend.src.core.langchain_tool_registry import (
    K1LangChainToolRegistry,
    get_tool_registry,
)
from apps.backend.src.core.langchain_schemas import (
    EvidenceSummary,
    NodeReasoningRequest,
    NodeReasoningResult,
    PromptProfileRecommendation,
    SeverityLevel,
    ToolSelectionRationale,
    TriageResult,
)


# ---------------------------------------------------------------------------
# K1ReasoningEngine
# ---------------------------------------------------------------------------


class K1ReasoningEngine:
    """
    Node-local LangChain-powered reasoning helpers.

    Used by LangGraph node executors to perform short cognitive tasks
    without becoming a mission orchestrator.

    All methods:
    - Accept a NodeReasoningRequest for context
    - Return a NodeReasoningResult with typed output
    - Support execution_mode="tool_mock" returning fixture data
    - Emit telemetry events via middleware callbacks
    """

    def __init__(
        self,
        model_factory: K1ModelFactory | None = None,
        tool_registry: K1LangChainToolRegistry | None = None,
        event_bus: Any = None,
    ) -> None:
        # Lazily resolved if not provided at construction time
        self._model_factory = model_factory
        self._tool_registry = tool_registry
        self._event_bus = event_bus

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_model_factory(self) -> K1ModelFactory:
        """Return the model factory, resolving the module singleton lazily."""
        if self._model_factory is None:
            self._model_factory = get_model_factory()
        return self._model_factory

    def _get_tool_registry(self) -> K1LangChainToolRegistry:
        """Return the tool registry, resolving the module singleton lazily."""
        if self._tool_registry is None:
            self._tool_registry = get_tool_registry()
        return self._tool_registry

    def _make_middleware(self, request: NodeReasoningRequest) -> K1MiddlewareStack:
        """Construct a K1MiddlewareStack correlated to the given request."""
        return make_middleware_stack(
            mission_id=request.mission_id,
            workflow_id=request.workflow_id,
            program_id=request.program_id,
            node_id=request.node_id,
            phase=request.phase,
            execution_mode=request.execution_mode,
            event_bus=self._event_bus,
        )

    @staticmethod
    def _is_simulation(execution_mode: str) -> bool:
        """Return True when no LLM call should be made."""
        return execution_mode in ("tool_mock", "graph_only")

    @staticmethod
    def _make_error_result(
        request: NodeReasoningRequest,
        reasoning_type: str,
        error: Exception,
    ) -> NodeReasoningResult:
        """Build a failure NodeReasoningResult from a caught exception."""
        logger.warning(
            "K1ReasoningEngine [%s] mission=%s node=%s: %s",
            reasoning_type,
            request.mission_id,
            request.node_id,
            error,
        )
        return NodeReasoningResult(
            node_id=request.node_id,
            mission_id=request.mission_id,
            success=False,
            reasoning_type=reasoning_type,
            output={},
            tokens_used=0,
            latency_ms=0.0,
            error=str(error),
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def summarize_artifact_bundle(self, request: NodeReasoningRequest) -> NodeReasoningResult:
        """
        Summarize a bundle of artifacts into an EvidenceSummary.

        In simulation modes (tool_mock / graph_only) returns a deterministic
        fixture immediately without invoking the LLM.

        Args:
            request: Full node reasoning context carrying artifacts list.

        Returns:
            NodeReasoningResult with output = EvidenceSummary.model_dump().
        """
        reasoning_type = "evidence_summary"

        # --- Simulation fast-path ---
        if self._is_simulation(request.execution_mode):
            mock = EvidenceSummary(
                findings_count=len(request.artifacts),
                high_confidence_count=max(0, len(request.artifacts) // 3),
                severity_distribution={"medium": len(request.artifacts)},
                top_findings=[],
                affected_targets=["mock_target"],
                signal_strength="medium",
                summary_text="[MOCK] Artifact bundle summarized.",
                artifact_ids_referenced=[],
            )
            return NodeReasoningResult(
                node_id=request.node_id,
                mission_id=request.mission_id,
                success=True,
                reasoning_type=reasoning_type,
                output=mock.model_dump(),
                tokens_used=0,
                latency_ms=0.0,
            )

        # --- Live LLM path ---
        if not _LANGCHAIN_AVAILABLE:
            return self._make_error_result(
                request,
                reasoning_type,
                RuntimeError("langchain_core not installed"),
            )

        try:
            system_prompt = (
                "You are a security analysis engine for the K1 bug bounty platform.\n"
                "Analyze the provided artifacts and produce a structured evidence summary.\n"
                "Focus on: findings count, severity distribution, signal strength, "
                "and key affected targets.\n"
                "Be precise and conservative in severity assessment."
            )
            human_content = json.dumps(request.artifacts, indent=2)

            model = self._get_model_factory().create(mission_id=request.mission_id)
            if model is None:
                return self._make_error_result(
                    request,
                    reasoning_type,
                    RuntimeError("Model factory returned None — LangChain unavailable"),
                )

            middleware = self._make_middleware(request)
            parser = JsonOutputParser()

            prompt = ChatPromptTemplate.from_messages(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(
                        content=human_content
                        + "\n\nReturn a JSON object matching the EvidenceSummary schema."
                    ),
                ]
            )
            chain = prompt | model | StrOutputParser() | parser

            t0 = time.monotonic()
            raw: dict[str, Any] = await chain.ainvoke(
                {},
                config=RunnableConfig(callbacks=middleware.callbacks()),
            )
            latency_ms = (time.monotonic() - t0) * 1000.0

            result = EvidenceSummary.model_validate(raw)
            return NodeReasoningResult(
                node_id=request.node_id,
                mission_id=request.mission_id,
                success=True,
                reasoning_type=reasoning_type,
                output=result.model_dump(),
                tokens_used=0,
                latency_ms=latency_ms,
            )

        except Exception as exc:  # noqa: BLE001
            return self._make_error_result(request, reasoning_type, exc)

    async def classify_finding(
        self,
        request: NodeReasoningRequest,
        finding: dict[str, Any],
    ) -> NodeReasoningResult:
        """
        Classify a single finding into a TriageResult.

        Args:
            request: Node reasoning context.
            finding: Raw finding dict to classify (must contain at minimum
                     'id' and 'title' keys for best results).

        Returns:
            NodeReasoningResult with output = TriageResult.model_dump().
        """
        reasoning_type = "triage"

        # --- Simulation fast-path ---
        if self._is_simulation(request.execution_mode):
            mock = TriageResult(
                finding_id=finding.get("id", "mock"),
                title=finding.get("title", "Mock Finding"),
                severity=SeverityLevel.MEDIUM,
                exploitability="unknown",
                priority=5,
                recommendation="investigate",
                rationale="[MOCK] Triage performed.",
                confidence=0.5,
            )
            return NodeReasoningResult(
                node_id=request.node_id,
                mission_id=request.mission_id,
                success=True,
                reasoning_type=reasoning_type,
                output=mock.model_dump(),
                tokens_used=0,
                latency_ms=0.0,
            )

        # --- Live LLM path ---
        if not _LANGCHAIN_AVAILABLE:
            return self._make_error_result(
                request,
                reasoning_type,
                RuntimeError("langchain_core not installed"),
            )

        try:
            system_prompt = (
                "You are a vulnerability triage specialist for the K1 bug bounty platform.\n"
                "Analyze the provided finding and produce a structured triage decision.\n"
                "Assess: severity, exploitability, priority (1-10), and recommendation.\n"
                "Be precise. Underclaiming is preferred to overclaiming."
            )
            human_content = json.dumps(finding, indent=2)

            model = self._get_model_factory().create(mission_id=request.mission_id)
            if model is None:
                return self._make_error_result(
                    request,
                    reasoning_type,
                    RuntimeError("Model factory returned None — LangChain unavailable"),
                )

            middleware = self._make_middleware(request)
            parser = JsonOutputParser()

            prompt = ChatPromptTemplate.from_messages(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(
                        content=human_content
                        + "\n\nReturn a JSON object matching the TriageResult schema."
                    ),
                ]
            )
            chain = prompt | model | StrOutputParser() | parser

            t0 = time.monotonic()
            raw: dict[str, Any] = await chain.ainvoke(
                {},
                config=RunnableConfig(callbacks=middleware.callbacks()),
            )
            latency_ms = (time.monotonic() - t0) * 1000.0

            result = TriageResult.model_validate(raw)
            return NodeReasoningResult(
                node_id=request.node_id,
                mission_id=request.mission_id,
                success=True,
                reasoning_type=reasoning_type,
                output=result.model_dump(),
                tokens_used=0,
                latency_ms=latency_ms,
            )

        except Exception as exc:  # noqa: BLE001
            return self._make_error_result(request, reasoning_type, exc)

    async def generate_evidence_digest(self, request: NodeReasoningRequest) -> NodeReasoningResult:
        """
        Generate a narrative evidence digest suitable for a report section.

        The digest is plain text (not structured JSON) produced via StrOutputParser.

        Args:
            request: Node reasoning context carrying findings list.

        Returns:
            NodeReasoningResult with output = {"digest": str}.
        """
        reasoning_type = "evidence_digest"

        # --- Simulation fast-path ---
        if self._is_simulation(request.execution_mode):
            mock_text = (
                f"[MOCK] Evidence digest for {len(request.findings)} findings "
                f"in phase {request.phase}."
            )
            return NodeReasoningResult(
                node_id=request.node_id,
                mission_id=request.mission_id,
                success=True,
                reasoning_type=reasoning_type,
                output={"digest": mock_text},
                tokens_used=0,
                latency_ms=0.0,
            )

        # --- Live LLM path ---
        if not _LANGCHAIN_AVAILABLE:
            return self._make_error_result(
                request,
                reasoning_type,
                RuntimeError("langchain_core not installed"),
            )

        try:
            system_prompt = (
                "You are a security report writer for the K1 bug bounty platform.\n"
                "Generate a concise technical evidence digest from the provided findings.\n"
                "The digest should be suitable for inclusion in a technical security report.\n"
                "Write clearly and precisely. Focus on confirmed findings only."
            )
            human_content = json.dumps(request.findings, indent=2)

            model = self._get_model_factory().create(mission_id=request.mission_id)
            if model is None:
                return self._make_error_result(
                    request,
                    reasoning_type,
                    RuntimeError("Model factory returned None — LangChain unavailable"),
                )

            middleware = self._make_middleware(request)
            str_parser = StrOutputParser()

            prompt = ChatPromptTemplate.from_messages(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=human_content),
                ]
            )
            chain = prompt | model | str_parser

            t0 = time.monotonic()
            digest: str = await chain.ainvoke(
                {},
                config=RunnableConfig(callbacks=middleware.callbacks()),
            )
            latency_ms = (time.monotonic() - t0) * 1000.0

            return NodeReasoningResult(
                node_id=request.node_id,
                mission_id=request.mission_id,
                success=True,
                reasoning_type=reasoning_type,
                output={"digest": digest},
                tokens_used=0,
                latency_ms=latency_ms,
            )

        except Exception as exc:  # noqa: BLE001
            return self._make_error_result(request, reasoning_type, exc)

    async def rank_candidate_tools(self, request: NodeReasoningRequest) -> NodeReasoningResult:
        """
        Rank available tools from request.available_tools for the current mission context.

        Args:
            request: Node reasoning context; request.available_tools carries
                     the tool IDs eligible for ranking.

        Returns:
            NodeReasoningResult with output = {"rankings": [ToolSelectionRationale.model_dump()]}.
        """
        reasoning_type = "tool_selection"

        # --- Simulation fast-path ---
        if self._is_simulation(request.execution_mode):
            rankings = [
                ToolSelectionRationale(
                    tool_id=t,
                    tool_name=t,
                    category="unknown",
                    reason="[MOCK]",
                    expected_output_types=[],
                    confidence=0.5,
                ).model_dump()
                for t in request.available_tools
            ]
            return NodeReasoningResult(
                node_id=request.node_id,
                mission_id=request.mission_id,
                success=True,
                reasoning_type=reasoning_type,
                output={"rankings": rankings},
                tokens_used=0,
                latency_ms=0.0,
            )

        # --- Live LLM path ---
        if not _LANGCHAIN_AVAILABLE:
            return self._make_error_result(
                request,
                reasoning_type,
                RuntimeError("langchain_core not installed"),
            )

        try:
            system_prompt = (
                "You are a tool selection engine for the K1 bug bounty platform.\n"
                "Given the current mission context and available tools, rank them by utility.\n"
                "Consider: target type, mission phase, tool capabilities, and safety constraints.\n"
                "Return a ranked list of tool selection rationales."
            )
            context_payload = {
                "mission_id": request.mission_id,
                "phase": request.phase,
                "available_tools": request.available_tools,
                "task_description": request.task_description,
                "system_context": request.system_context,
            }
            human_content = json.dumps(context_payload, indent=2)

            model = self._get_model_factory().create(mission_id=request.mission_id)
            if model is None:
                return self._make_error_result(
                    request,
                    reasoning_type,
                    RuntimeError("Model factory returned None — LangChain unavailable"),
                )

            middleware = self._make_middleware(request)
            parser = JsonOutputParser()

            prompt = ChatPromptTemplate.from_messages(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(
                        content=human_content
                        + "\n\nReturn a JSON object with key 'rankings' containing "
                        "a list of ToolSelectionRationale objects."
                    ),
                ]
            )
            chain = prompt | model | StrOutputParser() | parser

            t0 = time.monotonic()
            raw: dict[str, Any] = await chain.ainvoke(
                {},
                config=RunnableConfig(callbacks=middleware.callbacks()),
            )
            latency_ms = (time.monotonic() - t0) * 1000.0

            # Validate each ranking entry against the schema
            raw_rankings: list[dict[str, Any]] = raw.get("rankings", [])
            validated: list[dict[str, Any]] = []
            for item in raw_rankings:
                try:
                    validated.append(ToolSelectionRationale.model_validate(item).model_dump())
                except Exception:  # noqa: BLE001
                    # Skip malformed entries rather than failing the whole call
                    logger.warning(
                        "rank_candidate_tools: skipping malformed ranking entry: %s", item
                    )

            return NodeReasoningResult(
                node_id=request.node_id,
                mission_id=request.mission_id,
                success=True,
                reasoning_type=reasoning_type,
                output={"rankings": validated},
                tokens_used=0,
                latency_ms=latency_ms,
            )

        except Exception as exc:  # noqa: BLE001
            return self._make_error_result(request, reasoning_type, exc)

    async def select_prompt_profile(
        self,
        request: NodeReasoningRequest,
        candidate_profiles: list[dict[str, Any]],
    ) -> NodeReasoningResult:
        """
        Select the best prompt profile from a list of candidates.

        Args:
            request: Node reasoning context.
            candidate_profiles: List of profile dicts (each should have at minimum
                                a 'profile_id' key).

        Returns:
            NodeReasoningResult with output = PromptProfileRecommendation.model_dump().
        """
        reasoning_type = "prompt_profile_selection"

        # --- Simulation fast-path ---
        if self._is_simulation(request.execution_mode):
            if candidate_profiles:
                mock = PromptProfileRecommendation(
                    profile_id=candidate_profiles[0].get("profile_id", "mock"),
                    profile_type="prompt_profile",
                    reason="[MOCK]",
                    confidence=0.5,
                    based_on_executions=0,
                )
            else:
                mock = PromptProfileRecommendation(
                    profile_id="mock",
                    profile_type="prompt_profile",
                    reason="[MOCK] No candidates provided.",
                    confidence=0.0,
                    based_on_executions=0,
                )
            return NodeReasoningResult(
                node_id=request.node_id,
                mission_id=request.mission_id,
                success=True,
                reasoning_type=reasoning_type,
                output=mock.model_dump(),
                tokens_used=0,
                latency_ms=0.0,
            )

        # --- Live LLM path ---
        if not _LANGCHAIN_AVAILABLE:
            return self._make_error_result(
                request,
                reasoning_type,
                RuntimeError("langchain_core not installed"),
            )

        try:
            system_prompt = (
                "You are a prompt profile optimizer for the K1 bug bounty platform.\n"
                "Select the best prompt profile for the current mission context.\n"
                "Consider: phase appropriateness, historical performance, and task alignment."
            )
            context_payload = {
                "mission_id": request.mission_id,
                "phase": request.phase,
                "task_description": request.task_description,
                "system_context": request.system_context,
                "candidate_profiles": candidate_profiles,
            }
            human_content = json.dumps(context_payload, indent=2)

            model = self._get_model_factory().create(mission_id=request.mission_id)
            if model is None:
                return self._make_error_result(
                    request,
                    reasoning_type,
                    RuntimeError("Model factory returned None — LangChain unavailable"),
                )

            middleware = self._make_middleware(request)
            parser = JsonOutputParser()

            prompt = ChatPromptTemplate.from_messages(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(
                        content=human_content
                        + "\n\nReturn a JSON object matching the PromptProfileRecommendation schema."
                    ),
                ]
            )
            chain = prompt | model | StrOutputParser() | parser

            t0 = time.monotonic()
            raw: dict[str, Any] = await chain.ainvoke(
                {},
                config=RunnableConfig(callbacks=middleware.callbacks()),
            )
            latency_ms = (time.monotonic() - t0) * 1000.0

            result = PromptProfileRecommendation.model_validate(raw)
            return NodeReasoningResult(
                node_id=request.node_id,
                mission_id=request.mission_id,
                success=True,
                reasoning_type=reasoning_type,
                output=result.model_dump(),
                tokens_used=0,
                latency_ms=latency_ms,
            )

        except Exception as exc:  # noqa: BLE001
            return self._make_error_result(request, reasoning_type, exc)

    async def produce_structured_triage(self, request: NodeReasoningRequest) -> NodeReasoningResult:
        """
        Produce structured triage decisions for all findings in the request.

        Attempts to use K1ChatModel.with_structured_output(TriageResult) for each
        finding when the model supports it.  Falls back to JSON parsing on failure.

        Args:
            request: Node reasoning context carrying findings list.

        Returns:
            NodeReasoningResult with output = {"triage_results": [TriageResult.model_dump()]}.
        """
        reasoning_type = "structured_triage"

        # --- Simulation fast-path ---
        if self._is_simulation(request.execution_mode):
            results = [
                TriageResult(
                    finding_id=f.get("id", "mock"),
                    title=f.get("title", "Mock Finding"),
                    severity=SeverityLevel.MEDIUM,
                    exploitability="unknown",
                    priority=5,
                    recommendation="investigate",
                    rationale="[MOCK] Triage performed.",
                    confidence=0.5,
                ).model_dump()
                for f in request.findings
            ]
            return NodeReasoningResult(
                node_id=request.node_id,
                mission_id=request.mission_id,
                success=True,
                reasoning_type=reasoning_type,
                output={"triage_results": results},
                tokens_used=0,
                latency_ms=0.0,
            )

        # --- Live LLM path ---
        if not _LANGCHAIN_AVAILABLE:
            return self._make_error_result(
                request,
                reasoning_type,
                RuntimeError("langchain_core not installed"),
            )

        try:
            factory = self._get_model_factory()
            middleware = self._make_middleware(request)

            # Attempt structured output path first; fall back to JSON parser per-finding
            structured_chain = factory.create_with_structured_output(
                schema=TriageResult,
                mission_id=request.mission_id,
            )
            use_structured = structured_chain is not None

            triage_results: list[dict[str, Any]] = []
            total_latency_ms = 0.0

            for finding in request.findings:
                finding_json = json.dumps(finding, indent=2)
                triage_input = (
                    "Triage the following finding and return a TriageResult JSON:\n\n"
                    + finding_json
                )

                t0 = time.monotonic()

                if use_structured:
                    try:
                        from langchain_core.messages import HumanMessage as HM  # noqa: PLC0415

                        raw_result = await structured_chain.ainvoke(
                            [HM(content=triage_input)],
                            config=RunnableConfig(callbacks=middleware.callbacks()),
                        )
                        # with_structured_output may return a Pydantic instance or dict
                        if isinstance(raw_result, TriageResult):
                            triage_results.append(raw_result.model_dump())
                        elif isinstance(raw_result, dict):
                            triage_results.append(
                                TriageResult.model_validate(raw_result).model_dump()
                            )
                        else:
                            raise ValueError(
                                f"Unexpected structured output type: {type(raw_result)}"
                            )
                    except Exception as struct_exc:  # noqa: BLE001
                        # Structured path failed; fall through to JSON fallback below
                        logger.warning(
                            "produce_structured_triage: structured path failed for finding %s: %s; "
                            "falling back to JSON parser",
                            finding.get("id", "?"),
                            struct_exc,
                        )
                        use_structured = False  # Disable for remaining findings too

                if not use_structured:
                    # JSON fallback using plain model + JsonOutputParser
                    model = factory.create(mission_id=request.mission_id)
                    if model is None:
                        raise RuntimeError("Model factory returned None — LangChain unavailable")
                    json_parser = JsonOutputParser()
                    prompt = ChatPromptTemplate.from_messages(
                        [
                            SystemMessage(
                                content=(
                                    "You are a vulnerability triage specialist for the K1 "
                                    "bug bounty platform. Return JSON matching TriageResult schema."
                                )
                            ),
                            HumanMessage(content=triage_input),
                        ]
                    )
                    chain = prompt | model | StrOutputParser() | json_parser
                    raw_dict: dict[str, Any] = await chain.ainvoke(
                        {},
                        config=RunnableConfig(callbacks=middleware.callbacks()),
                    )
                    triage_results.append(TriageResult.model_validate(raw_dict).model_dump())

                total_latency_ms += (time.monotonic() - t0) * 1000.0

            return NodeReasoningResult(
                node_id=request.node_id,
                mission_id=request.mission_id,
                success=True,
                reasoning_type=reasoning_type,
                output={"triage_results": triage_results},
                tokens_used=0,
                latency_ms=total_latency_ms,
            )

        except Exception as exc:  # noqa: BLE001
            return self._make_error_result(request, reasoning_type, exc)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_reasoning_engine: K1ReasoningEngine | None = None


def get_reasoning_engine() -> K1ReasoningEngine:
    """
    Return the module-level K1ReasoningEngine singleton, initializing lazily.

    Uses default model_factory and tool_registry singletons.  For explicit
    configuration (e.g. event_bus wiring) call initialize_reasoning_engine()
    before the first get_reasoning_engine() call.

    Returns:
        The module-level K1ReasoningEngine instance.
    """
    global _reasoning_engine
    if _reasoning_engine is None:
        _reasoning_engine = K1ReasoningEngine()
    return _reasoning_engine


def initialize_reasoning_engine(
    model_factory: K1ModelFactory | None = None,
    tool_registry: K1LangChainToolRegistry | None = None,
    event_bus: Any = None,
) -> K1ReasoningEngine:
    """
    Initialize (or replace) the module-level K1ReasoningEngine singleton.

    Should be called once during application startup, typically inside the
    FastAPI lifespan manager after provider and registry initialization.

    Args:
        model_factory: Pre-initialized K1ModelFactory, or None to use the
                       module singleton resolved lazily on first call.
        tool_registry: Pre-initialized K1LangChainToolRegistry, or None to
                       use the module singleton resolved lazily.
        event_bus:     Optional event bus for telemetry wiring.

    Returns:
        The newly created K1ReasoningEngine singleton.
    """
    global _reasoning_engine
    _reasoning_engine = K1ReasoningEngine(
        model_factory=model_factory,
        tool_registry=tool_registry,
        event_bus=event_bus,
    )
    logger.info(
        "K1ReasoningEngine initialized (langchain_available=%s, event_bus=%s).",
        _LANGCHAIN_AVAILABLE,
        event_bus is not None,
    )
    return _reasoning_engine
