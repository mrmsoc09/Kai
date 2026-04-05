# Praison Capability Map

## Scope and Method
This map is derived from the full Phase 1 index (`5235` pages) and processed in controlled category batches (one category at a time) across all `52` categories.

Processing approach:
- Full-pass structural extraction over all indexed pages (`output/praison_docs_complete_index_2026-04-05.csv`)
- Category-batch synthesis (counts, topic signals, constraints by category)
- Deep-pass reads on high-impact operational pages (approval, autonomy, execution limits, jobs API, MCP auth/pagination/elicitation, guardrails, memory, retrieval, integration models)

This document stores only engineering-relevant outputs for Kai.

## Category Coverage (All Categories)
| Category | Pages | Engineering Role |
| --- | ---:| --- |
| sdk | 3791 | API surface, object model, method-level contracts |
| js | 290 | TypeScript/JS runtime and provider integration |
| examples | 173 | Composition patterns and reference flows |
| cli | 171 | Operator and automation entrypoints |
| features | 151 | Core behavior modules and runtime capabilities |
| tools | 91 | Tool ecosystem and adapter targets |
| rust | 76 | Rust bindings/runtime parity |
| mcp | 47 | Tool protocol integration and remote capability exposure |
| concepts | 46 | Mental model and abstractions |
| guides | 46 | Recommended integration approaches |
| deploy | 44 | Server/runtime deployment surfaces |
| databases | 26 | Persistence and vector/state backend options |
| embeddings | 26 | Embedding providers and options |
| configuration | 21 | Runtime policy and limit controls |
| observability | 21 | Trace/log/eval integrations |
| course | 20 | Learning-oriented pattern walkthroughs |
| agents | 18 | Task-focused agent templates |
| api | 15 | Network protocol endpoints |
| rag | 15 | Retrieval and citation behavior |
| ui | 15 | Interactive surfaces and streaming UX |
| models | 14 | LLM provider abstraction |
| capabilities | 13 | OpenAI/Anthropic-style endpoint parity |
| audio | 12 | STT/TTS multimodal capabilities |
| best-practices | 11 | Reliability/safety recommendations |
| developers | 10 | Contributor/developer workflow |
| code | 7 | External coding-agent tooling integration |
| image | 7 | Image generation/analysis pathways |
| memory | 7 | Tiered memory and graph memory options |
| knowledge | 6 | Knowledge source integration |
| nocode | 6 | YAML/CLI generation flow |
| video | 6 | Video generation integrations |
| eval | 3 | Evaluation loops |
| framework | 3 | CrewAI/AG2/praisonaiagents framework modes |
| persistence | 3 | Session persistence/resume |
| tutorials | 3 | Guided implementation examples |
| api-reference | 2 | Supplemental reference surfaces |
| monitoring | 2 | Monitoring-specific overlays |
| ocr | 2 | OCR providers |
| recipes | 2 | Recipe-centric automation |
| call | 1 | Voice/call flow |
| contributing | 1 | Contribution process |
| firecrawl | 1 | Specialized crawling integration |
| home | 1 | Landing aggregation |
| installation | 1 | Install path |
| integrations | 1 | Integrations entry |
| introduction | 1 | Intro entry |
| overview | 1 | Overview entry |
| playground | 1 | Playground entry |
| quickstart | 1 | Quickstart entry |
| reference | 1 | Quick reference |
| train | 1 | Model training/deployment extension |
| videos | 1 | Video tutorial entry |

## Capability Domains (Behavior, Constraints, Edge Cases)

### 1) Agent Runtime and Autonomy
Real behavior:
- Autonomy levels are explicit (`suggest`, `auto_edit`, `full_auto`).
- Iterative autonomy loops support completion signals, max-iteration caps, doom-loop detection, timeout, optional context clearing, and result reason codes.
- Human approval can gate dangerous operations, with risk levels and callback-based decision policies.

Constraints and edge cases:
- Full autonomy can auto-approve destructive actions if enabled.
- Loop completion is heuristic + signal-based; poor completion-promise design can stall loops.
- Approval context reuse can suppress repeated prompts; useful but risky if context boundaries are loose.

Composability:
- Strong fit as an inner orchestration capability when an outer governance boundary is present.
- Best used with explicit iteration limits and deterministic stop conditions.

### 2) Execution Limits, Reliability, and Guardrails
Real behavior:
- Execution config supports `max_iter`, `max_rpm`, `max_execution_time`, and retry limits.
- LLM config supports retries, backoff, timeout decomposition, rate-limit behavior, model fallback chains, and optional queue behavior.
- Guardrail modes include strict/permissive/audit patterns plus policy-string configuration.

