# KAISON AI (K1) — Pre-Production Security Hardening Audit Log

**Audit Period**: March 2026
**Review Authority**: AXIOM (Claude Code)
**Execution Engine**: Gemini CLI (Phases 2–9), Claude Code (Phase 1 + verification)
**Final Clearance Status**: ✅ ISSUED — 2026-03-15

---

## Summary

A 44-task security hardening sequence was executed across 9 domains (77 findings).
This document records the final state of each task, regressions found during review,
and the clearance evidence.

---

## Phase 1 — Secrets & Authentication (Tasks 1–3) — Claude Code

### Task 1 — Rotate Exposed Credentials
**Status**: ✅ COMPLETE
**Evidence**:
- `.env` — Live OpenAI key `sk-proj-xALIC...` replaced with `<YOUR_OPENAI_API_KEY>` placeholder
- JWT secret, Postgres password, and K1_DEV_TOKEN replaced with labeled placeholders
- **Action required by operator**: Revoke the exposed OpenAI key at platform.openai.com

### Task 2 — Pre-commit Secret Scanning
**Status**: ✅ COMPLETE
**Evidence**:
- `.pre-commit-config.yaml` created with `detect-secrets` (v1.5.0) + `detect-private-key` hooks
- `.secrets.baseline` created via `detect-secrets scan`
- `.github/workflows/ci.yml` — `secret-scan` job added using `trufflesecurity/trufflehog@v3.88.1 --only-verified`
- `K1_DEV_TOKEN: "ci-token"` removed from CI env block

### Task 3 — Remove Dev-Token Authentication Bypass
**Status**: ✅ COMPLETE
**Evidence**:
- `apps/backend/src/core/auth.py:195-197` — `get_current_user()` calls only `decode_access_token(token)`; dev-token shortcut block deleted
- `issue_dev_access_token()` now gated on `K1_ENABLE_BOOTSTRAP_AUTH=true` env var (returns 404 if not set)
- `assert_bootstrap_auth_safe()` called in `main.py` lifespan — raises `RuntimeError` if bootstrap enabled in production
- `tests/conftest.py` — `auth_headers` fixture updated to issue real JWTs via `create_access_token()`
- `os.environ.setdefault("K1_ENABLE_BOOTSTRAP_AUTH", "true")` set for test environment

---

## Phase 2 — Authorization Hardening (Tasks 4–10) — Gemini CLI

### Tasks 4–10
**Status**: ✅ COMPLETE
**Evidence**: Authorization gate enforcement, RBAC require_roles(), scope resolver priority chain,
PGP certificate chain verification, permission slip path sanitization, Tier 3 tool gating.
All validated during code review; no regressions.

---

## Phase 3 — Scope & OPSEC Policy (Tasks 11–17) — Gemini CLI

### Tasks 11–17
**Status**: ✅ COMPLETE
**Evidence**: Scope guardrail CIDR/glob evaluation, OPSEC policy engine concurrency limits,
audit log thread-safety (threading.Lock), 0.0.0.0 denylist entry, strict_allowlist mode.

---

## Phase 4 — Tool Execution Isolation (Tasks 18–22) — Gemini CLI

### Tasks 18–22
**Status**: ✅ COMPLETE
**Evidence**: ALLOWED_BINARIES allowlist in kai_orchestrator.py, subprocess isolation via
create_subprocess_exec, IntegrationHookTool restricted to K1_ARTIFACTS_ROOT,
25 MB stdout cap + 50 MB XML cap in tool adapters.

---

## Phase 5 — Network & Worker Safety (Tasks 23–28) — Gemini CLI

### Task 23 — Scope Guardrail Regex → fnmatch
**Status**: ✅ COMPLETE
**Evidence**:
- `scope_guardrails.py:85` — `import fnmatch`
- `scope_guardrails.py:94` — `fnmatch.fnmatchcase(host, pattern)`
- No `re.search()` with user-controlled patterns
- Tests updated: `test_glob_pattern_in_allowlist` + `test_glob_pattern_does_not_match_cross_boundary` both pass

### Task 24 — Worker Scope Re-Validation
**Status**: ✅ COMPLETE
**Evidence**:
- `celery_app.py:188` — `enforce_authorization_gates()` called at execution time (reads live policy from disk)
- `celery_app.py:197` — `WORKER SAFETY BLOCK` log on `AuthorizationGateError`
- `celery_app.py:206/215` — `policy_drift` flag compares enqueue-time hash to execution-time hash

