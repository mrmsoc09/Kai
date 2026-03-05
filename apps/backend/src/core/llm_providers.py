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
from datetime import datetime
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

    # Ollama (local)
    OLLAMA_LLAMA2 = "llama2"
    OLLAMA_NEURAL = "neural-chat"
    OLLAMA_MISTRAL = "mistral"

    # Gemma (Google)
    GEMMA_2_9B = "gemma:2b"
    GEMMA_7B = "gemma:7b"


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
        # Backward-compatible last chance; still fail closed if absent.
        fallback = os.getenv(env_name)
        if fallback and fallback.strip():
            return fallback.strip()
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
        self.model = os.getenv("K1_OPENAI_MODEL", LLMModel.GPT_4O.value)

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
        self.model = os.getenv("K1_GEMINI_MODEL", LLMModel.GEMINI_2_FLASH.value)
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
        self._usage_log: List[Dict[str, Any]] = []

    def register_provider(self, config: ProviderConfig):
        """Register an LLM provider"""
        provider_map = {
            LLMProvider.ANTHROPIC: AnthropicProvider,
            LLMProvider.OPENAI: OpenAIProvider,
            LLMProvider.GEMINI: GeminiProvider,
            LLMProvider.OLLAMA: OllamaProvider,
            LLMProvider.GEMMA: GemmaProvider
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
        """Initialize providers from environment variables"""
        primary = os.getenv("K1_PRIMARY_LLM_PROVIDER", "anthropic")
        fallbacks = os.getenv("K1_FALLBACK_LLM_PROVIDERS", "openai,gemini,ollama").split(",")

        # Register primary
        if primary == "anthropic":
            self.register_provider(ProviderConfig(
                provider=LLMProvider.ANTHROPIC,
                is_primary=True
            ))
        elif primary == "openai":
            self.register_provider(ProviderConfig(
                provider=LLMProvider.OPENAI,
                is_primary=True
            ))
        elif primary == "gemini":
            self.register_provider(ProviderConfig(
                provider=LLMProvider.GEMINI,
                is_primary=True
            ))
        elif primary == "ollama":
            self.register_provider(ProviderConfig(
                provider=LLMProvider.OLLAMA,
                is_primary=True
            ))
        elif primary == "gemma":
            self.register_provider(ProviderConfig(
                provider=LLMProvider.GEMMA,
                is_primary=True
            ))

        # Register fallbacks
        for fallback in fallbacks:
            fallback = fallback.strip()
            if fallback == "anthropic":
                self.register_provider(ProviderConfig(
                    provider=LLMProvider.ANTHROPIC,
                    is_fallback=True
                ))
            elif fallback == "openai":
                self.register_provider(ProviderConfig(
                    provider=LLMProvider.OPENAI,
                    is_fallback=True
                ))
            elif fallback == "gemini":
                self.register_provider(ProviderConfig(
                    provider=LLMProvider.GEMINI,
                    is_fallback=True
                ))
            elif fallback == "ollama":
                self.register_provider(ProviderConfig(
                    provider=LLMProvider.OLLAMA,
                    is_fallback=True
                ))
            elif fallback == "gemma":
                self.register_provider(ProviderConfig(
                    provider=LLMProvider.GEMMA,
                    is_fallback=True
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

                response = await provider.complete(messages, system, tools, **kwargs)

                # Log usage
                self._usage_log.append({
                    "timestamp": datetime.utcnow().isoformat(),
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