Constraints and edge cases:
- Many advanced knobs are policy examples; production behavior depends on runtime implementation maturity.
- Queue and fallback semantics vary by integration path (SDK vs CLI vs server).
- Aggressive retries without external rate constraints can amplify cost and latency.

Composability:
- Good fit for inner-call resilience.
- Must be subordinate to Kai scope/governance policy, not a replacement.

### 3) Async Jobs and Evented Execution
Real behavior:
- Async run API pattern: submit -> status/poll/stream -> result/cancel/delete.
- Supports idempotency keys, session grouping, webhooks, and SSE streaming.
- Status lifecycle includes `queued`, `running`, `succeeded`, `failed`, `cancelled`.

Constraints and edge cases:
- Auth may be optional by default in some server docs; must be enforced explicitly in production.
- Streaming requires SSE-capable clients; polling cadence should follow `retry_after` hints.
- Idempotency scope decisions (`none/session/global`) affect duplicate prevention semantics.

Composability:
- Strong fit for non-blocking work queues and long-running externalized tasks.
- Natural integration point for Kai phase-level asynchronous work offload.

### 4) Protocol Surfaces (MCP, A2A, AG-UI)
Real behavior:
- MCP docs cover auth (OAuth 2.1 + PKCE, OIDC, API keys), scope model, pagination with opaque cursors, and elicitation (form/url).
- A2A and AG-UI are positioned as transport protocols for agent-to-agent and agent-to-UI interactions.

Constraints and edge cases:
- MCP pagination is server-controlled; clients must not assume fixed page semantics.
- URL-mode elicitation is required for sensitive out-of-band workflows.
- Cross-protocol identity and authorization need explicit harmonization at integration boundaries.

Composability:
- MCP is high-value for tool federation.
- A2A/AG-UI are useful at ecosystem boundaries, not as a replacement for Kai mission state control.

### 5) Memory, Knowledge, and Retrieval
Real behavior:
- Multi-tier memory concepts (short/long/entity/user), optional graph memory, quality thresholds.
- Retrieval config supports auto/forced/skip retrieval, chunking, rerank, threshold, citation-capable query pathways.
- Quality-based RAG patterns add confidence filtering and weighted scoring.

Constraints and edge cases:
- Quality scoring introduces non-trivial variance and evaluation burden.
- Graph memory increases schema and operational complexity.
- Token budget pressure remains; retrieval quality and prompt shape must be co-optimized.

Composability:
- Good for analyst-assist and evidence triage.
- Must not become authoritative source of scope truth or compliance state.

### 6) Integration Models and Framework Modes
Real behavior:
- Six recipe integration models: embedded SDK, CLI invocation, local sidecar, remote runner, event-driven, plugin mode.
- CrewAI/AG2 paths rely on `roles` YAML; praison workflow `steps` format is distinct.

Constraints and edge cases:
- Framework selection is mode-sensitive; direct prompts may bypass selected external framework mode.
- Multi-framework parity is not automatic; schema translation is required.

Composability:
- Embedded/sidecar/event-driven models map cleanly to Kai extension strategies.
- Cross-framework persona portability requires a canonical intermediate schema.

### 7) Observability and Evaluation
Real behavior:
- Auto-instrumentation options and broad provider coverage.
- Tracing includes model/tool spans and token/cost surfaces.

Constraints and edge cases:
- Vendor-specific payload and redaction requirements vary.
- Blindly exporting all traces may leak sensitive findings context.

Composability:
- Useful as secondary telemetry fan-out.
- Kai EventBus and governance audit trails remain authoritative.

## Practical Fit for Kai
Use Praison primarily for:
- asynchronous execution surfaces
- protocol interoperability (especially MCP)
- convenience SDK layers for non-critical orchestration tasks
- optional retrieval/memory augmentation for analysis assistance

Do not use Praison as primary authority for:
- scope enforcement
- governance adjudication
- mission state truth
- report-readiness gate control

## Cross-Document Links
- Integration architecture: [praison_kai_integration.md](/home/k1-admin/Kai/docs/architecture/praison_kai_integration.md)
- Workflow matrix: [praison_workflow_matrix.md](/home/k1-admin/Kai/docs/research/praison_workflow_matrix.md)
- Persona mapping: [praison_persona_mapping.md](/home/k1-admin/Kai/docs/integrations/praison_persona_mapping.md)
- Implementation roadmap: [praison_implementation_roadmap.md](/home/k1-admin/Kai/docs/architecture/praison_implementation_roadmap.md)
