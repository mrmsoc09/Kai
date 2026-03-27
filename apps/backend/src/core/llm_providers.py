"""
Unified LLM Provider Interface for K1
Supports: Anthropic Claude, OpenAI GPT, Google Gemini, Ollama, Gemma
With automatic fallback and provider selection
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, AsyncIterator
from enum import Enum
import os
import json
from datetime import datetime, timezone
from .secret_manager import get_secret_manager, SecretManagerError

# Provider Libraries (install as needed)
try:
    from anthropic import Anthropic as AnthropicClient
except ImportError:
    AnthropicClient = None

try:
    import openai
except ImportError:
    openai = None

try:
    import google.generativeai as genai
except ImportError:
    genai = None

try:
    import ollama
except ImportError:
    ollama = None


class LLMProvider(str, Enum):
    """Available LLM providers"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"
    GEMINI_FLASH_LITE = "gemini-flash-lite"  # Tier 2: quota fallback, high-volume
    GEMINI_PRO = "gemini-pro"                # Tier 3: complex reasoning, scarce quota
    OLLAMA = "ollama"
    GEMMA = "gemma"


class LLMModel(str, Enum):
    """Available models for each provider"""
    # Anthropic Claude
    CLAUDE_3_5_SONNET = "claude-3-5-sonnet-20241022"
    CLAUDE_3_OPUS = "claude-3-opus-20250219"
    CLAUDE_3_HAIKU = "claude-3-5-haiku-20241022"

    # OpenAI GPT
    GPT_4_TURBO = "gpt-4-turbo"
    GPT_4_VISION = "gpt-4-vision"
    GPT_4O = "gpt-4o"
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_3_5_TURBO = "gpt-3.5-turbo"

    # Google Gemini
    GEMINI_2_FLASH = "gemini-2.0-flash"
    GEMINI_1_5_PRO = "gemini-1.5-pro"
    GEMINI_1_5_FLASH = "gemini-1.5-flash"
    # Gemini 2.5 series
    GEMINI_2_5_FLASH = "gemini-2.5-flash"
    GEMINI_2_5_FLASH_LITE = "gemini-2.5-flash-lite"
    GEMINI_2_5_PRO = "gemini-2.5-pro"

    # Ollama (local)
    OLLAMA_LLAMA2 = "llama2"
    OLLAMA_NEURAL = "neural-chat"
    OLLAMA_MISTRAL = "mistral"

    # Gemma (Google open-source, served via Ollama)
    GEMMA_2_9B = "gemma:2b"
    GEMMA_7B = "gemma:7b"
    GEMMA3_8B = "gemma3:8b"  # routing-tier model

    # Qwen (local emergency fallback)
    QWEN2_5_7B = "qwen2.5:7b"


class ProviderRole(str, Enum):
    """Semantic role of a provider in the 5-tier routing chain."""
    PRIMARY = "primary"          # Tier 1: full execution, tool calls, BBP pipeline
    HIGH_VOLUME = "high_volume"  # Tier 2: quota spillover, high-volume tasks
    COMPLEX = "complex"          # Tier 3: scarce quota — report gen, CVE triage
    ROUTING = "routing"          # Tier 4: classification only, no tool calls dispatched
    EMERGENCY = "emergency"      # Tier 5: offline-only last resort
    FALLBACK = "fallback"        # legacy alias — maps to HIGH_VOLUME


