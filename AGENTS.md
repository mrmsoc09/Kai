This file defines the operational rules for AI coding agents working in this repository.
All agents must read and follow this file before making architectural or code changes.

# AGENTS.md

## Project Identity
Kai / K1 is being developed into a real autonomous bug bounty orchestration platform with:
- resumable phase-based execution
- branch-aware workflows
- human-in-the-loop approval gates
- explicit intention tracking for every significant decision and action
- real backend-driven tool execution
- persistent findings, artifacts, notes, and audit trails

This repository must evolve away from simulated scan behavior and toward provable backend execution.

---

## Primary Mission
When working in this repository, prioritize converting Kai into a production-grade backend system for autonomous bug bounty hunting.

The system must support:
1. Real campaign creation and execution
2. Persistent scan/campaign state
3. Queue-backed job orchestration
4. Branch-local pause/resume for human approvals
5. Real tool execution through controlled runtimes
6. Structured observations, findings, artifacts, and notes
7. Intention-aware decision logging
8. Honest documentation of implemented vs planned behavior

---

## Core Engineering Principles

### 1. No Fake Completion
Do not claim a feature is implemented unless the code path exists and is testable.

Always distinguish between:
- implemented behavior
- partial behavior
- stubbed behavior
- simulated behavior
- planned behavior

### 2. Inspect Before Changing
Before making architectural changes:
- inspect the existing codebase
- identify the real execution path
- identify dead stubs and simulated flows
- preserve working contracts where practical

### 3. Intention Is First-Class
Every meaningful action in the system should eventually support explicit intention metadata.

Intention means:
- who initiated the action
- why the action is being taken
- what goal it is intended to achieve
- whether it is allowed by scope/policy
- whether it changes risk posture
- whether it should require human approval

Intention must influence:
- orchestration decisions
- approval gates
- audit logs
- tool execution policy
- reporting context

### 4. Branch-Local Human Approval
If one scan branch needs approval, only that dependent branch should pause.

Other independent and policy-allowed branches should continue running.

Never design the system so a single approval gate freezes the entire campaign unless explicitly required.

### 5. LLMs Do Not Own Truth
LLMs may assist with reasoning and summaries, but source-of-truth data must live in structured persistence layers:
- database records
- artifacts
- observations
- logs
- findings
- approval records

### 6. Security and Auditability
All meaningful decisions should be explainable after the fact.

The backend should be designed for:
- audit trails
- reproducibility
- scope enforcement
- policy checks
- artifact lineage
- operator review

---

## Preferred Architecture
Unless the repository already proves a better pattern, prefer:

- API / control plane: FastAPI
- Database: PostgreSQL
- Queue / broker: Redis
- Workers: Celery or equivalent robust background execution system
- Artifacts: filesystem or object storage abstraction
- Tool runtime: isolated worker/container execution
- Frontend integration: polling, SSE, or WebSocket updates
- Migrations: Alembic
- Tests: pytest

If existing architecture differs, inspect first and adapt rather than rewriting blindly.

---

## Domain Design Expectations
The backend should move toward these concepts:

- Program
- ScopeTarget
- CampaignRun
- PhaseJob
- ApprovalGate
- ToolExecution
- Observation
- Artifact
- Finding
- ScanNote
- SubmissionDraft
- AuditEvent
- IntentionRecord or equivalent intention-aware fields

All execution should be traceable through persisted records.

---

## Expected Workflow for Repository Changes

### Phase 1: Audit
Before major implementation:
- inspect the current backend and scan path
- document real behavior
- identify missing layers
- identify simulated paths
- identify missing intention support

### Phase 2: Domain Modeling
Create or refine:
- persistence models
- schemas
- state transitions
- branch dependency rules
- approval semantics
- intention-aware entities

### Phase 3: Orchestration
Implement:
- campaign creation
- job graph scheduling
- dependency-aware dispatch
- branch-local pause/resume
- retry and failure handling
- artifact/log persistence

### Phase 4: Runtime Integration
Implement:
- tool adapters
- controlled execution runtime
- parsed outputs
- evidence capture
- risk and intention-aware policy checks

### Phase 5: Reporting
Implement:
- finding normalization
- evidence packaging
- submission-draft generation
- final approval workflow

### Phase 6: Hardening
Implement:
- structured logging
- metrics
- health checks
- queue diagnostics
- audit events
- production readiness docs

---

## Documentation Rules
For any meaningful architecture change, create or update docs under `docs/`.

Expected documentation types:
- backend audit
- execution plan
- domain model
- orchestration design
- approval flow
- runtime isolation
- memory graph design
- reporting pipeline
- operations runbook
- production readiness checklist

Documentation must be honest and specific.

---

## Testing Rules
When implementing backend behavior:
- add tests for state transitions
- add tests for branch pause/resume
- add tests for approval handling
- add tests for persistence behavior
- add tests for tool execution parsing where practical

Do not leave critical orchestration logic untested.

---

