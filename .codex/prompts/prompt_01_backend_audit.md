Read and follow AGENTS.md before performing any action.

You are working inside the Kai / K1 repository.

Your task is to audit this repository and produce an implementation plan for converting Kai/K1 into a real autonomous bug bounty backend with:
- resumable phase execution
- branch-aware orchestration
- human-in-the-loop approval gates
- explicit intention tracking for every significant decision and action

Do not ask for permission.
Inspect the codebase first.
Do not begin large-scale implementation yet unless a tiny helper change is absolutely necessary for inspection.

Primary objective:
Determine whether the current backend truly supports autonomous bug bounty execution across all phases, or whether the current behavior is simulated, stubbed, incomplete, disconnected, or documentation-only.

Audit goals:
1. Identify the actual backend entrypoints, routers, services, models, workers, queues, persistence layers, and execution paths.
2. Determine whether the “begin scan” path is fully wired from:
   frontend trigger
   -> API route
   -> persisted campaign/scan record
   -> queued execution
   -> phase runner
   -> tool execution
   -> artifact creation
   -> status/log updates
   -> finding persistence
3. Find all missing pieces, dead stubs, mock/simulated paths, and documentation-only claims.
4. Determine whether the backend already contains any support for:
   - resumable jobs
   - branch execution
   - human approval gates
   - policy/risk classification
   - artifact persistence
   - report generation
   - audit logging
   - agent/tool orchestration
5. Specifically audit whether there is any concept of “intention” in the current backend.
   Intention means the declared purpose behind a scan, phase, tool execution, decision, escalation, or approval request.
   If missing, identify exactly where intention tracking should exist in the future architecture.

Required analysis focus:
- current backend structure
- current scan execution path
- current worker/background execution path
- current database model coverage
- current approval or pause/resume logic
- current logging/audit trail quality
- current artifact generation/storage flow
- current tool execution model
- current security boundary enforcement
- current support for parallelism and non-blocking branch continuation
- current support for explicit intention tracking

Create these files:
1. docs/backend_gap_audit.md
2. docs/backend_execution_plan.md

Requirements for docs/backend_gap_audit.md:
- current backend structure
- current scan execution path
- missing orchestration layers
- missing persistence models
- missing worker/runtime pieces
- missing approval-gate logic
- missing artifact/logging pipeline
- missing or weak audit trail elements
- missing or weak intention-tracking elements
- exact files that appear incomplete, simulated, dead, or misleading
- exact files that likely need to be created or modified
- a dedicated final section titled:
  Intention Tracking Gap Analysis

Requirements for docs/backend_execution_plan.md:
- recommended implementation order
- which pieces should be built first to make “begin scan” real
- where intention should be introduced as a first-class concept
- recommended domain entities for intention-aware execution
- recommended strategy for resumable branch-based orchestration
- recommended strategy for HiL pauses that block only dependent branches
- risks, unknowns, and assumptions
- a dedicated final section titled:
  Recommended Intention-Aware Orchestration Design

Rules:
- inspect before changing architecture
- be explicit about uncertainty
- do not claim functionality that cannot be proven from code
- clearly distinguish implemented behavior from intended behavior
- preserve current public API contracts where practical
- prefer the stack already implied by the repository if present
- do not perform broad implementation yet
- if useful, create helper notes under docs/audit_notes/

Important:
At the end of your work, provide a concise terminal summary listing:
- what you inspected
- what you created
- the top 5 most important findings
- the top 5 most important backend gaps
- whether “begin scan” is real, partial, simulated, or broken

Be brutally honest. No decorative nonsense.
