# K1 Project Directory Structure Map

**Project Root**: `/home/k1-admin/Kai`  
**Date**: April 11, 2026  
**Purpose**: Evidence & PoC Module Storage Configuration

---

## Executive Summary

K1 uses a **multi-tier data storage strategy**:

1. **`artifacts/`** — Primary storage for tool outputs, findings, and run data (env: `K1_ARTIFACTS_ROOT`)
2. **`output/`** — Workflow execution logs, reports, and normalized scan data (env: `K1_WORKFLOW_OUTPUT_ROOT`)
3. **`vault/`** — Encrypted secrets and governance configurations (GitHub Vault pattern)
4. **`config/`** — YAML-based configuration for tools, APIs, scope policies
5. **`apps/backend/src/`** — FastAPI application code and database models

---

## Complete Directory Tree

### Root Level Storage

```
/home/k1-admin/Kai/
├── artifacts/                          [PRIMARY FINDING STORAGE - K1_ARTIFACTS_ROOT]
│   ├── evidence/                       [Evidence qualification results]
│   ├── submissions/                    [Platform submissions (H1, BC, INT)]
│   │   └── outbox/                     [Pending submissions]
│   ├── workflows/                      [Workflow execution artifacts]
│   ├── dork_runs/                      [Google Dork run results]
│   ├── programs/                       [Bug bounty program configs]
│   ├── knowledge/                      [Knowledge base extractions]
│   ├── decision/                       [Decision tree outputs]
│   ├── ingest/                         [Data ingestion artifacts]
│   ├── graph/                          [Attack graph data]
│   └── auth/                           [Authentication artifacts]
│
├── output/                             [WORKFLOW OUTPUT - K1_WORKFLOW_OUTPUT_ROOT]
│   ├── logs/                           [Execution logs]
│   │   ├── scope_decisions.jsonl       [Scope validation audit (359KB)]
│   │   ├── workflow_*.jsonl            [Per-workflow logs]
│   │   └── ...
│   ├── raw/                            [Raw unprocessed outputs]
│   │   ├── wf-{uuid}/                  [Workflow artifacts]
│   │   └── ...
│   ├── normalized/                     [Normalized scan output]
│   │   ├── wf-{uuid}/                  [Workflow results]
│   │   └── ...
│   ├── workflows/                      [Workflow metadata]
│   ├── reports/                        [Generated reports]
│   ├── burp_exports/                   [Burp Suite imports]
│   └── slow_mem/                       [Slow memory cache]
│
├── vault/                              [ENCRYPTED SECRETS & GOVERNANCE]
│   └── permission_slips/               [PGP signatures, approvals]
│
├── config/                             [YAML CONFIGURATION]
│   ├── scope_guardrails.yaml           [Scope policy definition]
│   ├── policies.yaml                   [Governance policies]
│   ├── provider_registry.yaml          [LLM providers]
│   ├── apis.yaml                       [API credentials layout]
│   ├── toolpacks.yaml                  [Tool pack definitions]
│   ├── branding.yaml                   [Company branding]
│   ├── knowledge.yaml                  [Knowledge base config]
│   ├── registry/                       [Tool/skill registries]
│   │   ├── tool_registry.yaml
│   │   ├── skill_registry.yaml
│   │   ├── routing_matrix.yaml
│   │   └── model_capabilities.yaml
│   ├── providers/                      [LLM provider configs]
│   │   ├── anthropic.yaml
│   │   ├── openai.yaml
│   │   ├── gemini.yaml
│   │   ├── ollama.yaml
│   │   ├── openrouter.yaml
│   │   ├── gemma.yaml
│   │   └── qwen.yaml
│   ├── tools/                          [Tool-specific configs]
│   ├── security/                       [Security policies]
│   ├── environments/                   [Environment configs]
│   │   ├── local.yaml
│   │   ├── cloud.yaml
│   │   └── hybrid.yaml
│   ├── report_formats/                 [Report templates]
│   ├── email_formats/                  [Email templates]
│   └── authorized_scope.json           [Authorized targets list]
│
├── apps/backend/src/                   [FASTAPI APPLICATION]
│   ├── core/                           [Core business logic]
│   │   ├── governance_hil_approval.py  [HiL approval gates]
│   │   ├── kai_orchestrator.py         [Mission orchestrator]
│   │   ├── evidence_recording_engine.py [← Video recording]
│   │   ├── recording_client.py         [← Playwright headless]
│   │   ├── repro_script_generator.py   [← Script generation]
│   │   ├── generate_hil_bundle.py      [← Bundle packaging]
│   │   ├── novelty_dedupe_engine.py    [Novelty deduplication]
│   │   ├── workflow_executor.py        [Workflow DAG execution]
│   │   ├── scope_guardrails.py         [Scope validation]
│   │   ├── tool_registry_catalog.py    [Tool registry]
│   │   └── ... (50+ more core modules)
│   ├── models/                         [SQLAlchemy ORM models]
│   │   ├── bug_bounty.py               [Finding models]
│   │   ├── campaign.py                 [Campaign models]
│   │   ├── workflow.py                 [Workflow models]
│   │   ├── hil.py                      [HiL approval models]
│   │   └── ...
│   ├── routers/                        [FastAPI route handlers]
│   ├── config/                         [Application config]
│   └── main.py                         [FastAPI entry point]
│
├── apps/frontend/src/                  [REACT APPLICATION]
│   ├── App.tsx
│   ├── pages/
│   ├── components/
│   └── stores/
│
├── runtime/                            [RUNTIME STATE]
│   ├── logs/                           [Runtime logs]
│   ├── memory/                         [Runtime memory]
│   │   └── artifacts/                  [Agent memory artifacts]
│   └── ...
│
├── logs/                               [GENERAL LOGS]
│   └── telemetry.jsonl                 [Telemetry data]
│
├── .env                                [ENVIRONMENT VARIABLES]
│   └── K1_ARTIFACTS_ROOT=artifacts     [Default artifact root]
│   └── K1_WORKFLOW_OUTPUT_ROOT=output  [Default workflow output]
│   └── K1_VAULT_HOST_PORT=18201        [Vault server port]
│
└── ... (other directories: tests, tools, docs, crews, etc.)
```