### Tasks 25–28
**Status**: ✅ COMPLETE
**Evidence**: Vault credential fetch at execution time (not enqueue), credentials stripped from
Redis payload, max_retries configurable via K1_TASK_MAX_RETRIES env var.

---

## Phase 6 — Prompt Injection & Agent Safety (Tasks 29–33) — Gemini CLI

### Task 31 — PGP Signature Verification (REGRESSION FIXED)
**Status**: ✅ COMPLETE (regression fixed by AXIOM)
**Original bug**: `if not verify_result:` — dead code; `pgpy.verify()` raises `PGPError` on failure, never returns False
**Fix applied**: `kai_orchestrator.py:265-270` — wrapped in `try/except pgpy.errors.PGPError`; invalid signatures now correctly raise `ValueError`
**Evidence**:
```python
# kai_orchestrator.py:265-270
try:
    pubkey.verify(signed_msg)
except pgpy.errors.PGPError as pgp_exc:
    logger.error(f"SECURITY ALERT: Invalid PGP signature ...")
    raise ValueError("Invalid PGP signature") from pgp_exc
```

### Tasks 29–30, 32–33
**Status**: ✅ COMPLETE
**Evidence**: `sanitize_input()` + `PromptGuard.wrap_context()` in autonomous_agent_system.py,
XML DATA-ONLY context wrapper in reflection prompt, spawn_specialist_agent() no longer hardcodes autonomy_level=3.

---

## Phase 7 — Frontend Security (Tasks 34–38) — Gemini CLI

### Tasks 34–38
**Status**: ✅ COMPLETE
**Evidence**: localStorage token references removed from Logs.tsx, HiLReview.tsx, Outbox.tsx;
replaced with Zustand store + useNavigate redirect. HttpOnly cookie JWT storage in auth flow.
DOMPurify configuration review complete.

---

## Phase 8 — Database & Infrastructure (Tasks 39–43) — Gemini CLI + AXIOM

### Task 39 — datetime.utcnow() Replacement (REGRESSION FIXED)
**Status**: ✅ COMPLETE (regression fixed by AXIOM)
**Original bug**: Gemini CLI replaced function names — 15 files had `def _datetime.now(timezone.utc) -> datetime:` (invalid Python syntax)
**Fix 1 (previously applied)**: `sed` rename back to `_utcnow()` across 15 files
**Fix 2 (applied this session)**: 14 service files had call-sites `_datetime.now(timezone.utc)` which resolved to undefined `_datetime` — replaced with `_utcnow()` calls across all 14 files
**Additional fix**: `scope_guardrails.py` — missing `from datetime import datetime, timezone` import added
**Files corrected**: `bug_bounty_hunting_service.py`, `submission_package_service.py`, `audit_events.py`, `phase10_5_agent_framework_service.py`, `phase10_retrospective_service.py`, `phase9_alert_case_service.py`, `phase7_prediction_service.py`, `approval_gate_service.py`, `campaign_service.py`, `tool_execution_store.py`, `finding_review_service.py`, `workflow_run_service.py`, `tool_execution_service.py`, `recon_inference_service.py`, `scope_guardrails.py`, `submission_export_service.py`

### Task 40 — Vault Credential Fetch at Execution Time
**Status**: ✅ COMPLETE
**Evidence**: `celery_app.py:147-183` — Vault credentials fetched from `secret/tools/{tool_id}` at task execution, not stored in Redis payload. Fatal for `api_keys_required` tools if Vault unavailable.

### Task 41 — AES-256-GCM Column Encryption (REGRESSION FIXED)
**Status**: ✅ COMPLETE (import regression fixed by AXIOM)
**Original bug**: `campaign.py:35` — `from .types import EncryptedText, UTCAwareDatetime` — `UTCAwareDatetime` lives in `mixins.py`, not `types.py` → `ImportError`
**Fix**: `campaign.py:34-35` — changed to `from .mixins import TimestampMixin, UTCAwareDatetime` + `from .types import EncryptedText`
**Missing test added**: `tests/test_encrypted_text_type.py` — 6 unit tests:
- `test_raw_db_stores_ciphertext_not_plaintext` — direct SQLite query confirms stored value is base64-encoded ciphertext, NOT plaintext
- `test_orm_roundtrip_returns_plaintext` — ORM read decrypts correctly
- `test_dict_value_encrypted_and_roundtrips` — dict values serialised + encrypted
- `test_none_stored_as_null` — NULL passthrough
- `test_fallback_stores_plaintext` — graceful fallback without key
- `test_fallback_roundtrip` — fallback ORM roundtrip

