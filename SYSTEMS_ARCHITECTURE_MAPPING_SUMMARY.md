# Systems Architecture Mapping Summary

**K1 Evidence Pack Module Configuration**  
**Date**: April 11, 2026  
**Status**: ● COMPLETE ✓

---

## Overview

K1's data storage architecture uses a **multi-tier hierarchical structure** with three primary storage roots:

1. **`artifacts/`** (K1_ARTIFACTS_ROOT) — Tool outputs, findings, submissions
2. **`output/`** (K1_WORKFLOW_OUTPUT_ROOT) — Workflow logs, reports, normalized data
3. **`vault/`** — Encrypted secrets, governance configs, evidence

---

## TASK 1: Root Directory & Vault Location

### Backend Root
```
/home/k1-admin/Kai/apps/backend/src/
```
FastAPI application, core business logic, database models.

### Current Vault Location
```
/home/k1-admin/Kai/vault/
├── permission_slips/          [Existing - approval records]
└── [TO BE EXPANDED for Evidence Pack]
```

**Size**: Currently 4.0 KB (minimal) → Will grow with evidence pack

---

## TASK 2: Tool Outputs & Logs

### Primary Finding Log
**Location**: `/home/k1-admin/Kai/output/logs/scope_decisions.jsonl`

- **Format**: JSONL (newline-delimited JSON)
- **Size**: 359 KB (current)
- **Fields**: `timestamp`, `target`, `scope_status`, `reason`, `auditor_id`
- **Purpose**: Tracks every scope validation decision (in-scope/out-of-scope)
- **Updated**: Real-time as findings are validated

### Tool Output Directories

**By Type**:
- Recon tools: `/home/k1-admin/Kai/output/raw/wf-{uuid}/recon_*.json`
- Vulnerability scanners: `/home/k1-admin/Kai/output/raw/wf-{uuid}/nmap_*.json`
- Web crawlers: `/home/k1-admin/Kai/output/raw/wf-{uuid}/crawl_*.json`

**By Phase**:
- Phase 0 (Reconnaissance): `/home/k1-admin/Kai/output/raw/wf-{uuid}/phase_0_*.json`
- Phase 5 (Vulnerability Scanning): `/home/k1-admin/Kai/output/raw/wf-{uuid}/phase_5_*.json`
- Phase 9 (Alert Generation): `/home/k1-admin/Kai/output/raw/wf-{uuid}/phase_9_*.json`

**Normalized Results**:
- Location: `/home/k1-admin/Kai/output/normalized/wf-{uuid}/findings.json`
- Contains: Processed, unified format vulnerabilities

---

## TASK 3: Absolute Paths for Evidence Pack

### 1. Active Finding Logs

**Existing**:
```
/home/k1-admin/Kai/output/logs/scope_decisions.jsonl
```

**NEW**:
```
/home/k1-admin/Kai/output/logs/finding_status.jsonl
```
- Tracks finding lifecycle: DISCOVERED → RECORDED → SCRIPTED → BUNDLED → APPROVED → SUBMITTED

### 2. Tool-Specific Output Directories

**Raw Tool Output**:
```
/home/k1-admin/Kai/output/raw/wf-{workflow_id}/
├── {tool_name}_*.json
├── phase_{n}_*.json
└── ...
```

**Normalized Output**:
```
/home/k1-admin/Kai/output/normalized/wf-{workflow_id}/
└── findings.json
```

### 3. PGP Keys & Governance Configs

**PGP Keys** (for signature verification):
```
/home/k1-admin/Kai/vault/governance/pgp_keys/
├── {approver_id}.pub                    [Public key per approver]
├── admin.pub
├── security_team_lead.pub
└── compliance_officer.pub
```

**Governance Policies**:
```
/home/k1-admin/Kai/config/governance.yaml              [NEW - to create]
/home/k1-admin/Kai/config/scope_guardrails.yaml        [EXISTING]
/home/k1-admin/Kai/config/policies.yaml                [EXISTING]
```

**Approval Audit Log** (immutable):
```
/home/k1-admin/Kai/vault/governance/approval_audit.jsonl
```
- Records: `task_id`, `approver_id`, `pgp_signature_status`, `timestamp`

---

## Complete Directory Structure

### Environment Variables (`.env`)

```bash
# PRIMARY STORAGE ROOTS
K1_ARTIFACTS_ROOT=artifacts              # Finding artifacts (default)
K1_WORKFLOW_OUTPUT_ROOT=output            # Workflow logs (default)

# EVIDENCE PACK STORAGE (NEW)
K1_EVIDENCE_RECORDINGS_DIR=vault/evidence/recordings
K1_EVIDENCE_SCRIPTS_DIR=vault/evidence/scripts
K1_EVIDENCE_BUNDLES_DIR=vault/evidence/hil_bundles
K1_EVIDENCE_HTTP_LOGS_DIR=vault/evidence/http_logs
K1_GOVERNANCE_PGP_KEYS_DIR=vault/governance/pgp_keys
K1_GOVERNANCE_AUDIT_LOG=vault/governance/approval_audit.jsonl
K1_FINDINGS_STATUS_LOG=output/logs/finding_status.jsonl
```

