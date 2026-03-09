#!/usr/bin/env bash
set -euo pipefail

# Kai Codex bootstrap
# Run this from the Kai repository root:
#   chmod +x bootstrap_codex_kai.sh
#   ./bootstrap_codex_kai.sh

REPO_ROOT="${1:-$(pwd)}"

if [[ ! -d "$REPO_ROOT" ]]; then
  echo "[ERROR] Repo path does not exist: $REPO_ROOT"
  exit 1
fi

cd "$REPO_ROOT"

echo "[*] Working in: $(pwd)"

mkdir -p .codex/agents
mkdir -p .codex/prompts
mkdir -p .codex/hooks
mkdir -p docs/audit_notes

# -------------------------------------------------------------------
# AGENTS.md handling
# -------------------------------------------------------------------
AGENTS_FILE="AGENTS.md"
BACKUP_SUFFIX="$(date +%Y%m%d_%H%M%S)"
TMP_FILE="$(mktemp)"

read -r -d '' AGENTS_HEADER <<'EOF' || true
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
EOF

if [[ -f "$AGENTS_FILE" ]]; then
  if grep -q "This file defines the operational rules for AI coding agents working in this repository." "$AGENTS_FILE"; then
    echo "[*] AGENTS.md already contains the managed header. Leaving it in place."
  else
    cp "$AGENTS_FILE" "${AGENTS_FILE}.bak.${BACKUP_SUFFIX}"
    {
      printf "%s\n\n" "$AGENTS_HEADER"
      cat "$AGENTS_FILE"
    } > "$TMP_FILE"
    mv "$TMP_FILE" "$AGENTS_FILE"
    echo "[*] Existing AGENTS.md backed up to ${AGENTS_FILE}.bak.${BACKUP_SUFFIX}"
    echo "[*] Managed instruction header prepended to AGENTS.md"
  fi
else
  printf "%s\n" "$AGENTS_HEADER" > "$AGENTS_FILE"
  echo "[*] Created new AGENTS.md"
fi

# -------------------------------------------------------------------
# .codex/config.toml
# -------------------------------------------------------------------
cat > .codex/config.toml <<'EOF'
# Codex project configuration for Kai / K1

project_name = "Kai"
default_model = "gpt-5-codex"
temperature = 0.2

[context]
read_agents_md = true
prefer_repo_local_rules = true

[execution]
approval_mode = "manual"
allow_parallel_planning = true
intention_tracking = true

[paths]
prompts_dir = ".codex/prompts"
agents_dir = ".codex/agents"
hooks_dir = ".codex/hooks"
docs_dir = "docs"
EOF

# -------------------------------------------------------------------
# Agent configs
# -------------------------------------------------------------------
cat > .codex/agents/orchestrator.toml <<'EOF'
name = "orchestrator"
role = "Primary backend planning and orchestration agent"
focus = [
  "backend architecture",
  "scan execution flow",
  "branch-aware orchestration",
  "approval gates",
  "intention-aware design"
]
must_read = ["AGENTS.md"]
EOF

cat > .codex/agents/recon_agent.toml <<'EOF'
name = "recon_agent"
role = "Reconnaissance and discovery workflow specialist"
focus = [
  "passive recon",
  "asset discovery",
  "URL collection",
  "non-intrusive scan phases",
  "artifact collection"
]
must_read = ["AGENTS.md"]
EOF

cat > .codex/agents/vuln_agent.toml <<'EOF'
name = "vuln_agent"
role = "Validation and finding-correlation specialist"
focus = [
  "template-based validation",
  "finding normalization",
  "evidence generation",
  "risk posture analysis",
  "approval-required transitions"
]
must_read = ["AGENTS.md"]
EOF

cat > .codex/agents/reporting_agent.toml <<'EOF'
name = "reporting_agent"
role = "Reporting and evidence packaging specialist"
focus = [
  "submission drafts",
  "report generation",
  "artifact manifests",
  "operator review readiness",
  "audit-friendly summaries"
]
must_read = ["AGENTS.md"]
EOF

# -------------------------------------------------------------------
# Prompt #1
# -------------------------------------------------------------------
cat > .codex/prompts/prompt_01_backend_audit.md <<'EOF'
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
EOF

# -------------------------------------------------------------------
# Optional future prompt placeholders
# -------------------------------------------------------------------
cat > .codex/prompts/README.md <<'EOF'
Store sequential Codex prompt-chain files here.

Suggested sequence:
1. prompt_01_backend_audit.md
2. prompt_02_domain_model.md
3. prompt_03_orchestration.md
4. prompt_04_tool_runtime.md
5. prompt_05_memory_and_findings.md
6. prompt_06_frontend_integration.md
7. prompt_07_reporting.md
8. prompt_08_hardening.md
9. prompt_09_final_integration.md
EOF

# -------------------------------------------------------------------
# Hook scripts
# -------------------------------------------------------------------
cat > .codex/hooks/intention_check.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "[HOOK] Intention check placeholder: ensure major code changes document purpose, scope, and risk posture."
exit 0
EOF
chmod +x .codex/hooks/intention_check.sh

cat > .codex/hooks/run_tests.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
echo "[HOOK] Test runner placeholder: connect pytest/npm test here when backend path is known."
exit 0
EOF
chmod +x .codex/hooks/run_tests.sh

# -------------------------------------------------------------------
# Helpful readme for .codex
# -------------------------------------------------------------------
cat > .codex/README.md <<'EOF'
This directory contains Codex project-local configuration for Kai / K1.

Contents:
- config.toml      : project runtime/config hints
- agents/          : specialized task agent definitions
- prompts/         : reusable prompt-chain files
- hooks/           : helper scripts for future automation

AGENTS.md stays in the repository root because it is the primary instruction file.
EOF

echo
echo "[DONE] Kai Codex bootstrap complete."
echo
echo "Created/updated:"
echo "  - AGENTS.md"
echo "  - .codex/config.toml"
echo "  - .codex/agents/*.toml"
echo "  - .codex/prompts/prompt_01_backend_audit.md"
echo "  - .codex/hooks/*.sh"
echo "  - docs/audit_notes/"
echo
echo "Next steps:"
echo "  1. Review AGENTS.md"
echo "  2. Start Codex from repo root"
echo "  3. Paste or load .codex/prompts/prompt_01_backend_audit.md"
echo
echo "Example:"
echo "  codex"