---

## Environment Variables (Storage Configuration)

**File**: `.env` (at root level)

```bash
# === ARTIFACTS & DATA STORAGE ===
K1_ARTIFACTS_ROOT=artifacts                    # Tool outputs, findings, submissions
K1_WORKFLOW_OUTPUT_ROOT=output                 # Workflow logs, reports, normalized data

# === VAULT & SECRETS ===
VAULT_ADDR=http://localhost:18201              # Vault server address
VAULT_TOKEN=kai-dev-1774590091-20534           # Vault authentication token
VAULT_SECRET_PREFIX=kai                        # Vault secret namespace
K1_VAULT_HOST_PORT=18201                       # Vault port binding

# === DATABASE ===
DATABASE_URL=postgresql://k1:k1password@localhost:5432/k1
DATABASE_POOL_SIZE=20

# === LLM PROVIDERS ===
K1_PRIMARY_LLM_PROVIDER=ollama
K1_GEMINI_MODEL=gemini-2.5-flash
K1_OLLAMA_MODEL=qwen2.5-coder:7b
```

---

## Artifact Root: `/home/k1-admin/Kai/artifacts/`

**Purpose**: Primary storage for all finding data, tool outputs, and evidence.

**Size**: ~200 KB (mostly empty directories for PoC)

**Current Structure**:

```
artifacts/
├── evidence/                  [← Existing evidence storage]
│                              └─ (empty, reserved for future use)
│
├── submissions/               [Bug bounty platform submissions]
│   └── outbox/                └─ Pending submissions to H1/BC/INT
│
├── dork_runs/                 [Google Dork attack results]
│   └── {run_id}/
│       └── run.json           └─ Dork run metadata
│
├── workflows/                 [Workflow execution state]
│   └── {workflow_id}/
│
├── programs/                  [Bug bounty program configs]
│
├── knowledge/                 [Knowledge base data]
│
├── decision/                  [Decision tree outputs]
│
├── ingest/                    [Data ingestion artifacts]
│
├── graph/                     [Attack graph data]
│
└── auth/                      [Authentication artifacts]
```

