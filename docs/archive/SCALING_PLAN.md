# Agent-Zero Inference & Platform Scaling Plan

## Overview
We will scale a 24/7 autonomous bug bounty platform with a hybrid inference stack:
- Primary: self-hosted open-weight models for continuous routing, extraction, triage assistance, and drafting (cost control + data governance).
- Burst: selective frontier API models for difficult reasoning under strict budget caps and HiL gating.
- Note on "kimi k2-thinking": treat as optional burst API if region/policy permits; not a primary engine due to self-hosting impracticality and cost/control uncertainty.

## Inference Tiers
- Tier A (Continuous, self-host): Llama 3.1 8–14B, Qwen2.5 32B, Mixtral 8x7B (quantized) via vLLM/TensorRT-LLM. Runs on single L40S/A100 80GB; ~$360–$1,800/mo 24/7 depending on market/spot.
- Tier B (Burst, API): Claude 3.5 Sonnet, Gemini 2.0 Flash, DeepSeek-V3/R1. Strict budget caps, caching, and Vault-backed keys; used for complex planning/report finalization.

## Memory & Data Plane
- Vector: Postgres+pgvector (primary), Qdrant (backup). Embed findings/evidence/dorks/programs. Dedup via cosine + locality filters.
- Knowledge Graph: RDF/NetworkX persisted to SQL + export to /artifacts/graph/.
- Secrets: HashiCorp Vault for providers/keys; no secrets in repo.

## Execution & Governance
- HiL Gate: Mandatory approval with screen recording before any submission. Policy rules in configs/policies.yaml.
- Scope Enforcement: Allowed targets list (includes *.adobe.com) and per-program policy checks.
- Audit: Merkleized logs, immutable artifacts in /artifacts.

## Cost Controls
- Caching: prompt/result caches; RAG retrieval first; batch jobs off-peak.
- Quotas: per-provider daily/weekly caps; automatic degrade to Tier A on budget pressure.
- Observability: Prometheus/Grafana + Jaeger traces, per-run cost tagging.

## Roadmap
- Phase 1: Solidify Tier A models and vector memory; wire burst APIs with caps; Adobe target runbook.
- Phase 2: Autoscaling queues, adaptive batching, and fine-tuned small models for specific tasks.
- Phase 3: Multi-tenant isolation, per-program SLA/rate policies, and cost anomaly detection.

## LLM Scaling Strategy (Hybrid, 24/7 ops)
- Primary: self-hosted open weights for continuous workloads (routing, extraction, triage assist, drafting): Llama 3.1 8–14B or Qwen2.5 32B (quantized) on single L40S/A100 80GB. Cost: ~$360–$1.8k/mo 24/7 depending on SKU/spot.
- Secondary (burst reasoning): frontier APIs capped by budget for hardest tasks (report polishing, complex planning): Claude 3.5 Sonnet, Gemini 2.0 Flash, DeepSeek-V3/R1.
- Optional: Kimi K2 “thinking” (API where regionally available) as burst engine only; no self-hosted option known. Enforce per‑project budgets and caching.
- Integration: Vault-managed API keys; pgvector/Qdrant memory; per-run audit; strict HiL gates before any outbound submissions.
- Controls: rate limiting, token budgets, offline fallbacks; periodic cost/perf reviews; regression tests on planning/report templates.

## Target-Scale Runbook: Adobe (*.adobe.com) and Additional Targets
- Scope & Governance
  - Enforce require_hil=true; allowed_targets includes *.adobe.com (and future targets).
  - All reconnaissance via ethical plan-mode (Google CSE API only); no scraping; respect robots/ToS.
  - Vault for API keys (CSE, mailers), RBAC for operators; full audit (Merkle logs for reports and actions).
- Workload & Concurrency
  - OSINT plan execution: 2–4 concurrent CSE query lanes, 30–60 QPM capped per Search Engine; exponential backoff and caching.
  - Triage pipeline batches: 500–2,000 findings/day capacity (vector duplicate + EPSS/KEV); idle scale-down overnight.
  - Recording pipeline: segment rotation + daily compression; 30–90 day retention with opt-in archival.
- Data Plane
  - Vector: pgvector primary (Qdrant optional) with 768–1,536-d embedding; dedupe and priority indexing for titles/repro text.
  - Storage: Postgres for findings/evidence/HiL; artifacts under artifacts/{recordings,reports,submissions} with Merkle trees.
- LLM Layer (Hybrid)
  - Continuous: self-host Llama 3.1 8–14B or Qwen2.5 32B (quantized) for routing, extraction, triage notes.
  - Burst: frontier APIs (Claude 3.5 Sonnet, Gemini 2.0 Flash, DeepSeek-V3/R1) for complex reasoning; strict budgets.
  - Optional: Kimi K2 "thinking" as burst API if regionally available; no self-host path assumed.
- KPIs & Limits
  - Cost guardrails: <$1–2/day for plan-mode OSINT per target; <$10–30/day total including LLM; alert at 80% budget.
  - SLA: New plan results visible <15 min; report finalize-to-package <5 min after HiL approval.
- Scale-Out (2 more targets)
  - Horizontal add queues per target; per-target budgets, CSE CX separation, shared embeddings index with target tag.
  - Conflict isolation: separate run_ids and artifact roots per target; cross-target duplicate linking in vector store.