@dataclass
class LLMResponse:
    """Unified response from any LLM provider"""
    provider: LLMProvider
    model: str
    text: str
    tool_uses: List[Dict[str, Any]]
    stop_reason: str
    usage: Dict[str, int]  # {input_tokens, output_tokens}
    latency_ms: float
    cost_usd: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider.value,
            "model": self.model,
            "text": self.text,
            "tool_uses": self.tool_uses,
            "stop_reason": self.stop_reason,
            "usage": self.usage,
            "latency_ms": self.latency_ms,
            "cost_usd": self.cost_usd
        }


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider"""
    provider: LLMProvider
    api_key: Optional[str] = None
    api_endpoint: Optional[str] = None
    timeout_seconds: int = 60
    max_retries: int = 3
    retry_delay_ms: int = 1000
    temperature: float = 0.7
    max_tokens: int = 2048
    is_primary: bool = False
    is_fallback: bool = False
    # 4-tier routing fields
    role: ProviderRole = ProviderRole.FALLBACK
    routing_only: bool = False  # when True: strip tools before calling this provider
    rpm_limit: int = 0          # 0 = unlimited; set for quota-limited providers
    rpd_limit: int = 0          # requests per day limit


class BaseLLMProvider(ABC):
    """Base class for LLM providers"""

    def __init__(self, config: ProviderConfig):
        self.config = config
        self.name = config.provider.value
        self.model = None
        self.client = None
        self._initialize_client()

    @abstractmethod
    def _initialize_client(self):
        """Initialize the provider's client"""
        pass

    @abstractmethod
    async def complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """Send a completion request to the LLM"""
        pass

    @abstractmethod
    async def stream_complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream a completion response"""
        pass

    def _calculate_cost(
        self,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """Calculate cost based on token usage"""
        # Pricing as of Feb 2025
        pricing = {
            LLMProvider.ANTHROPIC: {
                "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
                "claude-3-opus": {"input": 0.015, "output": 0.075},
                "claude-3-5-haiku": {"input": 0.00080, "output": 0.004}
            },
            LLMProvider.OPENAI: {
                "gpt-4-turbo": {"input": 0.01, "output": 0.03},
                "gpt-4o": {"input": 0.005, "output": 0.015},
                "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
                "gpt-3.5-turbo": {"input": 0.0005, "output": 0.0015}
            },
            LLMProvider.GEMINI: {
                "gemini-2.0-flash": {"input": 0.0375, "output": 0.15},
                "gemini-1.5-pro": {"input": 0.00125, "output": 0.005},
                "gemini-1.5-flash": {"input": 0.0375, "output": 0.15}
            },
            LLMProvider.OLLAMA: {
                "all": {"input": 0.0, "output": 0.0}  # Local = free
            },
            LLMProvider.GEMMA: {
                "all": {"input": 0.0, "output": 0.0}  # Open source = free
            }
        }

        model_pricing = pricing.get(self.config.provider, {}).get(self.model, {})
        if not model_pricing:
            model_pricing = pricing.get(self.config.provider, {}).get("all", {})

        input_cost = (input_tokens / 1000) * model_pricing.get("input", 0)
        output_cost = (output_tokens / 1000) * model_pricing.get("output", 0)

        return round(input_cost + output_cost, 6)


def _resolve_api_key(explicit_api_key: Optional[str], env_name: str) -> str:
    if explicit_api_key:
        return explicit_api_key
    try:
        secret = get_secret_manager().get_required(env_name)
        return secret
    except SecretManagerError:
        # Fail closed in production paths to avoid unmanaged secret reads.
        raise ValueError(f"{env_name} not found")


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude provider"""

    def _initialize_client(self):
        if not AnthropicClient:
            raise ImportError("anthropic package not installed")

        api_key = _resolve_api_key(self.config.api_key, "ANTHROPIC_API_KEY")

        self.client = AnthropicClient(api_key=api_key)
        self.model = os.getenv("K1_ANTHROPIC_MODEL", LLMModel.CLAUDE_3_5_SONNET.value)

    async def complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """Claude API with tool calling"""
        import time

        start_time = time.time()

        try:
            # Convert tools to Anthropic format
            anthropic_tools = []
            if tools:
                for tool in tools:
                    anthropic_tools.append({
                        "name": tool["name"],
                        "description": tool["description"],
                        "input_schema": tool.get("input_schema", {})
                    })

            # Build request
            request_kwargs = {
                "model": self.model,
                "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
                "messages": messages,
                "temperature": kwargs.get("temperature", self.config.temperature)
            }

            if system:
                request_kwargs["system"] = system

            if anthropic_tools:
                request_kwargs["tools"] = anthropic_tools

            # Make API call
            response = self.client.messages.create(**request_kwargs)

            # Extract text and tool uses
            text = ""
            tool_uses = []

            for block in response.content:
                if hasattr(block, "text"):
                    text += block.text
                elif block.type == "tool_use":
                    tool_uses.append({
                        "id": block.id,
                        "name": block.name,
                        "input": block.input
                    })

            latency_ms = (time.time() - start_time) * 1000

            cost = self._calculate_cost(
                response.usage.input_tokens,
                response.usage.output_tokens
            )

            return LLMResponse(
                provider=LLMProvider.ANTHROPIC,
                model=self.model,
                text=text,
                tool_uses=tool_uses,
                stop_reason=response.stop_reason,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens
                },
                latency_ms=latency_ms,
                cost_usd=cost
            )

        except Exception as e:
            raise Exception(f"Anthropic API error: {str(e)}")

    async def stream_complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream Claude responses"""
        request_kwargs = {
            "model": self.model,
            "max_tokens": kwargs.get("max_tokens", self.config.max_tokens),
            "messages": messages,
            "temperature": kwargs.get("temperature", self.config.temperature)
        }

        if system:
            request_kwargs["system"] = system

        with self.client.messages.stream(**request_kwargs) as stream:
            for text in stream.text_stream:
                yield text


class OpenAIProvider(BaseLLMProvider):
    """OpenAI GPT provider"""

    def _initialize_client(self):
        if not openai:
            raise ImportError("openai package not installed")

        api_key = _resolve_api_key(self.config.api_key, "OPENAI_API_KEY")

        openai.api_key = api_key
        # Default to requested model, map gpt-4.1 to gpt-4-turbo for API compatibility
        env_model = os.getenv("K1_OPENAI_MODEL", LLMModel.GPT_4O.value)
        if env_model == "gpt-4.1":
            self.model = "gpt-4-turbo" # Closest production equivalent
        else:
            self.model = env_model

    async def complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """GPT API with tool calling"""
        import time

        start_time = time.time()

        try:
            # Build system message
            if system:
                messages = [{"role": "system", "content": system}] + messages

            # Convert tools to OpenAI format
            openai_tools = []
            if tools:
                for tool in tools:
                    openai_tools.append({
                        "type": "function",
                        "function": {
                            "name": tool["name"],
                            "description": tool["description"],
                            "parameters": tool.get("input_schema", {})
                        }
                    })

            # Make API call
            request_kwargs = {
                "model": self.model,
                "messages": messages,
                "temperature": kwargs.get("temperature", self.config.temperature),
                "max_tokens": kwargs.get("max_tokens", self.config.max_tokens)
            }

            if openai_tools:
                request_kwargs["tools"] = openai_tools

            response = openai.chat.completions.create(**request_kwargs)

            # Extract text and tool uses
            text = ""
            tool_uses = []

            for choice in response.choices:
                if choice.message.content:
                    text += choice.message.content

                if choice.message.tool_calls:
                    for tool_call in choice.message.tool_calls:
                        tool_uses.append({
                            "id": tool_call.id,
                            "name": tool_call.function.name,
                            "input": json.loads(tool_call.function.arguments)
                        })

            latency_ms = (time.time() - start_time) * 1000

            cost = self._calculate_cost(
                response.usage.prompt_tokens,
                response.usage.completion_tokens
            )

            return LLMResponse(
                provider=LLMProvider.OPENAI,
                model=self.model,
                text=text,
                tool_uses=tool_uses,
                stop_reason="end_turn",
                usage={
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens
                },
                latency_ms=latency_ms,
                cost_usd=cost
            )

        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")

    async def stream_complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream GPT responses"""
        if system:
            messages = [{"role": "system", "content": system}] + messages

        response = openai.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=kwargs.get("temperature", self.config.temperature),
            max_tokens=kwargs.get("max_tokens", self.config.max_tokens),
            stream=True
        )

        for chunk in response:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class GeminiProvider(BaseLLMProvider):
    """Google Gemini provider"""

    def _initialize_client(self):
        if not genai:
            raise ImportError("google-generativeai package not installed")

        api_key = _resolve_api_key(self.config.api_key, "GOOGLE_API_KEY")

        genai.configure(api_key=api_key)
        self.model = os.getenv("K1_GEMINI_MODEL", LLMModel.GEMINI_2_5_FLASH.value)
        self.client = genai.GenerativeModel(self.model)

    async def complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """Gemini API with tool calling"""
        import time

        start_time = time.time()

        try:
            # Convert to Gemini format
            gemini_messages = []
            for msg in messages:
                gemini_messages.append({
                    "role": msg["role"],
                    "parts": [{"text": msg["content"]}]
                })

            # Convert tools to Gemini format
            gemini_tools = []
            if tools:
                for tool in tools:
                    gemini_tools.append({
                        "name": tool["name"],
                        "description": tool["description"],
                        "input_schema": tool.get("input_schema", {})
                    })

            # Build system instruction
            system_instruction = system or "You are a helpful assistant."

            # Make API call
            response = self.client.generate_content(
                contents=gemini_messages,
                system_instruction=system_instruction,
                tools=gemini_tools if gemini_tools else None,
                generation_config={
                    "temperature": kwargs.get("temperature", self.config.temperature),
                    "max_output_tokens": kwargs.get("max_tokens", self.config.max_tokens)
                }
            )

            # Extract text and tool uses
            text = response.text if hasattr(response, "text") else ""
            tool_uses = []

            # Parse function calls if present
            if hasattr(response, "parts"):
                for part in response.parts:
                    if hasattr(part, "function_call"):
                        tool_uses.append({
                            "name": part.function_call.name,
                            "input": dict(part.function_call.args)
                        })

            latency_ms = (time.time() - start_time) * 1000

            # Estimate tokens (Gemini doesn't always provide exact counts)
            input_tokens = len(" ".join([msg["content"] for msg in messages]).split())
            output_tokens = len(text.split()) if text else 0

            cost = self._calculate_cost(input_tokens, output_tokens)

            return LLMResponse(
                provider=LLMProvider.GEMINI,
                model=self.model,
                text=text,
                tool_uses=tool_uses,
                stop_reason="stop",
                usage={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens
                },
                latency_ms=latency_ms,
                cost_usd=cost
            )

        except Exception as e:
            raise Exception(f"Gemini API error: {str(e)}")

    async def stream_complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream Gemini responses"""
        gemini_messages = []
        for msg in messages:
            gemini_messages.append({
                "role": msg["role"],
                "parts": [{"text": msg["content"]}]
            })

        system_instruction = system or "You are a helpful assistant."

        response = self.client.generate_content(
            contents=gemini_messages,
            system_instruction=system_instruction,
            generation_config={
                "temperature": kwargs.get("temperature", self.config.temperature),
                "max_output_tokens": kwargs.get("max_tokens", self.config.max_tokens)
            },
            stream=True
        )

        for chunk in response:
            if chunk.text:
                yield chunk.text


class GeminiFlashLiteProvider(GeminiProvider):
    """Gemini 2.5 Flash-Lite — quota fallback (1,000 RPD).

    Inherits the full Gemini completion logic but targets the lighter model
    and enforces a daily request cap via a class-level counter. The counter
    resets automatically at UTC midnight.
    """

    _daily_request_count: int = 0
    _count_date: str = ""

    def _initialize_client(self):
        if not genai:
            raise ImportError("google-generativeai package not installed")
        api_key = _resolve_api_key(self.config.api_key, "GOOGLE_API_KEY")
        genai.configure(api_key=api_key)
        self.model = os.getenv(
            "K1_GEMINI_FLASH_LITE_MODEL", LLMModel.GEMINI_2_5_FLASH_LITE.value
        )
        self.client = genai.GenerativeModel(self.model)

    def _check_daily_quota(self) -> None:
        """Increment daily counter and raise if the configured RPD limit is hit."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if GeminiFlashLiteProvider._count_date != today:
            GeminiFlashLiteProvider._count_date = today
            GeminiFlashLiteProvider._daily_request_count = 0
        limit = self.config.rpd_limit or 1000
        if GeminiFlashLiteProvider._daily_request_count >= limit:
            raise RuntimeError(
                f"GeminiFlashLite daily quota exhausted ({limit} RPD)"
            )
        GeminiFlashLiteProvider._daily_request_count += 1

    async def complete(self, messages, system=None, tools=None, **kwargs):
        """Check daily quota then delegate to the parent Gemini implementation."""
        self._check_daily_quota()
        return await super().complete(messages, system=system, tools=tools, **kwargs)