---

## Output Root: `/home/k1-admin/Kai/output/`

**Purpose**: Workflow execution logs, normalized scan output, and reports.

**Size**: ~2.5 MB

**Current Structure**:

```
output/
├── logs/                      [AUDIT & EXECUTION LOGS]
│   ├── scope_decisions.jsonl  [Scope validation decisions - 359 KB]
│   │   └─ Format: {timestamp, target, scope_status, reason, auditor_id}
│   ├── workflow_*.jsonl       [Per-workflow execution logs]
│   └── ...
│
├── raw/                       [RAW UNPROCESSED TOOL OUTPUT]
│   ├── wf-{uuid}/             [Workflow artifact directory]
│   │   ├── plan.json          [Workflow plan/DAG]
│   │   ├── phases.json        [Phase execution results]
│   │   └── ...
│   └── ...
│
├── normalized/                [NORMALIZED SCAN OUTPUT]
│   ├── wf-{uuid}/             [Normalized results per workflow]
│   │   └── *.json             [Vulnerability findings]
│   └── ...
│
├── workflows/                 [WORKFLOW EXECUTION METADATA]
│   ├── wf-{uuid}/             [Workflow state & progress]
│   └── ...
│
├── reports/                   [GENERATED REPORTS]
│   ├── wf-{uuid}/
│   │   ├── vulnerability_report.md
│   │   ├── summary.json
│   │   └── ...
│   └── ...
│
├── burp_exports/              [Burp Suite import/export data]
│
└── slow_mem/                  [Slow memory cache for ML]
```

**Key Log File - `scope_decisions.jsonl`**:
- Location: `/home/k1-admin/Kai/output/logs/scope_decisions.jsonl`
- Size: 359 KB
- Format: JSONL (newline-delimited JSON)
- Content: Every scope validation decision (in/out of scope, reason)
- Updated: Real-time as findings are validated

```jsonl
{"timestamp":"2026-04-10T23:21:00Z","target":"example.com","scope_status":"IN_SCOPE","reason":"Domain in allowlist","auditor_id":"kai_orchestrator"}
{"timestamp":"2026-04-10T23:21:15Z","target":"evil.com","scope_status":"OUT_OF_SCOPE","reason":"Not in authorized scope","auditor_id":"kai_orchestrator"}
...
```

---

## Vault Root: `/home/k1-admin/Kai/vault/`

**Purpose**: Encrypted secrets and governance configurations (follows GitHub Vault pattern).

**Current Structure**:

```
vault/
└── permission_slips/          [PGP signatures & approval records]
    └─ (reserved for HiL approval workflow)
```

**Planned for Evidence Pack**:
```
vault/
├── permission_slips/          [PGP-signed approvals]
│   └── {task_id}_approval.pgp [← PGP signature from HiL reviewer]
│
├── evidence/                  [← PROPOSED for Evidence Pack]
│   ├── recordings/            [← WebM video recordings]
│   │   └── {task_id}_recording.webm
│   │
│   ├── scripts/               [← Reproducible scripts]
│   │   ├── {task_id}_repro.sh
│   │   ├── {task_id}_repro.py
│   │   └── {task_id}_exploit.py
│   │
│   ├── hil_bundles/           [← Evidence bundles for HiL review]
│   │   └── {task_id}_{bundle_id}_evidence.zip
│   │
│   └── http_logs/             [← Raw HTTP traffic]
│       └── {task_id}_traffic.jsonl
│
└── governance/                [← Governance configs]
    ├── hil_policy.yaml        [← HiL approval policy]
    ├── pgp_keys/              [← Approver PGP public keys]
    └── approval_audit.jsonl   [← Immutable approval log]
```

---

## Backend Application: `/home/k1-admin/Kai/apps/backend/src/`

