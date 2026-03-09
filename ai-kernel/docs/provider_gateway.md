# Provider Gateway

`ai-kernel/wrappers/gateway/provider_gateway.py` normalizes access to OpenAI, Anthropic, Gemini, Ollama, OpenRouter, Gemma, and Qwen. Configuration lives in `config/providers/*.yaml`. Routing decisions are made via capability registry and routing policy, not hardcoded provider preference.
