# HiL (Human-in-the-Loop) Gate — Enforcement Spec

Objective: Prevent any stakeholder submission unless an authorized human approves the finding with complete evidence.

Required to submit:
- hil_approvals.status == APPROVED
- Checklist present and passing: repro_steps, http_traces_or_logs, poc_or_screencap, scope_confirmation, impact_rationale
- Immutable evidence bundle stored; report content hashed; manifest hashed and logged in audit_merkle_roots
- RBAC: submitter must have Permission.SUBMIT_FINDINGS; approver captured (approved_by, approved_at)

API contract (FastAPI):
- POST /findings/{id}/hil/request → create/update hil_approvals (PENDING)
- POST /findings/{id}/hil/approve → requires admin role; validates checklist + evidence; sets APPROVED
- POST /findings/{id}/submit → checks hil_approvals == APPROVED; verifies evidence + hashes; creates TheHive case (or links), then BBP submission
- GET  /findings/{id}/evidence → list evidence

DB touchpoints:
- findings.status transitions: NEW→IN_REVIEW→HIL_APPROVED→SUBMITTED
- hil_approvals unique per finding; evidence hashed (sha256)

Audit & tracing:
- Record decision path (approver, timestamps, hashes) and include Merkle root
- Emit spans for validation → approval → submission

Failure modes (fail-closed):
- Missing checklist item → 422
- No APPROVED record → 403
- Evidence hash mismatch → 409

Pseudocode (submission):
```
if not hil_approved(finding_id): raise HTTPException(403)
assert checklist_passed(finding_id)
manifest = build_artifact_manifest(finding_id)
root = merkle_root(manifest)
store_root(run_id, root)
case_id = thehive.ensure_case(finding)
bbp.submit(finding, case_id)
update finding.status = 'SUBMITTED'
```