**Purpose**: FastAPI application handling all orchestration and APIs.

**Key Files for Evidence Pack**:

```
apps/backend/src/
├── core/                      [CORE BUSINESS LOGIC]
│   │
│   ├── recording_client.py              [NEW - Playwright headless browser]
│   │   ├─ RecordingClient class        (browser automation, recording)
│   │   ├─ RecordingSession class       (session lifecycle)
│   │   └─ PlaywrightConfig dataclass   (browser config)
│   │
│   ├── evidence_recording_engine.py    [NEW - Recording orchestration]
│   │   ├─ RecordingEngine class        (session management)
│   │   ├─ RecordingConfig dataclass    (storage paths)
│   │   └─ Global singleton             (get_recording_engine())
│   │
│   ├── repro_script_generator.py       [NEW - Script generation]
│   │   ├─ ReproScriptGenerator class   (curl, Python, exploit)
│   │   ├─ ReproductionScript dataclass (script metadata)
│   │   └─ Global singleton             (get_repro_generator())
│   │
│   ├── generate_hil_bundle.py          [NEW - Bundle packaging]
│   │   ├─ HILBundleGenerator class     (ZIP creation, approval)
│   │   ├─ HILBundle dataclass          (bundle metadata)
│   │   ├─ PGPSignature dataclass       (signature validation)
│   │   └─ Global singleton             (get_hil_bundle_generator())
│   │
│   ├── governance_hil_approval.py      [EXISTING - HiL gates]
│   │   ├─ HiLApprovalGateway class     (approval orchestration)
│   │   ├─ ActionRequest dataclass
│   │   └─ ApprovalDecision dataclass
│   │
│   ├── kai_orchestrator.py             [EXISTING - Mission execution]
│   ├── scope_guardrails.py             [EXISTING - Scope validation]
│   ├── workflow_executor.py            [EXISTING - DAG execution]
│   └── ... (50+ more modules)
│
├── models/                    [DATABASE MODELS]
│   ├── bug_bounty.py                   [Finding/Vulnerability models]
│   ├── campaign.py                     [Campaign models]
│   ├── workflow.py                     [Workflow models]
│   ├── hil.py                          [HiL approval models]
│   └── ...
│
├── routers/                   [API ENDPOINTS]
│   ├── findings.py                     [Finding submission APIs]
│   ├── approvals.py                    [← Approval endpoint]
│   ├── evidence.py                     [← Evidence retrieval]
│   └── ...
│
└── main.py                    [FastAPI entry point]
```

---

## Configuration Storage: `/home/k1-admin/Kai/config/`

**Purpose**: YAML-based policies and tool registries.

**Relevant Configs for Evidence Pack**:

```
config/
├── scope_guardrails.yaml               [Scope policy & denylist]
├── policies.yaml                       [Governance policies]
├── security/                           [Security configs]
│   └── pgp_keys.yaml                   [← Approver PGP keys]
│
├── tools/                              [Tool-specific configs]
│   └── ... (browser config, recording defaults, etc.)
│
└── [PROPOSED - governance.yaml]        [← HiL & approval policy]
    ├─ approval_timeout: 300 (seconds)
    ├─ signature_validity: 86400 (seconds)
    ├─ required_approvers: list
    └─ pgp_key_directory: vault/governance/pgp_keys/
```

---

## Recommended Directory Structure for Evidence Pack

### 1. **Recording Storage**

**Location**: `vault/evidence/recordings/` (relative to K1 root)

**Absolute Path**: `/home/k1-admin/Kai/vault/evidence/recordings/`

```
vault/evidence/recordings/
├── {task_id}_recording.webm            [WebM video file, 20-50 MB each]
├── {task_id}_recording.json            [Metadata: duration, FPS, resolution]
└── {task_id}_interactions.json         [Browser interaction log]
```

**Why this location**:
- Falls under `vault/` (sensitive content)
- Organized under `evidence/` subdirectory (clarity)
- Separate from tool outputs (organized structure)
- Easy to encrypt/backup as a unit