## Editing Rules
When making code changes:
- prefer small, coherent commits
- preserve public interfaces where practical
- avoid unnecessary rewrites
- do not remove useful docs unless replacing them with better docs
- do not silently break scan flow contracts

When uncertainty exists, document it.

---

## Forbidden Behaviors
Do not:
- fake backend execution with frontend-only simulation and present it as real
- treat intention as optional metadata
- let one approval gate block unrelated safe branches
- store critical truth only in model output text
- claim production readiness without worker, persistence, and audit paths
- hide missing features behind vague wording

---

## Definition of Success
A successful backend implementation means:
- “begin scan” creates a real persisted campaign
- jobs are queued and executed by workers
- logs and artifacts are written and retrievable
- findings are persisted
- risky branches can pause for HiL approval
- unrelated branches can continue
- every major decision/action can be explained through intention-aware audit data
- docs and tests reflect reality

---

## Instruction to Coding Agent
Your job is not to make the repository look advanced.
Your job is to make the repository actually work.

Always prefer provable execution over impressive wording.
Always surface uncertainty honestly.
Always treat intention, auditability, and branch-aware approval logic as major design requirements.

---

# AGENTS.md

Kai Autonomous Security Research Platform
AI Development Specification

---

# 1. Purpose

Kai (K1) is an autonomous security research and bug bounty orchestration platform.

The platform is designed to assist security researchers by automating:

* Opportunity intelligence
* Asset discovery
* Reconnaissance
* Vulnerability signal detection
* Evidence collection
* Benchmark validation
* Reporting preparation

Kai is designed as a **defensive research platform operating within authorized scopes only**.

Kai must **never perform unauthorized scanning or exploitation**.

---

# 2. Platform Development Priorities

Kai development must maintain equal priority across:

1. Core platform backend
2. Tool orchestration and automation scripts
3. Evidence and intelligence engines
4. System installers and update systems
5. Worker infrastructure
6. Operator UI/UX

Frontend improvements must **never come at the expense of backend capability or platform automation**.

Kai is primarily an **automation and intelligence platform**, not a UI-first product.

---

# 3. Platform Architecture

Kai consists of six primary subsystems.

---

## 3.1 Opportunity Intelligence Engine

This subsystem selects and ranks bug bounty opportunities.

Inputs include:

* program scope
* payout likelihood
* payout amount
* platform popularity
* recent vulnerability reports
* exploit availability
* exposed technologies
* recon intelligence

Sources include:

* NVD
* ExploitDB
* CISA KEV
* vendor advisories
* threat intelligence feeds
* recon results

The system produces **ranked hunt plans**.

Each plan must include:

* target ranking
* vulnerability pressure score
* expected effort cost
* reasoning summary
* supporting evidence references

Location:

```
core/intelligence/
```

---

## 3.2 Scope and Authorization Gate

All scanning and testing must pass through scope validation.

Required validation:

* program identifier
* authorization certificate
* allowed testing methods
* excluded assets

No tool may run without scope validation.

All tool execution must call:

```
scope_validator()
authorization_certificate_check()
```

---

## 3.3 Tool Orchestration Layer

Kai orchestrates tools using workers.

Workers must:

* enforce OPSEC limits
* control rate limits
* capture artifacts
* generate evidence objects
* respect scope validation

Workers run in asynchronous queues.

Location:

```
workers/
```

---

## 3.4 Tool Adapter Layer

External tools must be wrapped in adapters.

Adapters provide:

* input schema
* safe execution
* output normalization
* evidence generation

Location:

```
adapters/
```

Adapters must never be bypassed.

---

## 3.5 Evidence and Knowledge Layer

All findings must produce **Evidence Objects**.

Evidence objects provide:

* normalized data
* artifact hashes
* provenance tracking
* confidence scoring

Evidence objects are stored in:

```
core/evidence/
```

Evidence is indexed for retrieval using:

* vector search
* graph relationships
* artifact storage

LlamaIndex or equivalent may be used.

---

## 3.6 Platform Operations Layer

Kai includes operational tooling to support the platform.

Responsibilities include:

* system installation
* dependency management
* weekly tool updates
* health monitoring
* platform benchmarking

Location:

```
ops/
```

---

# 4. Supported Operating Systems

Primary supported systems:

* Debian 13
* Ubuntu 22.04 LTS

Compatible environments:

* Kali Linux
* Parrot Security OS
* Tsurugi OS

Primary testing must occur on Debian and Ubuntu.

Other systems are supported through containerized toolpacks.

---

# 5. Toolpack Architecture

Kai manages external tools using toolpacks.

A toolpack defines:

* tool installation method
* update method
* adapter mapping
* evidence output type
* required dependencies

Example toolpack categories:

Recon Tools
Vulnerability Detection
OSINT
Mobile Security
Supply Chain Security
Threat Intelligence
Automation Systems
SOC Integration

Toolpacks must be defined in:

```
ops/toolpacks.yaml
```

---

# 6. Supported Tool Ecosystem

Kai supports integration with the following tools.

Recon and Asset Discovery

