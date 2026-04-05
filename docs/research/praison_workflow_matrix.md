# Praison Workflow Pattern Matrix

This matrix translates Praison workflow capabilities into Kai implementation choices.

| Pattern | Praison support level | Constraints | Recommended use in Kai | Avoid/Caution | Fallback approach |
| --- | --- | --- | --- | --- | --- |
| Single-agent synchronous task | Native | Limited throughput; caller-blocking | Lightweight enrichment tasks in non-critical nodes | Running heavy scans inline | Route to queued worker phase |
| Multi-agent sequential pipeline | Native | Error propagation across chain | Structured analysis pipelines where deterministic ordering matters | Long chains without checkpoint boundaries | Split into LangGraph phase nodes |
| Multi-agent parallel fan-out | Native (framework-dependent) | Coordination overhead; result merge complexity | Parallel evidence enrichment or classification branches | Unbounded parallelism under tenant load | Concurrency caps + queue backpressure |
| Iterative autonomy loop | Native | Needs strict `max_iterations`, timeout, doom-loop limits | Bounded planning/refinement loops for text/code artifacts | Full-auto on high-risk actions | Force `suggest`/approval mode + hard stop |
| Human approval gate | Native | Callback policy can drift from platform policy | Secondary UX gate for user-facing operations | Treating it as final governance authority | Keep Kai governance as terminal gate |
| Async jobs submit/status/result | Native | API auth may be deployment-dependent | Long-running offloaded tasks and cross-service workloads | Fire-and-forget without idempotency | Use idempotency + persisted reconciliation |
| Async streaming progress (SSE) | Native | SSE client/state management needed | Operator observability, live mission panels | Using stream as sole state source | Polling with `retry_after` intervals |
| Event-driven queue workflow | Native | Eventual consistency and replay complexity | Batch and non-interactive campaign expansion | Compliance-critical state mutation without sync checks | Deterministic MissionRuntime state merge |
| MCP tool federation | Native | Auth/scopes/cursor pagination handling required | External tool ecosystem integration | Direct trust in external tool schema/output | Normalize via Kai tool adapters + schema validation |
| MCP elicitation (form/url) | Native | URL mode required for sensitive flows | User confirmation and external consent steps | Passing sensitive form data through weak channels | Force URL-mode + explicit approval linkage |
| A2A protocol exchange | Native | Identity and trust semantics externalized | Controlled inter-agent boundary with explicit contracts | Cross-tenant/open trust assumptions | Signed envelope + contract validation |
| AG-UI interaction stream | Native | Transport-level concerns (ordering/reconnect) | Rich UI streaming for assistant sessions | Driving mission truth from UI events | EventBus as source of truth |
| Retrieval-augmented response | Native | Quality and token budget tuning required | Analyst assist, context expansion, citations | Using retrieval outputs as unverified evidence | Evidence verification node + confidence threshold |
| Quality-scored memory store | Native | Scoring variance and threshold calibration | Preference/context memory for repeated operations | Auto-promoting low-confidence content | Threshold + periodic memory compaction |
| Graph memory relationships | Partial/Advanced | Operational complexity (graph DB, schema drift) | Relationship-heavy analyst context | Overusing for short-lived workflow state | Use standard store + derived graph views |
| Cross-framework execution (CrewAI/AG2) | Native bridge | Requires `roles` YAML and schema translation | Controlled compatibility mode for imported teams | Assuming parity with praison `steps` workflows | Canonical schema compiler to target framework |
| CLI invocation model | Native | Process overhead and parsing fragility | CI automation and scripting glue | High-frequency low-latency paths | Embedded SDK or sidecar API |
| Local sidecar HTTP runner | Native | Service lifecycle + auth config required | Polyglot integration boundary | Public exposure without auth hardening | Local-only bind + gateway auth |
| Remote managed runner | Native/Pattern | Higher operational complexity | Multi-tenant external execution plane | Directly binding to mission-critical control path | Keep as optional enrichment backend |
| No-code YAML generation | Native | Generated configs can be underspecified | Rapid prototyping and template generation | Direct production deployment of generated configs | Compile through validation lint + policy checks |

## Cross-Links
- Capability map: [praison_capability_map.md](/home/k1-admin/Kai/docs/research/praison_capability_map.md)
- Integration architecture: [praison_kai_integration.md](/home/k1-admin/Kai/docs/architecture/praison_kai_integration.md)
- Persona mapping: [praison_persona_mapping.md](/home/k1-admin/Kai/docs/integrations/praison_persona_mapping.md)
- Roadmap: [praison_implementation_roadmap.md](/home/k1-admin/Kai/docs/architecture/praison_implementation_roadmap.md)
