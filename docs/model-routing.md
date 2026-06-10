# Model Routing

Kai now uses a role-based router for remote and local LLM selection.

## Provider Modes

`KAI_MODEL_PROVIDER` controls the runtime mode:

- `auto`: prefer a healthy local OpenAI-compatible endpoint when configured; otherwise use OpenRouter.
- `openrouter`: force OpenRouter routes and require `OPENROUTER_API_KEY`.
- `local`: force a local OpenAI-compatible endpoint and do not require `OPENROUTER_API_KEY`.

## Required Environment

```bash
OPENROUTER_API_KEY=...
OPENAI_API_KEY=...             # optional premium final-say fallback
KAI_MODEL_PROVIDER=auto
KAI_OPENROUTER_DISCOVERY_ENABLED=true
KAI_LOCAL_LLM_BASE_URL=http://127.0.0.1:8000/v1
KAI_LOCAL_BULK_MODEL=deepseek-r1-distill-qwen-32b
KAI_LOCAL_CODING_MODEL=qwen2.5-coder-32b-instruct
KAI_LOCAL_PREMIUM_MODEL=qwen2.5-72b-instruct
KAI_MODEL_ROUTE_BULK=deepseek/deepseek-v4-flash
KAI_MODEL_ROUTE_CODING=qwen/qwen3.5-27b
KAI_MODEL_ROUTE_PREMIUM=moonshotai/kimi-k2.5
KAI_MODEL_ROUTE_FREE_PREMIUM=moonshotai/kimi-k2.6:free
```

## Roles

Routes are defined in [config/model_routing.yaml](/home/k1-admin/Kai/config/model_routing.yaml).

Default roles:

- `bulk_reasoning`: DeepSeek V4 Flash, then DeepSeek V4 Pro, then `local.bulk_reasoning`
- `coding`: Qwen 3.5 27B, then DeepSeek V4 Pro, then `local.coding`
- `free_premium`: Kimi K2.6 free when discovery confirms it, then Kimi K2.5, then DeepSeek V4 Pro, then `local.premium`
- `premium_escalation`: Kimi K2.5, then DeepSeek V4 Pro, then `local.premium`, then `openai/gpt-4.1`

Aliases map workload names onto those route roles. Examples:

- `report_drafting`, `triage`, `scheduler`, `recon_synthesis`, and `case_analysis` map to `bulk_reasoning`
- `code_generation`, `test_generation`, `refactor`, `docker_generation`, `kubernetes_generation`, and `parser_generation` map to `coding`
- `hard_failure_escalation` and `architecture_redesign` map to `premium_escalation`

## OpenRouter Discovery

Kai checks `GET https://openrouter.ai/api/v1/models` and caches the model registry with a TTL.

Discovery is used to decide whether opportunistic routes like `moonshotai/kimi-k2.6:free` are currently eligible. If discovery fails, Kai keeps running and falls back to the static route order.

## Local OpenAI-Compatible Endpoints

Any OpenAI-compatible `/v1/chat/completions` endpoint can be used for local mode, including:

- vLLM
- SGLang
- LM Studio
- Ollama's OpenAI-compatible API
- compatible reverse proxies

Kai probes `GET <KAI_LOCAL_LLM_BASE_URL>/models` to decide whether the local route is healthy in `auto` mode.

## Guardrails and Observability

The router enforces per-role:

- max output tokens
- temperature and `top_p`
- optional reasoning effort
- estimated per-request cost ceilings
- monthly provider budget tracking

Kai logs:

- selected role
- provider
- model
- fallback attempt number
- latency
- token counts when returned
- estimated request cost when known
- failure reason

Kai does not log API keys or full prompts by default.