* Subfinder
* Amass
* PureDNS
* Dnsx
* Massdns
* Naabu
* Nmap
* Masscan
* Httpx
* Httprobe
* Wafw00f
* BuiltWith
* Gau
* Waymore

Web and API Testing

* ffuf
* Feroxbuster
* Arjun
* ParamMiner
* LinkFinder
* SecretFinder
* Nuclei
* Dalfox
* Sqlmap
* XSStrike
* Commix

OSINT and Intelligence

* Spiderfoot
* Sherlock
* Maigret
* Social Analyzer
* Lampyre
* IntelX
* BreachDirectory
* Hudson Rock Cavalier
* Flare.io

Infrastructure Intelligence

* Shodan
* Censys
* Hunter.io
* crt.sh

Mobile and Reverse Engineering

* Frida
* Objection
* MobSF
* Ghidra
* Jadx

AI Security Testing

* Garak
* PyRIT

Supply Chain Security

* Trivy
* Syft
* Grype
* Cycode
* Socket.dev
* Snyk
* Endor Labs

Automation and Security Platforms

* n8n
* Shuffle
* TheHive
* Cortex
* Wazuh

Bug Bounty Infrastructure

* Rengine
* BBRF
* Axiom

Security Testing Suites

* Burp Suite Pro
* Caido
* OWASP ZAP

Monitoring and Analysis

* Wireshark
* Cyber Triage
* PlexTrac

Threat Intelligence Platforms

* Wiz
* Sysdig Secure
* ThreatModeler
* Vanta
* Chainalysis Reactor

Agent and Automation Frameworks

* Agent-Zero
* LangChain
* LangGragh
* LangSmith
* DeepAgents
* Praison AI
* CAI
* PentAGI
* PentestAgents

Knowledge Systems

* LlamaIndex
* VertexAI

---

# 7. Tool Adapter Contract

All tools must implement adapters.

Example:

```
class ToolAdapter(BaseAdapter):

    tool_id: str
    version: str
    supported_targets: list

    async def run(self, target, config):
        pass
```

Adapters must:

* enforce OPSEC rules
* normalize outputs
* generate evidence objects
* store artifacts

Artifacts must be written to:

```
artifacts/<run_id>/<tool_id>/
```

Artifacts must include SHA256 hashes.

---

# 8. Evidence Object Schema

Evidence objects contain:

```
evidence_id
type
tool
target
timestamp
structured_data
confidence_score
artifacts
scope_status
```

Artifact metadata must include:

```
artifact_path
sha256
mime_type
description
```

---

# 9. Benchmark and Proof Engine

Kai must validate all platform claims using benchmark scenarios.

Benchmarks must run on:

* synthetic datasets
* offline fixtures
* deterministic inputs

Location:

```
benchmarks/
```

Metrics include:

Coverage

```
discovered_assets / total_assets
```

Precision

```
true_positives / reported_positives
```

Recall

```
true_positives / ground_truth
```

Runtime

```
total_execution_time
```

Cost

```
LLM token usage
API usage
```

Reliability

```
error_rate
retry_rate
```

---

# 10. Claim Registry

Platform capability claims must be defined in:

```
claims/claims.yaml
```

Each claim must include:

* metric
* threshold
* benchmark scenario
* validation condition

Claims must be validated automatically during benchmark runs.

---

# 11. Weekly Tool Update System

Kai must maintain weekly tool updates.

Update automation scripts live in:

```
ops/update_weekly.sh
```

Updates must:

* refresh tool repositories
* rebuild docker toolpacks
* update adapters
* validate version outputs
* run health checks

Updates must not break adapter compatibility.

---

# 12. Testing Requirements

Each tool adapter must include tests.

Required tests:

* adapter contract test
* output normalization test
* artifact hash test
* benchmark fixture test

Tests must not perform external scanning.

Fixtures must live in:

```
tests/fixtures/
```

---

# 13. Coding Rules

Allowed:

* typed Python code
* async execution
* modular architecture
* Pydantic schemas

Forbidden:

* direct CLI parsing in API layer
* bypassing adapter interfaces
* writing artifacts outside artifact directories
* embedding secrets in code

---

# 14. Documentation Requirements

New tools must update documentation.

Required files:

```
docs/cheatsheets/tool_adapters.md
docs/cheatsheets/operator_playbook.md
docs/cheatsheets/evidence_model.md
```

---

# 15. Development Workflow

When implementing a new tool:

1 Create adapter skeleton
2 Implement parser
3 Normalize evidence output
4 Add tests
5 Add benchmark scenario
6 Update documentation

---

# 16. Safety Policy

Kai must not generate or execute code that:

* performs exploitation
* performs denial of service
* bypasses scope validation
* automates credential attacks

Kai is strictly a **defensive research platform**.

---

# 17. AI Agent Responsibilities

AI coding agents working on this repository must:

* preserve architecture
* respect tool adapter contracts
* enforce evidence schemas
* maintain reproducible benchmarks
* respect authorization boundaries

When uncertain about architecture, agents must propose changes rather than implementing them directly.

---