### 2. **Script Storage**

**Location**: `vault/evidence/scripts/` (relative to K1 root)

**Absolute Path**: `/home/k1-admin/Kai/vault/evidence/scripts/`

```
vault/evidence/scripts/
├── {task_id}_repro.sh                  [Curl command script]
├── {task_id}_repro.py                  [Python requests script]
└── {task_id}_exploit.py                [Standalone exploit class]
```

### 3. **HiL Bundles**

**Location**: `vault/evidence/hil_bundles/` (relative to K1 root)

**Absolute Path**: `/home/k1-admin/Kai/vault/evidence/hil_bundles/`

```
vault/evidence/hil_bundles/
├── {task_id}_{bundle_id}_evidence.zip  [Evidence ZIP file, 70-100 MB each]
│   ├── report.md                       (3-persona markdown)
│   ├── evidence/                       (video + metadata)
│   ├── scripts/                        (curl, Python, exploit)
│   ├── logs/                           (HTTP traffic)
│   ├── README.md                       (bundle instructions)
│   └── BUNDLE_MANIFEST.json            (metadata & status)
│
└── {task_id}_{bundle_id}_evidence.json [Bundle metadata (for indexing)]
```

### 4. **HTTP Traffic Logs**

**Location**: `vault/evidence/http_logs/` (relative to K1 root)

**Absolute Path**: `/home/k1-admin/Kai/vault/evidence/http_logs/`

```
vault/evidence/http_logs/
├── {task_id}_traffic.jsonl             [Raw HTTP request/response pairs]
└── {task_id}_metadata.json             [Log metadata: count, endpoints, etc.]
```

### 5. **PGP Approvals & Governance**

**Location**: `vault/governance/` (relative to K1 root)

**Absolute Path**: `/home/k1-admin/Kai/vault/governance/`

```
vault/governance/
├── pgp_keys/                           [Approver PGP public keys]
│   ├── {approver_id}.pub               [Public key for signature verification]
│   └── ...
│
├── hil_policy.yaml                     [HiL approval policy config]
├── approval_audit.jsonl                [Immutable approval log]
└── rejected_findings.jsonl             [Rejected findings log]
```

---

## Finding Logs: `/home/k1-admin/Kai/output/logs/`

**Primary Finding Log**: `scope_decisions.jsonl`

**Absolute Path**: `/home/k1-admin/Kai/output/logs/scope_decisions.jsonl`

**Format**: JSONL (one JSON object per line)

**Fields**:
```json
{
  "timestamp": "2026-04-11T14:32:00Z",
  "target": "example.com",
  "scope_status": "IN_SCOPE|OUT_OF_SCOPE|REQUIRES_APPROVAL|RESTRICTED",
  "reason": "Domain in allowlist|Not authorized|...",
  "auditor_id": "kai_orchestrator|{user_id}",
  "finding_id": "{task_id}",
  "severity": "CRITICAL|HIGH|MEDIUM|LOW|INFO"
}
```

**Proposed Addition - Finding Status Log**:

**New File**: `finding_status.jsonl`

**Location**: `/home/k1-admin/Kai/output/logs/finding_status.jsonl`

```json
{
  "timestamp": "2026-04-11T14:32:15Z",
  "task_id": "task_xyz789",
  "status": "DISCOVERED|RECORDED|SCRIPTED|BUNDLED|PENDING_APPROVAL|APPROVED|REJECTED|SUBMITTED",
  "bundle_id": "8f9d2e1b",
  "approver_id": "{user_id}",
  "pgp_signature_status": "valid|expired|invalid",
  "platform_submission_status": "pending|submitted|accepted|rejected"
}
```

---

## Complete Recommended Structure for Evidence Pack

### Create These Directories

```bash
mkdir -p /home/k1-admin/Kai/vault/evidence/recordings
mkdir -p /home/k1-admin/Kai/vault/evidence/scripts
mkdir -p /home/k1-admin/Kai/vault/evidence/hil_bundles
mkdir -p /home/k1-admin/Kai/vault/evidence/http_logs
mkdir -p /home/k1-admin/Kai/vault/governance/pgp_keys
```