class GeminiProProvider(GeminiProvider):
    """Gemini 2.5 Pro — complex reasoning tier (Tier 3).

    Strictly scarce: 5 RPM, 100 RPD.  A hard cap is enforced at
    GEMINI_PRO_DAILY_CAP (default 80) RPD to keep 20 requests as a daily
    buffer.

    Use ONLY for: report generation, CVE triage, complex multi-hop exploit
    chains, final vulnerability validation before submission.  Dispatched
    EXCLUSIVELY when task complexity is explicitly classified as HIGH.

    Hardware note: this is a remote API call — inference speed is not limited
    by the CPU-only local hardware.
    """

    # Class-level state (shared across instances within the process)
    _daily_request_count: int = 0
    _count_date: str = ""
    _minute_request_count: int = 0
    _minute_window_start: float = 0.0

    def _initialize_client(self) -> None:
        if not genai:
            raise ImportError("google-generativeai package not installed")
        api_key = _resolve_api_key(self.config.api_key, "GOOGLE_API_KEY")
        genai.configure(api_key=api_key)
        self.model = os.getenv("GEMINI_PRO_MODEL", LLMModel.GEMINI_2_5_PRO.value)
        self.client = genai.GenerativeModel(self.model)

    def _check_quota(self) -> None:
        """Enforce RPM (5) and RPD hard-cap (GEMINI_PRO_DAILY_CAP) for Pro tier.

        Raises RuntimeError if either limit is breached — caller must catch
        and promote to an available alternative tier.
        """
        import time as _time

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if GeminiProProvider._count_date != today:
            GeminiProProvider._count_date = today
            GeminiProProvider._daily_request_count = 0
            GeminiProProvider._minute_request_count = 0
            GeminiProProvider._minute_window_start = _time.monotonic()

        # Daily hard cap
        rpd_cap: int = int(os.getenv("GEMINI_PRO_DAILY_CAP", "80"))
        rpd_limit: int = self.config.rpd_limit or 100
        if GeminiProProvider._daily_request_count >= rpd_cap:
            raise RuntimeError(
                f"GeminiPro daily hard cap reached ({rpd_cap}/{rpd_limit} RPD). "
                "Reserved buffer — no further Pro requests until UTC midnight."
            )

        # RPM enforcement (5 RPM)
        rpm_limit: int = self.config.rpm_limit or 5
        now = _time.monotonic()
        if now - GeminiProProvider._minute_window_start >= 60.0:
            GeminiProProvider._minute_request_count = 0
            GeminiProProvider._minute_window_start = now
        if GeminiProProvider._minute_request_count >= rpm_limit:
            raise RuntimeError(
                f"GeminiPro RPM limit hit ({rpm_limit} RPM). Caller should backoff."
            )

        GeminiProProvider._daily_request_count += 1
        GeminiProProvider._minute_request_count += 1

    async def complete(self, messages, system=None, tools=None, **kwargs):
        """Enforce Pro quota then delegate to parent Gemini implementation."""
        self._check_quota()
        return await super().complete(messages, system=system, tools=tools, **kwargs)