### Directory Tree

```
/home/k1-admin/Kai/
├── artifacts/                          [K1_ARTIFACTS_ROOT]
│   ├── evidence/
│   ├── submissions/
│   ├── workflows/
│   ├── dork_runs/
│   ├── programs/
│   ├── knowledge/
│   ├── decision/
│   ├── ingest/
│   ├── graph/
│   └── auth/
│
├── output/                             [K1_WORKFLOW_OUTPUT_ROOT]
│   ├── logs/
│   │   ├── scope_decisions.jsonl       ← PRIMARY FINDING LOG
│   │   └── finding_status.jsonl        ← NEW STATUS LOG
│   ├── raw/
│   ├── normalized/
│   ├── workflows/
│   ├── reports/
│   └── ...
│
├── vault/
│   ├── permission_slips/               [EXISTING]
│   ├── evidence/                       [NEW - Evidence Pack]
│   │   ├── recordings/                 ← WebM videos
│   │   ├── scripts/                    ← curl, Python, exploit
│   │   ├── hil_bundles/                ← Evidence packages (ZIP)
│   │   └── http_logs/                  ← Raw HTTP traffic
│   └── governance/                     [NEW - Governance]
│       ├── pgp_keys/                   ← Approver keys
│       ├── approval_audit.jsonl        ← Approval log
│       ├── hil_policy.yaml
│       └── rejected_findings.jsonl
│
├── config/
│   ├── governance.yaml                 [NEW - Evidence Pack config]
│   ├── scope_guardrails.yaml
│   ├── policies.yaml
│   ├── providers/
│   ├── tools/
│   ├── registry/
│   ├── security/
│   └── ...
│
├── apps/backend/src/
│   ├── core/
│   │   ├── recording_client.py         [NEW]
│   │   ├── evidence_recording_engine.py [NEW]
│   │   ├── repro_script_generator.py   [NEW]
│   │   ├── generate_hil_bundle.py      [NEW]
│   │   ├── governance_hil_approval.py
│   │   ├── kai_orchestrator.py
│   │   ├── scope_guardrails.py
│   │   └── ... (50+ more modules)
│   ├── models/
│   ├── routers/
│   └── main.py
│
└── .env
    └─ K1_ARTIFACTS_ROOT, K1_WORKFLOW_OUTPUT_ROOT, K1_EVIDENCE_*, K1_GOVERNANCE_*
```

---

## Storage Breakdown

| Component | Path | Size | Purpose |
|-----------|------|------|---------|
| **Artifacts Root** | `/home/k1-admin/Kai/artifacts/` | 200 KB | Tool outputs, findings, submissions |
| **Workflow Output** | `/home/k1-admin/Kai/output/` | 2.5 MB | Logs, reports, normalized data |
| **Vault** | `/home/k1-admin/Kai/vault/` | 4.0 KB → ∞ | Secrets, governance, evidence |
| **Scope Log** | `output/logs/scope_decisions.jsonl` | 359 KB | Scope validation audit |
| **Recordings** | `vault/evidence/recordings/` | 20-50 MB/ea | WebM video evidence |
| **Scripts** | `vault/evidence/scripts/` | 1-10 KB/ea | Reproducible scripts |
| **Bundles** | `vault/evidence/hil_bundles/` | 70-100 MB/ea | Evidence packages (ZIP) |
| **HTTP Logs** | `vault/evidence/http_logs/` | 10-50 KB/ea | Raw traffic |
| **PGP Keys** | `vault/governance/pgp_keys/` | 1-4 KB/ea | Approver public keys |
| **Approval Log** | `vault/governance/approval_audit.jsonl` | Grows | Approval history |

---

## Finding Lifecycle Data Flow

