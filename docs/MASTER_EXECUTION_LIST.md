# Kai Master Execution List

This is the single merged execution list combining:
- gap-closure backlog
- AI workflow placement requirements

No timeline fields are included by design.
Status values: `done`, `in_progress`, `todo`, `blocked`.

| ID | Status | Task | Owner | Dependencies | Definition of Done | Validation |
|---|---|---|---|---|---|---|
| M-001 | done | Canonicalize `ops/toolpacks.yaml` and startup toolpack policy loading | Backend/SRE | none | Startup resolves canonical toolpack source and passes schema validation | `python3 scripts/validate_claims.py` + startup smoke |
| M-002 | done | Create `claims/claims.yaml` with measurable thresholds | SecOps/Product | none | Claims registry exists and passes validator | `python3 scripts/validate_claims.py` |
| M-003 | done | Create deterministic benchmark harness + fixtures | Backend | none | Fixture-only benchmark runner exists and is deterministic | `python3 scripts/run_benchmarks.py --verify-claims` |
| M-004 | done | Persist authorization certificates and authorization decisions (immutable ledger) | Backend/SecOps | none | Certs/decisions survive restart and are queryable for audit | unit + integration tests |
| M-005 | done | Enforce canonical Evidence Object schema parity across all producers/consumers | Backend | M-004 | No schema divergence across adapters/report pipeline | schema contract tests |
| M-006 | done | Add artifact hash revalidation in report assembly | Backend | M-005 | Report assembly rejects tampered/missing artifacts | unit tests with tamper cases |
| M-007 | done | Complete critical adapter contract fixtures and normalization tests | Backend/SecOps | M-005 | Critical adapters pass contract and fixture tests | `pytest apps/backend/tests/test_adapter_*` |
| M-008 | done | Implement central OPSEC policy engine (rate/concurrency/budget by method) | Backend/SRE | M-007 | Worker dispatch is policy-governed and auditable | integration tests |
| M-009 | done | Build submission lifecycle state machine with auditable transitions | Backend/Product | M-005 | Full submission states and transition guards implemented | API integration tests |
| M-010 | done | Add SLA timers and next-action prompts for submissions | Backend/Frontend | M-009 | Timers/prompts surfaced and persisted | UI/API tests |
| M-011 | done | Build unified comms inbox linked to finding/report threads | Backend/Frontend | M-009 | Every comm thread maps to run/finding/report IDs | end-to-end tests |
| M-012 | done | Add approval-gated AI draft replies for stakeholder comms | Backend/Product | M-011 | No outbound send without explicit approval | policy tests |
| M-013 | done | Implement payout ledger (`expected`,`actual`,`fees`,`net`) | Backend/Finance | M-009 | Accepted findings link to payout records | accounting API tests |
| M-014 | done | Add monthly payout reconciliation export | Backend/Finance | M-013 | Reconciliation report generated and reproducible | snapshot tests |
| M-015 | done | Implement opportunity score v1 (EV + duplicate risk + effort) | Backend/Product | M-003 | Ranked plans produced with explainable factors | scorer unit tests |
| M-016 | done | Add pre-submit duplicate-risk gate | Backend/Product | M-015 | High duplicate-risk submissions require override | gate tests |
| M-017 | done | Add report quality gate with evidence-to-claim trace matrix | Backend/Product | M-005 | Submission blocked below quality threshold | report validator tests |
| M-018 | done | Implement hybrid retriever (vector + graph provenance ranking) | Backend/ML | M-015 | Retrieval returns provenance-ranked context | retrieval benchmarks |
| M-019 | done | Refactor DAG semantics to defensive-only phases | Backend | none | No exploitation semantics in orchestration state machine | orchestration tests |
| M-020 | done | Integrate bounded reflective learning using reject/duplicate outcomes | Backend/ML | M-016 | Tactic updates bounded, logged, and reversible | simulation tests |
| M-021 | done | Complete Vault migration inventory and close unmanaged secret reads | SecOps/Backend | M-002 | Production secret paths only via secret manager | static checks + startup checks |
| M-022 | done | Add weekly update compatibility gate for toolpacks/adapters | SRE | M-007 | Update pipeline fails on adapter incompatibility | CI scheduled run |
| M-023 | done | Add governance readiness endpoint (policy/claims/benchmark status) | Backend/SRE | M-002,M-003 | Readiness endpoint reports governance state | API tests |
| M-024 | done | Build KPI dashboard (acceptance, duplicates, throughput, net payout) | Product/Frontend | M-013,M-016 | Weekly/monthly KPI views available and exportable | UI/API tests |
| M-025 | done | Implement AI skill router with signed context contracts | Backend/ML | M-004 | Skill invocations require run/program/cert context signature | unit tests |
| M-026 | done | Implement hook registry (pre-run/post-run/approval/retry/safety hooks) | Backend | M-008 | Hook chain deterministic and auditable | integration tests |
| M-027 | done | Add confidence policy engine for LLM decisions (stop/escalate rules) | Backend/ML | M-017 | Low-confidence outputs trigger deterministic fallback/HIL | policy tests |
| M-028 | done | Add model decision observability (cost/latency/quality/confidence) | Backend/SRE | M-027 | Per-location metrics emitted for all AI decision points | telemetry tests |
| M-029 | done | Add non-bypassability CI checks for scope/auth + adapter-only execution | SecOps/Backend | M-026 | CI fails when execution path lacks mandatory gates | negative tests |
| M-030 | done | Add claims for accepted-rate and payout-efficiency leading indicators | Product/Finance | M-024 | Outcome KPI claims tracked and thresholded | benchmark + KPI checks |