class OllamaProvider(BaseLLMProvider):
    """Ollama provider (local models)"""

    def _initialize_client(self):
        if not ollama:
            raise ImportError("ollama package not installed")

        self.api_endpoint = self.config.api_endpoint or os.getenv("OLLAMA_API_URL", "http://localhost:11434")
        self.model = os.getenv("K1_OLLAMA_MODEL", LLMModel.OLLAMA_LLAMA2.value)

    async def complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """Ollama API call"""
        import time

        start_time = time.time()

        try:
            # Build prompt from messages
            prompt = ""
            if system:
                prompt += f"System: {system}\n\n"

            for msg in messages:
                role = msg["role"].upper()
                prompt += f"{role}: {msg['content']}\n"

            prompt += "ASSISTANT:"

            # Make API call
            response = ollama.generate(
                model=self.model,
                prompt=prompt,
                stream=False
            )

            latency_ms = (time.time() - start_time) * 1000

            # Estimate tokens (Ollama doesn't return token counts)
            input_tokens = len(prompt.split())
            output_tokens = len(response.get("response", "").split())

            return LLMResponse(
                provider=LLMProvider.OLLAMA,
                model=self.model,
                text=response.get("response", ""),
                tool_uses=[],  # Ollama doesn't support tool calling yet
                stop_reason="stop",
                usage={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens
                },
                latency_ms=latency_ms,
                cost_usd=0.0  # Local = free
            )

        except Exception as e:
            raise Exception(f"Ollama API error: {str(e)}")

    async def stream_complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream Ollama responses"""
        prompt = ""
        if system:
            prompt += f"System: {system}\n\n"

        for msg in messages:
            role = msg["role"].upper()
            prompt += f"{role}: {msg['content']}\n"

        prompt += "ASSISTANT:"

        response = ollama.generate(
            model=self.model,
            prompt=prompt,
            stream=True
        )

        for chunk in response:
            if "response" in chunk:
                yield chunk["response"]


class GemmaProvider(BaseLLMProvider):
    """Gemma provider (Google open-source)"""

    def _initialize_client(self):
        if not genai:
            raise ImportError("google-generativeai package not installed")

        api_key = _resolve_api_key(self.config.api_key, "GOOGLE_API_KEY")

        genai.configure(api_key=api_key)
        # Note: Gemma is served via Google's API
        self.model = os.getenv("K1_GEMMA_MODEL", "gemma-2b-it")
        self.client = genai.GenerativeModel(self.model)

    async def complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> LLMResponse:
        """Gemma API call"""
        import time

        start_time = time.time()

        try:
            gemini_messages = []
            for msg in messages:
                gemini_messages.append({
                    "role": msg["role"],
                    "parts": [{"text": msg["content"]}]
                })

            response = self.client.generate_content(
                contents=gemini_messages,
                generation_config={
                    "temperature": kwargs.get("temperature", self.config.temperature),
                    "max_output_tokens": kwargs.get("max_tokens", self.config.max_tokens)
                }
            )

            latency_ms = (time.time() - start_time) * 1000
            text = response.text if hasattr(response, "text") else ""

            input_tokens = len(" ".join([msg["content"] for msg in messages]).split())
            output_tokens = len(text.split()) if text else 0

            return LLMResponse(
                provider=LLMProvider.GEMMA,
                model=self.model,
                text=text,
                tool_uses=[],
                stop_reason="stop",
                usage={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens
                },
                latency_ms=latency_ms,
                cost_usd=0.0
            )

        except Exception as e:
            raise Exception(f"Gemma API error: {str(e)}")

    async def stream_complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream Gemma responses"""
        gemini_messages = []
        for msg in messages:
            gemini_messages.append({
                "role": msg["role"],
                "parts": [{"text": msg["content"]}]
            })

        response = self.client.generate_content(
            contents=gemini_messages,
            generation_config={
                "temperature": kwargs.get("temperature", self.config.temperature),
                "max_output_tokens": kwargs.get("max_tokens", self.config.max_tokens)
            },
            stream=True
        )

        for chunk in response:
            if chunk.text:
                yield chunk.text


