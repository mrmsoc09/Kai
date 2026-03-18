"""
LangChain Model Factory for K1 / Kai Platform
==============================================
Adapts Kai's multi-provider LLM abstraction (``llm_providers.LLMProviderFactory``)
into a LangChain-compatible ``BaseChatModel`` so that LangGraph nodes, LangChain
chains, and structured-output pipelines can drive inference through the same
provider-routing and fallback logic that the rest of the platform uses.

Architecture note:
  ``llm_factory`` is imported lazily (inside method bodies) to prevent circular
  imports at module load time — the Kai startup sequence registers providers
  after modules are loaded.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional LangChain import — degrade gracefully if not installed
# ---------------------------------------------------------------------------
try:
    from langchain_core.callbacks import CallbackManagerForLLMRun
    from langchain_core.callbacks.manager import AsyncCallbackManagerForLLMRun
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.output_parsers.pydantic import PydanticOutputParser
    from langchain_core.outputs import ChatGeneration, ChatResult
    from langchain_core.runnables import Runnable
    from pydantic import BaseModel as PydanticBaseModel
    from pydantic import Field

    _LANGCHAIN_AVAILABLE = True
except ImportError:
    _LANGCHAIN_AVAILABLE = False
    BaseChatModel = None  # type: ignore[assignment,misc]
    logger.warning(
        "langchain_core is not installed — K1ChatModel and K1ModelFactory will not be available. "
        "Install langchain-core>=0.1 to enable LangChain integration."
    )


# ---------------------------------------------------------------------------
# Helper: convert LangChain BaseMessage list → Kai message dicts
# ---------------------------------------------------------------------------

def _to_kai_messages(
    messages: list[BaseMessage],
) -> tuple[list[dict[str, str]], str]:
    """
    Convert a LangChain message list to Kai's ``[{role, content}]`` format.

    System messages are extracted and returned separately as the ``system``
    parameter that Kai's provider abstraction expects.  If multiple
    SystemMessages are present they are concatenated with a newline separator
    (unusual but handled defensively).

    Returns:
        (kai_messages, system_text)
    """
    kai_msgs: list[dict[str, str]] = []
    system_parts: list[str] = []

    for msg in messages:
        if isinstance(msg, SystemMessage):
            system_parts.append(str(msg.content))
        elif isinstance(msg, HumanMessage):
            kai_msgs.append({"role": "user", "content": str(msg.content)})
        elif isinstance(msg, AIMessage):
            kai_msgs.append({"role": "assistant", "content": str(msg.content)})
        else:
            # Fallback: use the role attribute when available (e.g. FunctionMessage)
            role = getattr(msg, "role", "user")
            kai_msgs.append({"role": role, "content": str(msg.content)})

    return kai_msgs, "\n".join(system_parts)


def _llm_response_to_chat_result(response: Any) -> ChatResult:
    """
    Convert a ``LLMResponse`` dataclass to a LangChain ``ChatResult``.

    Tool uses from the provider are forwarded via ``additional_kwargs`` on the
    ``AIMessage`` so that downstream LangChain agents can inspect them.
    """
    additional_kwargs: dict[str, Any] = {}
    if response.tool_uses:
        additional_kwargs["tool_calls"] = response.tool_uses

    ai_message = AIMessage(
        content=response.text,
        additional_kwargs=additional_kwargs,
    )
    generation = ChatGeneration(message=ai_message, text=response.text)
    return ChatResult(generations=[generation])


# ---------------------------------------------------------------------------
# K1ChatModel — only defined when LangChain is available
# ---------------------------------------------------------------------------

if _LANGCHAIN_AVAILABLE:

    class K1ChatModel(BaseChatModel):
        """
        LangChain ``BaseChatModel`` that delegates inference to Kai's
        ``LLMProviderFactory`` singleton, preserving provider-routing,
        fallback logic, cost tracking, and telemetry.

        Fields map directly to the factory ``complete()`` signature so they
        can be set per-invocation via ``.bind()`` or at construction time.
        """

        # ------------------------------------------------------------------
        # Pydantic v2 field declarations
        # ------------------------------------------------------------------
        model_name: str = Field(default="default", description="Logical model name for telemetry.")
        preferred_provider: str | None = Field(
            default=None,
            description="LLMProvider enum value ('anthropic', 'openai', …) to prefer.",
        )
        system_prompt: str = Field(
            default="",
            description="Mission-level system context prepended when no SystemMessage is present.",
        )
        temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature.")
        max_tokens: int = Field(default=2048, gt=0, description="Maximum tokens to generate.")
        mission_id: str = Field(default="", description="Mission ID for telemetry correlation.")

        # ------------------------------------------------------------------
        # LangChain identity
        # ------------------------------------------------------------------
        @property
        def _llm_type(self) -> str:
            return "k1_chat_model"

        def _identifying_params(self) -> dict[str, Any]:
            """Surface key params for LangChain caching and tracing layers."""
            return {
                "model_name": self.model_name,
                "preferred_provider": self.preferred_provider,
                "mission_id": self.mission_id,
            }

        # ------------------------------------------------------------------
        # Internal: resolve preferred_provider → LLMProvider enum
        # ------------------------------------------------------------------
        def _resolve_provider(self) -> Any | None:
            """
            Translate the string ``preferred_provider`` field into the
            ``LLMProvider`` enum used by the factory.  Returns ``None`` if
            unset or unrecognised (factory will use primary).
            """
            if not self.preferred_provider:
                return None
            try:
                # Lazy import to avoid circular at module load
                from core.llm_providers import LLMProvider  # noqa: PLC0415

                return LLMProvider(self.preferred_provider.lower())
            except (ValueError, ImportError):
                logger.warning(
                    "Unknown preferred_provider '%s' — falling back to primary provider.",
                    self.preferred_provider,
                )
                return None

        # ------------------------------------------------------------------
        # Synchronous generate (LangChain standard interface)
        # ------------------------------------------------------------------
        def _generate(
            self,
            messages: list[BaseMessage],
            stop: list[str] | None = None,
            run_manager: CallbackManagerForLLMRun | None = None,
            **kwargs: Any,
        ) -> ChatResult:
            """
            Synchronous bridge to the async ``llm_factory.complete()``.

            Creates a fresh event loop when no loop is running (typical for
            synchronous callers).  When called from within a running async
            context the caller should use ``_agenerate`` directly.
            """
            # Lazy import — avoids circular imports and startup-order issues
            from core.llm_providers import llm_factory  # noqa: PLC0415

            kai_msgs, extracted_system = _to_kai_messages(messages)
            system = extracted_system or self.system_prompt or None
            preferred = self._resolve_provider()

            async def _run() -> Any:
                return await llm_factory.complete(
                    messages=kai_msgs,
                    system=system,
                    preferred_provider=preferred,
                    temperature=kwargs.get("temperature", self.temperature),
                    max_tokens=kwargs.get("max_tokens", self.max_tokens),
                )

            try:
                # Prefer the existing event loop if it is not already running
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Nested call (e.g., from a Jupyter/FastAPI context).
                    # Use a new thread-bound loop as a safe escape hatch.
                    import concurrent.futures  # noqa: PLC0415

                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                        future = pool.submit(asyncio.run, _run())
                        response = future.result()
                else:
                    response = loop.run_until_complete(_run())
            except RuntimeError:
                # No current event loop — create a new one
                response = asyncio.run(_run())

            return _llm_response_to_chat_result(response)

        # ------------------------------------------------------------------
        # Asynchronous generate (preferred for async callers)
        # ------------------------------------------------------------------
        async def _agenerate(
            self,
            messages: list[BaseMessage],
            stop: list[str] | None = None,
            run_manager: AsyncCallbackManagerForLLMRun | None = None,
            **kwargs: Any,
        ) -> ChatResult:
            """
            Native async path — directly awaits ``llm_factory.complete()``.
            Preferred over ``_generate`` when the caller is already async.
            """
            from core.llm_providers import llm_factory  # noqa: PLC0415

            kai_msgs, extracted_system = _to_kai_messages(messages)
            system = extracted_system or self.system_prompt or None
            preferred = self._resolve_provider()

            response = await llm_factory.complete(
                messages=kai_msgs,
                system=system,
                preferred_provider=preferred,
                temperature=kwargs.get("temperature", self.temperature),
                max_tokens=kwargs.get("max_tokens", self.max_tokens),
            )
            return _llm_response_to_chat_result(response)

        # ------------------------------------------------------------------
        # Structured output — prompt-instruction approach
        # ------------------------------------------------------------------
        def with_structured_output(
            self,
            schema: dict[str, Any] | type,
            *,
            include_raw: bool = False,
            **kwargs: Any,
        ) -> Runnable:
            """
            Return a ``Runnable`` that coerces model output into ``schema``.

            Because Kai's provider abstraction does not expose a native
            tool-calling / function-calling bind layer that LangChain can
            introspect, this implementation uses a prompt-instruction
            strategy:

            1. A ``PydanticOutputParser`` generates JSON schema instructions
               that are appended to the system prompt of each invocation via
               a ``RunnableLambda`` pre-processor.
            2. The model is invoked and the raw text response is parsed back
               into the Pydantic model (or dict for non-Pydantic schemas).

            This mirrors the strategy used by LLM wrappers that do not
            support ``bind_tools()``.

            Args:
                schema: A Pydantic v2 ``BaseModel`` subclass or a JSON Schema
                        dict.  Pydantic schemas produce typed instances;
                        dict schemas produce validated dicts.
                include_raw: If ``True``, the returned ``Runnable`` yields
                             ``{'raw': AIMessage, 'parsed': ..., 'parsing_error': ...}``.
                             If ``False`` (default), only the parsed result is returned.

            Returns:
                A LangChain ``Runnable`` chain.
            """
            from langchain_core.runnables import RunnableLambda  # noqa: PLC0415

            # Build the correct output parser depending on schema type
            is_pydantic = isinstance(schema, type) and issubclass(schema, PydanticBaseModel)

            if is_pydantic:
                output_parser: Any = PydanticOutputParser(pydantic_object=schema)
                format_instructions = output_parser.get_format_instructions()
            else:
                # For plain dict schemas, use JSON output parser
                from langchain_core.output_parsers import JsonOutputParser  # noqa: PLC0415

                output_parser = JsonOutputParser()
                import json  # noqa: PLC0415

                schema_str = json.dumps(schema, indent=2) if isinstance(schema, dict) else ""
                format_instructions = (
                    "Return a JSON object matching this schema:\n" + schema_str
                )

            # Pre-processor: inject format instructions into the last human message
            # or append them to the system prompt via a new SystemMessage.
            def _inject_format_instructions(
                messages: list[BaseMessage],
            ) -> list[BaseMessage]:
                """
                Append output format instructions to the final HumanMessage, or
                add a new HumanMessage containing just the instructions if the
                message list ends with an AIMessage.
                """
                if not messages:
                    return messages
                # Clone to avoid mutating caller's list
                msgs = list(messages)
                # Find the last human message and augment it
                for i in range(len(msgs) - 1, -1, -1):
                    if isinstance(msgs[i], HumanMessage):
                        augmented_content = (
                            str(msgs[i].content)
                            + "\n\n"
                            + format_instructions
                        )
                        msgs[i] = HumanMessage(content=augmented_content)
                        return msgs
                # No human message found — append standalone instructions
                msgs.append(HumanMessage(content=format_instructions))
                return msgs

            injector = RunnableLambda(_inject_format_instructions)
            str_parser = StrOutputParser()

            if not include_raw:
                # Standard pipeline: inject format instructions → model → str → parse
                return injector | self | str_parser | output_parser  # type: ignore[return-value]

            # include_raw=True path: return {'raw': AIMessage, 'parsed': ..., 'parsing_error': ...}
            def _to_raw_dict(ai_message: AIMessage) -> dict[str, Any]:
                """Parse text from model output, tolerating parse failures."""
                text = ai_message.content if isinstance(ai_message.content, str) else str(ai_message.content)
                try:
                    parsed = output_parser.parse(text)
                    return {"raw": ai_message, "parsed": parsed, "parsing_error": None}
                except Exception as exc:
                    return {"raw": ai_message, "parsed": None, "parsing_error": exc}

            # inject → model yields AIMessage; then wrap into the raw dict
            return injector | self | RunnableLambda(_to_raw_dict)  # type: ignore[return-value]

else:
    # LangChain not available — provide a stub so import sites don't crash
    K1ChatModel = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# K1ModelFactory — manages K1ChatModel instances
# ---------------------------------------------------------------------------


class K1ModelFactory:
    """
    Factory that creates configured ``K1ChatModel`` instances (or ``None``
    when LangChain is not installed).

    Accepts an optional ``event_bus`` parameter for future telemetry
    integration; not currently wired.
    """

    def __init__(self, event_bus: Any = None) -> None:
        self._event_bus = event_bus
        if not _LANGCHAIN_AVAILABLE:
            logger.warning(
                "K1ModelFactory: langchain_core not available. "
                "All factory methods will return None."
            )

    # ------------------------------------------------------------------
    # Core factory method
    # ------------------------------------------------------------------
    def create(
        self,
        preferred_provider: str | None = None,
        system_prompt: str = "",
        mission_id: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> K1ChatModel | None:  # type: ignore[name-defined]
        """
        Return a configured ``K1ChatModel``.

        Args:
            preferred_provider: LLMProvider value string, e.g. ``"anthropic"``.
            system_prompt: Mission-level system context for the model.
            mission_id: Correlation ID embedded in telemetry.
            temperature: Sampling temperature (0.0–2.0).
            max_tokens: Maximum tokens to generate.

        Returns:
            ``K1ChatModel`` instance, or ``None`` if LangChain is unavailable.
        """
        if not _LANGCHAIN_AVAILABLE or K1ChatModel is None:
            logger.warning("K1ModelFactory.create: langchain_core unavailable, returning None.")
            return None

        return K1ChatModel(
            preferred_provider=preferred_provider,
            system_prompt=system_prompt,
            mission_id=mission_id,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    # ------------------------------------------------------------------
    # Structured-output factory method
    # ------------------------------------------------------------------
    def create_with_structured_output(
        self,
        schema: type,
        preferred_provider: str | None = None,
        system_prompt: str = "",
        mission_id: str = "",
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> Any | None:
        """
        Return a ``K1ChatModel`` chained with ``with_structured_output(schema)``.

        The returned object is a LangChain ``Runnable`` that coerces the model
        output into an instance of ``schema`` (typically a Pydantic v2 model).

        Args:
            schema: Pydantic v2 ``BaseModel`` subclass (or JSON schema dict)
                    to validate output against.
            preferred_provider: Provider preference forwarded to ``create()``.
            system_prompt: System context forwarded to ``create()``.
            mission_id: Telemetry correlation ID.
            temperature: Sampling temperature.
            max_tokens: Maximum tokens.

        Returns:
            A LangChain ``Runnable`` or ``None`` if LangChain is unavailable.
        """
        model = self.create(
            preferred_provider=preferred_provider,
            system_prompt=system_prompt,
            mission_id=mission_id,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if model is None:
            return None

        return model.with_structured_output(schema)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_model_factory: K1ModelFactory | None = None


def get_model_factory() -> K1ModelFactory:
    """
    Return the module-level ``K1ModelFactory`` singleton.

    Initialises with default settings on first call.  For explicit
    configuration (e.g., event bus wiring) call ``initialize_model_factory()``
    before the first ``get_model_factory()`` call.
    """
    global _model_factory
    if _model_factory is None:
        _model_factory = K1ModelFactory()
    return _model_factory


def initialize_model_factory(event_bus: Any = None) -> K1ModelFactory:
    """
    Create (or replace) the module-level ``K1ModelFactory`` singleton.

    Should be called once during application startup, typically inside the
    FastAPI lifespan manager alongside other provider initialisation.

    Args:
        event_bus: Optional event bus for future telemetry hooks.

    Returns:
        The newly created ``K1ModelFactory`` singleton.
    """
    global _model_factory
    _model_factory = K1ModelFactory(event_bus=event_bus)
    logger.info("K1ModelFactory initialised (langchain_available=%s).", _LANGCHAIN_AVAILABLE)
    return _model_factory
