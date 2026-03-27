# GeminiOrchestrator — Five-Tier Model Routing Architecture

## Hardware Context

**Deployment**: Lenovo V15 G2 IJL
**Specs**: CPU-only, 40 GB RAM, 1 TB NVMe SSD, no discrete GPU
**Local inference**: 5–15 tokens/second

### Why local inference is routing-only

At 5–15 t/s on CPU-only hardware, local model inference is acceptable for
classification decisions (single short response needed) but not for sustained
agentic pipeline execution (multi-turn reasoning, tool dispatch, multi-KB output).

All agentic work runs through the Gemini API free tier. Local models are
**routing-only** and **emergency fallback only**. This is a deliberate
architectural constraint enforced in code.

---

## Five-Tier Model Strategy

| Tier | Role            | Model                    | RPM | RPD  | Use                                              |
|------|-----------------|--------------------------|-----|------|--------------------------------------------------|
| 1    | PRIMARY         | `gemini-2.5-flash`       | 10  | 250  | All agentic execution, tool dispatch, BBP pipeline |
| 2    | HIGH_VOLUME     | `gemini-2.5-flash-lite`  | 15  | 1000 | High-volume recon, classification, quota spillover |
| 3    | COMPLEX         | `gemini-2.5-pro`         | 5   | 100  | Report gen, CVE triage, complex multi-hop chains  |
| 4    | LOCAL_ROUTING   | `gemma3:8b` via Ollama   | —   | —    | Task classification **only** — no tool calls      |
| 5    | LOCAL_EMERGENCY | `qwen2.5:7b` Q4_K_M      | —   | —    | Full offline fallback — last resort only          |

### Tier 1 — PRIMARY

- **Model**: `gemini-2.5-flash`
- **Limits**: 10 RPM, 250 RPD
- **Use**: All BBP pipeline execution, tool dispatch, multi-step reasoning, agentic task chains
- **Notes**: Native tool calling, proven agentic reliability

### Tier 2 — HIGH VOLUME FALLBACK

- **Model**: `gemini-2.5-flash-lite`
- **Limits**: 15 RPM, 1,000 RPD
- **Trigger**: Auto-activated when Flash daily quota drops below `GEMINI_FLASH_DAILY_ALERT` (default 50)
- **Use**: High-volume recon tasks, classification, simple routing, quota spillover from Tier 1

### Tier 3 — COMPLEX REASONING (scarce — guard carefully)

- **Model**: `gemini-2.5-pro`
- **Limits**: 5 RPM, 100 RPD
- **Hard cap**: 80 RPD consumed — reserves 20 RPD as daily buffer
- **Trigger**: Explicit `COMPLEXITY_HIGH` classification only — never auto-promoted
- **Use**: Report generation, CVE triage, complex multi-hop chains, final vulnerability validation before submission

### Tier 4 — LOCAL ROUTING

- **Model**: `gemma3:8b` via Ollama
- **Use**: Task classification and routing decisions **only**
- **Constraint**: NEVER dispatches tool calls. NEVER executes agentic tasks. Text classification only.
- **Notes**: Uses Gemini CLI native local model routing. 5–15 t/s acceptable for classification.

### Tier 5 — EMERGENCY FALLBACK

- **Model**: `qwen2.5:7b` Q4_K_M via Ollama
- **Use**: Full offline operation only — all API tiers exhausted or network unavailable
- **Constraint**: Not suitable for sustained pipeline use at 5–15 t/s on CPU-only hardware
- **Trigger**: All API tiers return 429 or network unavailable
- **Logging**: Activation logged at `CRITICAL` level with explicit warning about degraded performance

---

## Quota Management

### Client-side tracking

`quota_tracker.py` maintains per-model token buckets (RPM) and daily counters
(RPD) in memory, persisted to disk on every mutation so process restarts survive
intraday.

**Persistence path**: `GEMINI_QUOTA_PERSIST_PATH` (default: `artifacts/quota_state.json`)
**Reset**: Counters reset at UTC midnight.

### Alert thresholds

| Threshold           | Default | Behaviour                                        |
|---------------------|---------|--------------------------------------------------|
| `GEMINI_FLASH_DAILY_ALERT`  | 50  | Flash-Lite spillover activated; MEDIUM tasks routed to Tier 2 |
| `GEMINI_PRO_DAILY_CAP`      | 80  | Pro hard gate; no new HIGH tasks until next reset |
| `GEMINI_PRO_DAILY_ALERT`    | 20  | Warning logged; `pro_restricted` flag set         |

### 429 Handling

On any 429 response:
1. Exponential backoff with ±30% jitter starting at 1,000 ms (max 32,000 ms)
2. Auto-promote to next available tier
3. **Never** propagate a 429 upstream — callers always receive a result or a clean error

---

## Task Classification (model_router.py)

```
instruction → Gemma3:8b (Ollama)
              ↓ (if unavailable)
              keyword classifier (instant, always available)
              ↓
  LOW  → Flash-Lite (Tier 2)
  MEDIUM → Flash (Tier 1)    [or Flash-Lite if spillover active]
  HIGH → Pro (Tier 3)        [or Flash if Pro restricted]
```

Classification results are cached by instruction SHA-256 with a 5-minute TTL.

---

## Wired Integration Points

### ScreenVisionAgent

`GeminiOrchestrator.execute()` calls `_observe_vision()` post-execution when
`K1_VISION_ANALYSIS_ENABLED=true`. The `VisionValidationService` captures
screenshots, analyses them with Claude vision, and returns `VisionAnalysisResult`
objects. Observations are attached to `OrchestrationResult.vision_observations`.