class LLMProviderFactory:
    """Factory for creating and managing LLM providers with fallback logic"""

    def __init__(self):
        self.providers: Dict[LLMProvider, BaseLLMProvider] = {}
        self.primary_provider: Optional[LLMProvider] = None
        self.fallback_chain: List[LLMProvider] = []
        self.routing_provider: Optional[LLMProvider] = None  # classification-only tier
        self._usage_log: List[Dict[str, Any]] = []

    def register_provider(self, config: ProviderConfig):
        """Register an LLM provider"""
        provider_map = {
            LLMProvider.ANTHROPIC: AnthropicProvider,
            LLMProvider.OPENAI: OpenAIProvider,
            LLMProvider.GEMINI: GeminiProvider,
            LLMProvider.GEMINI_FLASH_LITE: GeminiFlashLiteProvider,
            LLMProvider.GEMINI_PRO: GeminiProProvider,
            LLMProvider.OLLAMA: OllamaProvider,
            LLMProvider.GEMMA: GemmaProvider,
        }

        provider_class = provider_map.get(config.provider)
        if not provider_class:
            raise ValueError(f"Unknown provider: {config.provider}")

        try:
            provider_instance = provider_class(config)
            self.providers[config.provider] = provider_instance

            if config.is_primary:
                self.primary_provider = config.provider

            if config.is_fallback:
                self.fallback_chain.append(config.provider)

            print(f"✓ Registered {config.provider.value} LLM provider")
            return True

        except Exception as e:
            print(f"✗ Failed to register {config.provider.value}: {str(e)}")
            return False

    def initialize_from_env(self):
        """Initialize the 5-tier provider chain from environment variables.

        Tiers (in priority order):
          1. PRIMARY      — gemini (gemini-2.5-flash)       — all agentic execution, tool dispatch
          2. HIGH_VOLUME  — gemini-flash-lite (1,000 RPD)   — quota spillover, bulk tasks
          3. COMPLEX      — gemini-pro (gemini-2.5-pro)     — complex reasoning, explicit HIGH only
          4. ROUTING      — gemma (gemma3:8b local)         — classification only, no tool calls
          5. EMERGENCY    — ollama (qwen2.5:7b Q4_K_M)      — full offline last resort

        Hardware note: Tiers 4-5 are local models running at 5-15 t/s on CPU-only
        hardware.  Acceptable for routing decisions only.  NOT suitable for sustained
        agentic pipeline execution.
        """
        primary = os.getenv("K1_PRIMARY_LLM_PROVIDER", "gemini").strip().lower()
        fallbacks_raw = os.getenv(
            "K1_FALLBACK_LLM_PROVIDERS", "gemini-flash-lite,gemini-pro,ollama"
        ).split(",")
        fallbacks = [f.strip().lower() for f in fallbacks_raw if f.strip()]
        routing = os.getenv("K1_ROUTING_LLM_PROVIDER", "gemma").strip().lower()

        # Canonical mapping from env-string → LLMProvider enum
        _provider_key_map: Dict[str, LLMProvider] = {
            "anthropic": LLMProvider.ANTHROPIC,
            "openai": LLMProvider.OPENAI,
            "gemini": LLMProvider.GEMINI,
            "gemini-flash-lite": LLMProvider.GEMINI_FLASH_LITE,
            "gemini-pro": LLMProvider.GEMINI_PRO,
            "ollama": LLMProvider.OLLAMA,
            "gemma": LLMProvider.GEMMA,
        }

        # Register primary provider
        primary_enum = _provider_key_map.get(primary)
        if primary_enum:
            self.register_provider(ProviderConfig(
                provider=primary_enum,
                is_primary=True,
                role=ProviderRole.PRIMARY,
            ))

        # Register routing provider (classification only — tools stripped before dispatch)
        routing_enum = _provider_key_map.get(routing)
        if routing_enum and routing_enum != primary_enum:
            self.register_provider(ProviderConfig(
                provider=routing_enum,
                is_fallback=False,
                role=ProviderRole.ROUTING,
                routing_only=True,
            ))
            self.routing_provider = routing_enum

        # Register fallbacks in declared order with explicit 5-tier roles
        _role_map: Dict[str, ProviderRole] = {
            "gemini-flash-lite": ProviderRole.HIGH_VOLUME,
            "gemini-pro": ProviderRole.COMPLEX,
            "ollama": ProviderRole.EMERGENCY,
            "gemma": ProviderRole.EMERGENCY,
        }
        _rpd_map: Dict[str, int] = {
            "gemini-flash-lite": 1000,
            "gemini-pro": 100,
        }
        _rpm_map: Dict[str, int] = {
            "gemini-flash-lite": 15,
            "gemini-pro": 5,
        }
        for fb in fallbacks:
            fb_enum = _provider_key_map.get(fb)
            if not fb_enum or fb_enum == primary_enum:
                continue
            self.register_provider(ProviderConfig(
                provider=fb_enum,
                is_fallback=True,
                role=_role_map.get(fb, ProviderRole.FALLBACK),
                rpd_limit=_rpd_map.get(fb, 0),
                rpm_limit=_rpm_map.get(fb, 0),
            ))

    async def complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        preferred_provider: Optional[LLMProvider] = None,
        **kwargs
    ) -> LLMResponse:
        """Call LLM with automatic fallback"""

        # Determine which provider to try first
        providers_to_try = []

        if preferred_provider and preferred_provider in self.providers:
            providers_to_try.append(preferred_provider)

        if self.primary_provider:
            if self.primary_provider not in providers_to_try:
                providers_to_try.append(self.primary_provider)

        providers_to_try.extend(self.fallback_chain)

        # Try each provider until one works
        last_error = None
        for provider_name in providers_to_try:
            try:
                provider = self.providers.get(provider_name)
                if not provider:
                    continue

                # Routing-only providers never receive tool definitions — strip them
                actual_tools = tools
                if getattr(provider.config, "routing_only", False):
                    actual_tools = None

                response = await provider.complete(messages, system, actual_tools, **kwargs)

                # Log usage
                self._usage_log.append({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "provider": provider_name.value,
                    "model": response.model,
                    "input_tokens": response.usage["input_tokens"],
                    "output_tokens": response.usage["output_tokens"],
                    "cost_usd": response.cost_usd,
                    "latency_ms": response.latency_ms
                })

                return response

            except Exception as e:
                last_error = e
                print(f"Provider {provider_name.value} failed: {str(e)}")
                continue

        # All providers failed
        raise Exception(f"All LLM providers failed. Last error: {str(last_error)}")

    async def stream_complete(
        self,
        messages: List[Dict[str, str]],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        preferred_provider: Optional[LLMProvider] = None,
        **kwargs
    ) -> AsyncIterator[str]:
        """Stream LLM response with fallback"""

        providers_to_try = []

        if preferred_provider and preferred_provider in self.providers:
            providers_to_try.append(preferred_provider)

        if self.primary_provider:
            if self.primary_provider not in providers_to_try:
                providers_to_try.append(self.primary_provider)

        providers_to_try.extend(self.fallback_chain)

        last_error = None
        for provider_name in providers_to_try:
            try:
                provider = self.providers.get(provider_name)
                if not provider:
                    continue

                async for chunk in provider.stream_complete(messages, system, tools, **kwargs):
                    yield chunk

                return

            except Exception as e:
                last_error = e
                print(f"Provider {provider_name.value} failed: {str(e)}")
                continue

        raise Exception(f"All LLM providers failed. Last error: {str(last_error)}")

    def get_provider(self, provider: Optional[LLMProvider] = None) -> "BaseLLMProvider":
        """Return a registered provider instance.

        If *provider* is given, return that provider.  Otherwise return the
        primary provider.  Raises ValueError if the requested provider is not
        registered.
        """
        target = provider or self.primary_provider
        if target and target in self.providers:
            return self.providers[target]
        # Fall back to first available provider
        if self.providers:
            return next(iter(self.providers.values()))
        raise ValueError("No LLM providers registered")

    def get_usage_log(self) -> List[Dict[str, Any]]:
        """Get LLM usage history"""
        return self._usage_log

    def get_usage_stats(self) -> Dict[str, Any]:
        """Get aggregated usage statistics"""
        if not self._usage_log:
            return {}

        total_cost = sum(log.get("cost_usd", 0) for log in self._usage_log)
        total_tokens = sum(
            log.get("input_tokens", 0) + log.get("output_tokens", 0)
            for log in self._usage_log
        )
        avg_latency = sum(log.get("latency_ms", 0) for log in self._usage_log) / len(self._usage_log)

        # Provider breakdown
        provider_stats = {}
        for log in self._usage_log:
            provider = log["provider"]
            if provider not in provider_stats:
                provider_stats[provider] = {
                    "count": 0,
                    "cost": 0.0,
                    "tokens": 0,
                    "latency": []
                }
            provider_stats[provider]["count"] += 1
            provider_stats[provider]["cost"] += log.get("cost_usd", 0)
            provider_stats[provider]["tokens"] += log.get("input_tokens", 0) + log.get("output_tokens", 0)
            provider_stats[provider]["latency"].append(log.get("latency_ms", 0))

        # Calculate averages
        for provider in provider_stats:
            if provider_stats[provider]["latency"]:
                provider_stats[provider]["avg_latency"] = (
                    sum(provider_stats[provider]["latency"]) / len(provider_stats[provider]["latency"])
                )
            del provider_stats[provider]["latency"]

        return {
            "total_calls": len(self._usage_log),
            "total_cost_usd": round(total_cost, 4),
            "total_tokens": total_tokens,
            "avg_latency_ms": round(avg_latency, 2),
            "provider_stats": provider_stats
        }


# Global factory instance
llm_factory = LLMProviderFactory()
