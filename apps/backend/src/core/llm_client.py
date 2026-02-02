"""
Unified LLM Client Abstraction Layer
Provides unified interface for Claude (Anthropic), GPT (OpenAI), and Gemini
"""

import json
import os
from typing import Any, Dict, List, Optional, Union
from enum import Enum
from dataclasses import dataclass
from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)


class LLMProvider(Enum):
    """Supported LLM providers"""
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GEMINI = "gemini"


class LLMModel(Enum):
    """Available models per provider"""
    # Anthropic
    CLAUDE_OPUS_4 = "claude-opus-4-20250805"
    CLAUDE_SONNET = "claude-3-5-sonnet-20241022"
    CLAUDE_HAIKU = "claude-3-5-haiku-20241022"

    # OpenAI
    GPT_4_TURBO = "gpt-4-turbo"
    GPT_4_VISION = "gpt-4-vision"
    GPT_35_TURBO = "gpt-3.5-turbo"

    # Gemini
    GEMINI_2_0_FLASH = "gemini-2.0-flash"
    GEMINI_1_5_PRO = "gemini-1.5-pro"
    GEMINI_1_5_FLASH = "gemini-1.5-flash"


@dataclass
class ToolUse:
    """Represents a tool call from LLM"""
    id: str
    name: str
    input: Dict[str, Any]


@dataclass
class LLMMessage:
    """Represents a message in conversation"""
    role: str  # "user" or "assistant"
    content: Union[str, List[Dict[str, Any]]]


@dataclass
class LLMResponse:
    """Unified LLM response structure"""
    text: str
    tool_uses: List[ToolUse]
    stop_reason: str
    model: str
    usage: Dict[str, int]  # input_tokens, output_tokens
    metadata: Dict[str, Any] = None


class BaseLLMClient(ABC):
    """Abstract base class for LLM clients"""

    def __init__(self, api_key: str, model: LLMModel):
        self.api_key = api_key
        self.model = model
        self.provider = self._get_provider()

    @abstractmethod
    def _get_provider(self) -> LLMProvider:
        """Get provider type"""
        pass

    @abstractmethod
    def complete(
        self,
        messages: List[LLMMessage],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> LLMResponse:
        """Execute LLM completion"""
        pass

    @abstractmethod
    def stream_complete(
        self,
        messages: List[LLMMessage],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ):
        """Stream LLM completion"""
        pass


class AnthropicClient(BaseLLMClient):
    """Claude (Anthropic) LLM client"""

    def __init__(self, api_key: Optional[str] = None, model: LLMModel = LLMModel.CLAUDE_SONNET):
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not provided")

        super().__init__(api_key, model)

        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)
        except ImportError:
            raise ImportError("anthropic package required. Install: pip install anthropic")

    def _get_provider(self) -> LLMProvider:
        return LLMProvider.ANTHROPIC

    def complete(
        self,
        messages: List[LLMMessage],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> LLMResponse:
        """Execute Claude completion with tool use support"""
        import anthropic

        # Convert messages to Anthropic format
        api_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        # Prepare tool definitions if provided
        api_tools = None
        if tools:
            api_tools = [
                {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "input_schema": tool.get("input_schema", {})
                }
                for tool in tools
            ]

        # Call Claude API
        response = self.client.messages.create(
            model=self.model.value,
            max_tokens=max_tokens,
            system=system,
            tools=api_tools,
            messages=api_messages,
            temperature=temperature,
        )

        # Extract text and tool uses
        text = ""
        tool_uses = []

        for block in response.content:
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                tool_uses.append(
                    ToolUse(
                        id=block.id,
                        name=block.name,
                        input=block.input
                    )
                )

        return LLMResponse(
            text=text,
            tool_uses=tool_uses,
            stop_reason=response.stop_reason,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
            },
            metadata={"provider": LLMProvider.ANTHROPIC.value}
        )

    def stream_complete(
        self,
        messages: List[LLMMessage],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ):
        """Stream Claude completion"""
        import anthropic

        api_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

        api_tools = None
        if tools:
            api_tools = [
                {
                    "name": tool["name"],
                    "description": tool.get("description", ""),
                    "input_schema": tool.get("input_schema", {})
                }
                for tool in tools
            ]

        with self.client.messages.stream(
            model=self.model.value,
            max_tokens=max_tokens,
            system=system,
            tools=api_tools,
            messages=api_messages,
            temperature=temperature,
        ) as stream:
            text = ""
            for event in stream:
                if hasattr(event, "content_block"):
                    if event.content_block.type == "text":
                        chunk = event.delta.text
                        text += chunk
                        yield chunk
                elif hasattr(event, "delta"):
                    if hasattr(event.delta, "text"):
                        chunk = event.delta.text
                        text += chunk
                        yield chunk


