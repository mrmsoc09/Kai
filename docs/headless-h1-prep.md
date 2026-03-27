# Headless H1 Prep (No Execution)

This prep profile readies Kai for a **headless** HackerOne run across:

- `x.com` (catalog id: `hackerone:twitter`)
- `snapchat.com` (catalog id: `hackerone:snapchat`)
- `coinbase.com` (catalog id: `hackerone:coinbase`)

It does **not** start scans.

## Command

```bash
./scripts/prepare_headless_h1_scan.sh
```

## What It Configures

- Provider chain for real-run behavior:
  - `K1_PRIMARY_LLM_PROVIDER=anthropic`
  - `K1_FALLBACK_LLM_PROVIDERS=openai,ollama,gemma`
  - `K1_ROUTING_LLM_PROVIDER=gemma`
- Local model guardrails (<=9B only):
  - `K1_OLLAMA_ALLOWED_MODELS=qwen2.5-coder:7b,llama3.1:8b,gemma:7b`
  - `K1_MAX_LOCAL_MODEL_B=9`
- Headless-target metadata:
  - `K1_HEADLESS_TARGETS=x.com,snapchat.com,coinbase.com`
  - `K1_HEADLESS_PROGRAM_IDS=hackerone:twitter,hackerone:snapchat,hackerone:coinbase`
  - `K1_HEADLESS_MIN_PARALLEL_SCANS=1`
  - `K1_HEADLESS_MAX_PARALLEL_SCANS=3`
  - `K1_HEADLESS_REQUIRE_HIL=true`
  - `K1_HEADLESS_PAID_BUDGET_CENTS=1700`

## Verification Artifact

The prep script writes:

- `artifacts/headless/headless_h1_preflight.json`

It includes:

- confirmed catalog IDs
- provider key availability status (env-level)
- local model policy verification
- explicit marker that execution has not started

## Important

- If paid providers fail at runtime (missing key/quota/credit), Kai's provider fallback chain continues to local models.
- HiL remains required before report submission/finalization.
