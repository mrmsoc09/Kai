# LangStudio Orchestration Matrix

Decision matrix for choosing LangGraph, DeepAgents, Praison, or custom Kai runtime patterns.

| Pattern | LangGraph | DeepAgents | Praison | Custom runtime | Kai recommendation | Avoid/Caution | Fallback |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Deterministic stage DAG with approvals | Strong | Medium | Medium | Medium | LangGraph primary + Kai governance gates | Avoid implicit transitions without checkpoints | Pause + resume from checkpoint |
| Long-running resumable investigations | Strong | Strong | Medium | Medium | LangGraph threads/checkpoints | Avoid volatile in-memory-only state | Persistent checkpointer + replay mode |
| Specialist deep analysis with decomposition | Medium | Strong | Medium | Low | DeepAgents node under contract and limits | Avoid unrestricted local shell/filesystem backends | Route to constrained LangChain tool loop |
| Rapid single-agent assistant flow | Medium | Medium | Strong | Medium | Praison or LangChain quick path for low-risk tasks | Avoid using this for mission-critical pipelines | Promote to LangGraph flow when complexity rises |
| Multi-agent parallel sub-work streams | Strong | Strong | Medium | Medium | LangGraph subgraphs + DeepAgents for specialist branches | Avoid unbounded fan-out and namespace collisions | Cap concurrency and serialize branches |
| Human-in-the-loop tool approval | Strong | Strong | Strong | Low | LangGraph/DeepAgents interrupt + Kai terminal approval | Avoid HITL without checkpointer/thread discipline | Force sync approval gate in Kai |
| External protocol interoperability (MCP/A2A) | Medium | Medium | Strong | Medium | Praison-facing protocol bridge normalized into Kai | Avoid direct external protocol trust | Canonical schema adapter + rejection path |
| High-security multi-tenant execution | Medium | Medium | Medium | Strong | Kai custom policy layer over LangGraph runtime | Avoid shared memory namespaces and host shell backends | Tenant-scoped namespaces + sandbox backends |
| Tool-heavy deterministic automation | Strong | Medium | Medium | Strong | LangGraph + Kai wrappers | Avoid bypassing wrapper provenance | Wrapper-only dispatch and retries |
| No-code operator flow creation | Low | Low | Strong | Low | Praison for operator UX, compile into Kai-safe plans | Avoid direct no-code output execution | Compile/validate plan before run |
| Evaluation-driven improvement loop | Medium | Medium | Medium | Medium | LangSmith eval + Kai strategy learning loop | Avoid model-only judge with no regression dataset | Hybrid evaluators (rule + LLM + human) |
| Ultra-low-latency stateless request | Low | Low | Medium | Strong | Custom lightweight runtime path | Avoid full graph overhead for trivial requests | Stateless endpoint with strict timeout |

## Operating Rule

- Default choice: LangGraph for orchestration, LangChain for node intelligence, DeepAgents only where specialist autonomy is net-positive.
- Praison remains control-plane and interoperability support, not runtime truth.