```
1. DISCOVERY
   ├─ Tool executes: output/raw/wf-{uuid}/{tool}_*.json
   └─ Status: DISCOVERED

2. VALIDATION (Scope Check)
   ├─ Decision logged: output/logs/scope_decisions.jsonl
   └─ Status: IN_SCOPE | OUT_OF_SCOPE | REQUIRES_APPROVAL

3. RECORDING (Playwright)
   ├─ Video saved: vault/evidence/recordings/{task_id}_recording.webm
   ├─ Metadata: vault/evidence/recordings/{task_id}_recording.json
   └─ Status: RECORDED

4. SCRIPT GENERATION
   ├─ Curl: vault/evidence/scripts/{task_id}_repro.sh
   ├─ Python: vault/evidence/scripts/{task_id}_repro.py
   ├─ Exploit: vault/evidence/scripts/{task_id}_exploit.py
   └─ Status: SCRIPTED

5. BUNDLING (ZIP Package)
   ├─ Bundle: vault/evidence/hil_bundles/{task_id}_{bundle_id}_evidence.zip
   ├─ Metadata: vault/evidence/hil_bundles/{task_id}_{bundle_id}_evidence.json
   └─ Status: BUNDLED

6. MANUAL APPROVAL (HiL Review)
   ├─ Expert reviews video + report + scripts
   ├─ Expert signs: k1 approve {task_id} --pgp-sign <signature>
   ├─ Logged: vault/governance/approval_audit.jsonl
   └─ Status: APPROVED | REJECTED

7. PLATFORM SUBMISSION
   ├─ Check approval: can_submit_to_platform({task_id})
   ├─ BLOCKS if: no valid PGP signature or status != APPROVED
   ├─ Queued: artifacts/submissions/outbox/
   └─ Status: SUBMITTED
```

---

## Configuration Files to Create/Update

### 1. New: `/home/k1-admin/Kai/config/governance.yaml`

```yaml
evidence_pack:
  enabled: true
  recording:
    format: webm
    resolution: 1920x1080
    fps: 30
    max_duration_seconds: 300
  scripts:
    types:
      - curl
      - python_requests
      - python_exploit
      - bash
  bundles:
    storage_dir: vault/evidence/hil_bundles
    compression: deflate

hil_approval:
  enabled: true
  approval_timeout_seconds: 300
  pgp_signature_validity_hours: 24
  required_signature_for_submission: true
```

### 2. Update: `/home/k1-admin/Kai/.env`

Add evidence pack environment variables (see above).

### 3. Existing: `/home/k1-admin/Kai/config/scope_guardrails.yaml`

Already defines scope policy. No changes needed for evidence pack.

---

## Setup Commands

```bash
# Create directories
mkdir -p /home/k1-admin/Kai/vault/evidence/{recordings,scripts,hil_bundles,http_logs}
mkdir -p /home/k1-admin/Kai/vault/governance/pgp_keys

# Verify
ls -la /home/k1-admin/Kai/vault/evidence/
ls -la /home/k1-admin/Kai/vault/governance/

# Create governance.yaml
cat > /home/k1-admin/Kai/config/governance.yaml << 'EOF'
evidence_pack:
  enabled: true
  # ... (see template above)
hil_approval:
  enabled: true
  # ... (see template above)
EOF

# Update .env
# (Manually add K1_EVIDENCE_*, K1_GOVERNANCE_* variables)
```

---

## Integration Points

### In `apps/backend/src/main.py`

```python
# Import Evidence Pack modules
from core.recording_client import RecordingClient
from core.evidence_recording_engine import get_recording_engine
from core.repro_script_generator import get_repro_generator
from core.generate_hil_bundle import get_hil_bundle_generator

# Initialize singletons (async)
async def startup():
    await get_recording_engine()
    await get_repro_generator()
    await get_hil_bundle_generator()
```

### In `apps/backend/src/core/kai_orchestrator.py`

```python
# During mission execution:
# 1. Start recording when vulnerability detected
session = await recording_engine.start_recording(task_id, target_url)

# 2. Generate scripts from captured traffic
curl_script = await repro_gen.generate_curl_command(...)
python_script = await repro_gen.generate_python_requests(...)
exploit_script = await repro_gen.generate_exploit_script(...)

# 3. Create bundle for manual review
bundle = await bundle_gen.create_bundle(task_id, report_path, ...)

# 4. Block platform submission until approved
if not await bundle_gen.can_submit_to_platform(task_id):
    # Finding is locked until PGP-signed approval received
    return  # Don't submit yet
```

---

## Files Provided

This architecture mapping includes:

1. **K1_DIRECTORY_STRUCTURE_MAP.md** — Detailed structure with recommendations
2. **EVIDENCE_PACK_PATHS_QUICK_REFERENCE.txt** — Quick lookup table
3. **EVIDENCE_PACK_DIRECTORY_TREE.txt** — Visual tree with data flow
4. **SYSTEMS_ARCHITECTURE_MAPPING_SUMMARY.md** — This document

---

## Status

✓ Root directory identified: `/home/k1-admin/Kai/apps/backend/src`  
✓ Vault location: `/home/k1-admin/Kai/vault/`  
✓ Artifact root identified: `/home/k1-admin/Kai/artifacts/` (K1_ARTIFACTS_ROOT)  
✓ Workflow output root: `/home/k1-admin/Kai/output/` (K1_WORKFLOW_OUTPUT_ROOT)  
✓ Active finding logs located: `output/logs/scope_decisions.jsonl`  
✓ Tool output directories mapped  
✓ PGP keys & governance paths defined  

**Ready for Evidence Pack Module Configuration**

---

**Generated**: April 11, 2026  
**Architecture Status**: ● COMPLETE ✓