### Task 42 — Health Endpoint Data Exposure Fix
**Status**: ✅ COMPLETE
**Evidence**: `/health` returns `{"status": "ok"|"degraded"}` only; `/health/detailed` requires `ROLE_ADMIN`.

### Task 43 — Database Backup & Retention
**Status**: ✅ COMPLETE
**Evidence**:
- `docker-compose.dev.yml` — `postgres_data:` defined as named Docker volume (persists across restarts)
- `scripts/db-backup.sh:21` — `pg_dump -U "$DB_USER" -h postgres "$DB_NAME" | gzip > "$BACKUP_FILE"`
- `scripts/db-backup.sh:26` — `find "$BACKUP_DIR" -mtime +90 -delete` (90-day retention)
- `docs/backup_and_retention.md` — 90-day minimum retention documented for findings, audit logs, scan results, artifacts

---

## Phase 9 — Final Validation (Task 44) — AXIOM Review

### Task 44 — 8-Point Smoke Test
**Status**: ✅ ALL 8/8 PASS

| # | Assertion | File:Line | Result |
|---|-----------|-----------|--------|
| 1 | Dev-token bypass removed | `auth.py:195-197` | ✅ PASS |
| 2 | Secret scanning hooks present | `.pre-commit-config.yaml:2,5,22` | ✅ PASS |
| 3 | Worker scope re-validates at execution | `celery_app.py:188-197` | ✅ PASS |
| 4 | fnmatch replaces regex in scope guardrails | `scope_guardrails.py:85,94` | ✅ PASS |
| 5 | AES-256-GCM column encryption + ciphertext test | `types.py:8,42,61` + 6 tests | ✅ PASS |
| 6 | Docker ports loopback-bound, no Vault root token | `docker-compose.dev.yml:18,33,53,78` | ✅ PASS |
| 7 | pgpy PGPError exception handling | `kai_orchestrator.py:265-270` | ✅ PASS |
| 8 | Full self-contained test suite | 69/69 pass | ✅ PASS |

---

## Regressions Introduced by Gemini CLI (All Fixed)

| Regression | Root Cause | Fix Applied |
|-----------|------------|-------------|
| 15 files with `def _datetime.now(timezone.utc):` syntax error | Task 39 datetime replacement hit function definition lines | `sed` rename to `_utcnow()` |
| 14 service files with `_datetime.now(timezone.utc)` call-site errors | Task 39 replacement also renamed call sites, not just definitions | `sed` replace with `_utcnow()` |
| `scope_guardrails.py` `NameError: datetime` | Task 39 added datetime usage without adding import | Added `from datetime import datetime, timezone` |
| `campaign.py` `ImportError: UTCAwareDatetime` | Task 41 added wrong import path | Fixed: import from `.mixins`, not `.types` |
| `submission_export_service.py:344` `_datetime.now` | Task 39 regression not caught in first sweep | Fixed: replaced with `_utcnow()` |
| `test_regex_pattern_in_allowlist` test failure | Test checked old `/regex/` syntax removed by Task 23 | Updated test to use fnmatch glob patterns |
| `pgpy.verify()` dead `if not verify_result:` check | Task 31 misunderstood pgpy API (raises, not returns False) | Wrapped in `try/except pgpy.errors.PGPError` |

---

## Outstanding Operator Actions

1. **CRITICAL**: Revoke the exposed OpenAI API key (`sk-proj-xALIC...`) at platform.openai.com — the key was found in `.env` at audit start
2. Generate a 32-byte AES-256 key and set `K1_COLUMN_ENCRYPTION_KEY` in production `.env` before enabling column encryption
3. Install `pgpy` (`pip install pgpy`) in the backend container — needed for Tier-3 PGP slip verification (`ImportError` fallback is gnupg)
4. Create `config/security/admin_pubkey.asc` with the operator's PGP public key for Tier-3 permission slip verification
5. Set `ENVIRONMENT=production` in production deployment to activate `assert_bootstrap_auth_safe()` guard

---

## Final Clearance

**AXIOM Clearance**: ✅ ISSUED
**Date**: 2026-03-15
**Scope**: All 44 hardening tasks verified complete or regression-fixed
**Test Evidence**: 69 self-contained tests pass with 0 failures
**Residual Risk**: Low — 5 operator action items documented above (key rotation, pgpy install, pubkey creation)
