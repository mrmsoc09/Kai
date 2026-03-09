# Kai Gap Closure TODO

## Legend
- Effort: S/M/L
- Priority: Critical/High/Medium/Low

| ID | Priority | Task | Owner | Effort | Dependencies | Definition of Done | Validation |
|---|---|---|---|---|---|---|---|
| T-001 | Critical | Canonicalize `ops/toolpacks.yaml` and startup path | Backend/SRE | S | none | Startup resolves toolpacks from `ops/` without ambiguity | `python3 scripts/validate_claims.py` + startup smoke |
| T-002 | Critical | Add and maintain `claims/claims.yaml` thresholds | SecOps/Product | M | T-003 | Claims file complete with scenario coverage | `python3 scripts/validate_claims.py` |
| T-003 | Critical | Deterministic `benchmarks/` suite with fixtures | Backend | M | none | Offline deterministic benchmark runner in CI | `python3 scripts/run_benchmarks.py --verify-claims` |
| T-004 | Critical | Persist authorization certificates and decisions | Backend | M | DB migration | Cert/audit survives restart | migration tests + API integration |
| T-005 | Critical | Canonical Evidence Object schema parity | Backend | M | T-004 | All producers/consumers aligned | schema contract tests |
| T-006 | High | Artifact hash revalidation at report assembly | Backend | S | T-005 | Tampered artifacts are rejected | unit test with modified artifact |
| T-007 | High | Adapter contract fixtures for critical tools | SecOps/Backend | M | T-005 | Critical adapters pass normalization/hash tests | `pytest apps/backend/tests/test_adapter_*` |
| T-008 | High | OPSEC policy engine (rate/concurrency budget) | Backend/SRE | M | T-007 | Worker dispatch policy-enforced | integration tests |
| T-009 | Critical | Submission lifecycle state machine | Backend/Product | L | T-005 | Full status transitions with audit | API integration tests |
| T-010 | High | SLA timers and next-action prompts | Backend/Frontend | M | T-009 | Timers and prompts visible in UI | UI/API tests |
| T-011 | High | Unified comms inbox linked to finding/report | Backend/Frontend | L | T-009 | Threads fully linked by IDs | end-to-end tests |
| T-012 | Medium | Approval-gated AI draft replies | Backend/Product | M | T-011 | No outbound auto-send without approval | policy and unit tests |
| T-013 | Critical | Payout ledger schema and APIs | Backend/Finance | M | T-009 | Expected vs actual payout tracked | accounting API tests |
| T-014 | High | Monthly reconciliation export | Backend/Finance | S | T-013 | Monthly statement generated | snapshot tests |
| T-015 | High | Opportunity scoring v1 (EV + duplicate risk) | Backend/Product | M | T-003 | Ranked hunt plans with score factors | unit tests |
| T-016 | High | Pre-submit duplicate-risk gate | Backend/Product | M | T-015 | High duplicate risk requires override | submission gate tests |
| T-017 | High | Report quality gate + trace matrix | Backend/Product | M | T-005 | Report blocked until quality threshold met | report validator tests |
| T-018 | Medium | Hybrid retriever (vector + graph provenance) | Backend/ML | L | T-015 | Provenance-ranked retrieval in prod path | retrieval benchmarks |
| T-019 | High | Defensive-only DAG semantics refactor | Backend | M | none | No exploitation-phase semantics remain | orchestration tests |
| T-020 | Medium | Reflective loop tied to reject/duplicate outcomes | Backend/ML | M | T-016 | Bounded updates + reason logs | simulation tests |
| T-021 | High | Complete Vault secret migration inventory closure | SecOps/Backend | M | T-002 | No unmanaged prod secret reads | static checks + startup checks |
| T-022 | Medium | Weekly updates with compatibility gate | SRE | M | T-007 | Update job fails on adapter incompatibility | CI scheduled run |
| T-023 | Medium | Readiness endpoint with governance status | Backend/SRE | S | T-002,T-003 | Readiness reports claim/policy status | API tests |
| T-024 | High | KPI dashboard for acceptance/net payout | Product/Frontend | M | T-013,T-016 | Weekly/monthly KPI views + export | UI/API tests |