### Update Environment Configuration

**File**: `/home/k1-admin/Kai/.env`

```bash
# === EVIDENCE PACK STORAGE ===
K1_EVIDENCE_RECORDINGS_DIR=vault/evidence/recordings
K1_EVIDENCE_SCRIPTS_DIR=vault/evidence/scripts
K1_EVIDENCE_BUNDLES_DIR=vault/evidence/hil_bundles
K1_EVIDENCE_HTTP_LOGS_DIR=vault/evidence/http_logs
K1_GOVERNANCE_PGP_KEYS_DIR=vault/governance/pgp_keys
K1_GOVERNANCE_AUDIT_LOG=vault/governance/approval_audit.jsonl
K1_FINDINGS_STATUS_LOG=output/logs/finding_status.jsonl
```

### Update Config File

**File**: `/home/k1-admin/Kai/config/governance.yaml` (create if missing)

```yaml
evidence_pack:
  enabled: true
  
  recording:
    format: webm
    resolution: 1920x1080
    fps: 30
    max_duration_seconds: 300
    storage_dir: vault/evidence/recordings
    
  scripts:
    types:
      - curl
      - python_requests
      - python_exploit
      - bash
    storage_dir: vault/evidence/scripts
    
  bundles:
    storage_dir: vault/evidence/hil_bundles
    compression: deflate
    include_metadata: true
    
  http_logs:
    storage_dir: vault/evidence/http_logs
    format: jsonl
    
hil_approval:
  enabled: true
  approval_timeout_seconds: 300
  pgp_signature_validity_hours: 24
  required_signature_for_submission: true
  pgp_keys_directory: vault/governance/pgp_keys
  approval_audit_log: vault/governance/approval_audit.jsonl
```

---

## Summary Table

| Component | Absolute Path | Purpose | Size | Format |
|-----------|---------------|---------|------|--------|
| **Recordings** | `/home/k1-admin/Kai/vault/evidence/recordings/` | WebM video recordings | 20-50 MB each | WebM + JSON metadata |
| **Scripts** | `/home/k1-admin/Kai/vault/evidence/scripts/` | Curl, Python, exploit scripts | 1-10 KB each | Bash, Python |
| **Bundles** | `/home/k1-admin/Kai/vault/evidence/hil_bundles/` | Evidence ZIP packages | 70-100 MB each | ZIP (deflate) |
| **HTTP Logs** | `/home/k1-admin/Kai/vault/evidence/http_logs/` | Raw request/response pairs | 10-50 KB each | JSONL |
| **PGP Keys** | `/home/k1-admin/Kai/vault/governance/pgp_keys/` | Approver public keys | < 1 KB each | PGP |
| **Approval Audit** | `/home/k1-admin/Kai/vault/governance/approval_audit.jsonl` | Immutable approval log | Grows over time | JSONL |
| **Scope Decisions** | `/home/k1-admin/Kai/output/logs/scope_decisions.jsonl` | Scope validation log | 359 KB (current) | JSONL |
| **Finding Status** | `/home/k1-admin/Kai/output/logs/finding_status.jsonl` | Finding lifecycle log | Grows over time | JSONL |

---

## Integration Checklist

- [ ] Create `vault/evidence/` subdirectories
- [ ] Create `vault/governance/` subdirectories
- [ ] Update `.env` with new environment variables
- [ ] Create `config/governance.yaml` with Evidence Pack config
- [ ] Update `apps/backend/src/main.py` to load governance singleton
- [ ] Wire `RecordingClient` into `GeminiOrchestrator`
- [ ] Wire `ReproScriptGenerator` into finding export pipeline
- [ ] Wire `HILBundleGenerator` into approval workflow
- [ ] Add PGP key management to `vault/governance/pgp_keys/`
- [ ] Test end-to-end: record → script → bundle → approval

---

**Generated**: April 11, 2026  
**Ready for**: Evidence Pack Module Integration