### ToolRegistry (stub — next session)

`GeminiOrchestrator._dispatch_tool(tool_name, inputs)` is a stub that logs
tool calls and returns placeholder results. It is marked:

```python
# KAISON-TODO: Wire to ToolRegistry next session
```

Full implementation will look up `tool_name` in ToolRegistry, validate inputs
against schema, and execute via Celery worker with scope/cert gates.

---

## Frontend Binding Points

### WebSocket Endpoints

| Endpoint | Protocol | Auth | Purpose |
|----------|----------|------|---------|
| `/api/v1/orchestration/ws/chat` | WS | `?token=` | Streaming chat relay |
| `/api/v1/orchestration/ws/agents` | WS | `?token=` | Agent+quota status (5s push) |

### REST Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/orchestration/health` | GET | Provider chain health |
| `/api/v1/orchestration/agents` | GET | Agent node list |
| `/api/v1/orchestration/quota` | GET | Per-tier quota status |
| `/api/v1/orchestration/tier` | GET | Active tier |
| `/api/v1/orchestration/dispatch` | POST | Execute OrchestrationTask |
| `/api/v1/orchestration/stream/{task_id}` | GET (SSE) | Task result stream |
| `/api/v1/orchestration/workflows` | GET | Hunt workflow list |
| `/api/v1/orchestration/workflows/hunt` | POST | Enqueue hunt workflow |

### Frontend Components

| Component | Binding |
|-----------|---------|
| `UnifiedOrchestrationDashboard.tsx` | Polls `/health`, `/agents`, `/quota`, `/llm/providers` on mount; WS `/ws/agents` for live updates |
| `AIEngine.tsx` | WS `/ws/chat` for streaming chat |
| `useAgentStatus.ts` hook | WS `/ws/agents` — exposes `agents`, `activeTier`, `quotaStatus`, `sessionState` |
| `orchestrationService` (services.ts) | All REST endpoints including `dispatch()`, `getQuotaStatus()`, `getActiveTier()`, `streamSession()` |

### Quota Indicator

The dashboard renders a colour-coded quota bar for each API tier:

| Flash RPD remaining | Colour  | Meaning                         |
|---------------------|---------|---------------------------------|
| > 100               | 🟢 green  | Healthy                         |
| 50–100              | 🟡 yellow | Getting low                     |
| < 50                | 🟠 orange | Spillover to Flash-Lite active  |
| Pro < 20            | 🔴 red    | Buffer zone — dispatch restricted |

---

## Configuration

All config keys live in `apps/backend/src/config/agents.yaml` under
`gemini_orchestrator:`. Set values via environment variables.

```
GEMINI_CLI_PATH              gemini
GEMINI_DEFAULT_MODEL         gemini-2.5-flash
GEMINI_FLASH_MODEL           gemini-2.5-flash          # Tier 1
GEMINI_FLASH_LITE_MODEL      gemini-2.5-flash-lite     # Tier 2
GEMINI_PRO_MODEL             gemini-2.5-pro            # Tier 3
GEMINI_LOCAL_ROUTING_MODEL   gemma3:8b                 # Tier 4
GEMINI_LOCAL_FALLBACK_MODEL  qwen2.5:7b                # Tier 5
GEMINI_MAX_SESSIONS          3
GEMINI_FLASH_DAILY_ALERT     50
GEMINI_PRO_DAILY_CAP         80
GEMINI_PRO_DAILY_ALERT       20
GEMINI_LOG_SESSIONS          true
GEMINI_QUOTA_PERSIST_PATH    artifacts/quota_state.json
GEMINI_FLASH_DAILY_LIMIT     250
GEMINI_FLASH_RPM             10
GEMINI_FLASH_LITE_DAILY_LIMIT 1000
GEMINI_FLASH_LITE_RPM        15
GEMINI_PRO_DAILY_LIMIT       100
GEMINI_PRO_RPM               5
```

---

## Future Architecture

> Tiers 4–5 will be replaced by a custom KAISON AI agent fine-tuned on
> accumulated platform hunt data, optimised for offensive security reasoning
> and BBP workflow orchestration. GeminiOrchestrator is model-agnostic by
> design — swapping any tier requires only a config change.

The `ModelTier` enum and routing logic are decoupled from provider
implementation. A new local model is wired by:

1. Adding a `ModelTier` enum value
2. Registering a provider in `LLMProviderFactory.initialize_from_env()`
3. Updating `GEMINI_LOCAL_ROUTING_MODEL` or `GEMINI_LOCAL_FALLBACK_MODEL` env

No orchestration logic changes are required.

---

## Key Files

| File | Purpose |
|------|---------|
| `apps/backend/src/core/gemini_orchestrator.py` | Singleton hub, 5-tier execution, vision + tool dispatch |
| `apps/backend/src/core/quota_tracker.py` | Token bucket, RPD counters, persistence, callbacks |
| `apps/backend/src/core/model_router.py` | Task classification via Gemma3 + keyword fallback |
| `apps/backend/src/core/task_schema.py` | OrchestrationTask, OrchestrationResult, QuotaStatus, ModelTier |
| `apps/backend/src/core/llm_providers.py` | Provider implementations, LLMProviderFactory |
| `apps/backend/src/routers/orchestration_v1.py` | FastAPI router — all /api/v1/orchestration/* endpoints |
| `config/providers/gemini.yaml` | Gemini model config (Flash, Flash-Lite, Pro) |
| `config/providers/gemma.yaml` | Gemma3 routing-tier config |
| `config/providers/qwen.yaml` | Qwen emergency fallback config |