class OpenAIClient(BaseLLMClient):
    """GPT (OpenAI) LLM client"""

    def __init__(self, api_key: Optional[str] = None, model: LLMModel = LLMModel.GPT_4_TURBO):
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not provided")

        super().__init__(api_key, model)

        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=api_key)
        except ImportError:
            raise ImportError("openai package required. Install: pip install openai")

    def _get_provider(self) -> LLMProvider:
        return LLMProvider.OPENAI

    def complete(
        self,
        messages: List[LLMMessage],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ) -> LLMResponse:
        """Execute GPT completion with tool use support"""
        # Convert messages to OpenAI format
        api_messages = []

        if system:
            api_messages.append({"role": "system", "content": system})

        for msg in messages:
            api_messages.append({"role": msg.role, "content": msg.content})

        # Prepare tool definitions
        api_tools = None
        if tools:
            api_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {})
                    }
                }
                for tool in tools
            ]

        # Call OpenAI API
        response = self.client.chat.completions.create(
            model=self.model.value,
            messages=api_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=api_tools,
            tool_choice="auto" if api_tools else None,
        )

        # Extract text and tool calls
        text = ""
        tool_uses = []

        for choice in response.choices:
            if choice.message.content:
                text += choice.message.content

            if choice.message.tool_calls:
                for tool_call in choice.message.tool_calls:
                    tool_uses.append(
                        ToolUse(
                            id=tool_call.id,
                            name=tool_call.function.name,
                            input=json.loads(tool_call.function.arguments)
                        )
                    )

        return LLMResponse(
            text=text,
            tool_uses=tool_uses,
            stop_reason=response.choices[0].finish_reason,
            model=response.model,
            usage={
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
            },
            metadata={"provider": LLMProvider.OPENAI.value}
        )

    def stream_complete(
        self,
        messages: List[LLMMessage],
        system: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **kwargs
    ):
        """Stream GPT completion"""
        api_messages = []

        if system:
            api_messages.append({"role": "system", "content": system})

        for msg in messages:
            api_messages.append({"role": msg.role, "content": msg.content})

        api_tools = None
        if tools:
            api_tools = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {})
                    }
                }
                for tool in tools
            ]

        stream = self.client.chat.completions.create(
            model=self.model.value,
            messages=api_messages,
            max_tokens=max_tokens,
            temperature=temperature,
            tools=api_tools,
            tool_choice="auto" if api_tools else None,
            stream=True,
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class LLMClientFactory:
    """Factory for creating LLM clients"""

    _clients = {
        LLMProvider.ANTHROPIC: AnthropicClient,
        LLMProvider.OPENAI: OpenAIClient,
    }

    @classmethod
    def create(
        cls,
        provider: Union[LLMProvider, str] = None,
        model: Union[LLMModel, str] = None,
        api_key: Optional[str] = None,
    ) -> BaseLLMClient:
        """Factory method to create appropriate LLM client"""

        # Determine provider from env or parameter
        if provider is None:
            provider_name = os.getenv("K1_PROVIDER_PREFERRED", "anthropic").lower()
            provider = LLMProvider(provider_name)
        elif isinstance(provider, str):
            provider = LLMProvider(provider.lower())

        # Determine model
        if model is None:
            if provider == LLMProvider.ANTHROPIC:
                model = LLMModel.CLAUDE_SONNET
            elif provider == LLMProvider.OPENAI:
                model = LLMModel.GPT_4_TURBO
        elif isinstance(model, str):
            # Try to match model string to enum
            for m in LLMModel:
                if model.lower() in m.value.lower():
                    model = m
                    break
            if isinstance(model, str):
                model = LLMModel(model)

        # Create client
        client_class = cls._clients.get(provider)
        if not client_class:
            raise ValueError(f"Provider {provider} not supported")

        return client_class(api_key=api_key, model=model)

    @classmethod
    def get_default_client(cls) -> BaseLLMClient:
        """Get default configured client"""
        return cls.create()
