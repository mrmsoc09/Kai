# Safety & Validation API Reference
## PROMPT 7 & 8 REST Endpoints

---

## PROMPT 7: Safety Systems

### Emergency Abort / Kill Switch

#### Request Scan Abort
```http
POST /api/v1/safety/scans/{scan_id}/abort
Query Parameters:
  - reason: string (required) - Human-readable reason for abort

Response:
{
  "status": "kill_switch_activated",
  "scan_id": "uuid",
  "abort_requested_at": "2026-04-14T12:00:00Z",
  "requested_by": "analyst-001"
}
```

#### Check Abort Status
```http
GET /api/v1/safety/scans/{scan_id}/abort-status

Response (abort requested):
{
  "abort_requested": true,
  "requested_by": "analyst-001",
  "reason": "Scope violation detected",
  "requested_at": "2026-04-14T12:00:00Z"
}

Response (no abort):
{
  "abort_requested": false
}
```

### Scope Violations Audit Trail

#### List All Violations
```http
GET /api/v1/safety/violations
Query Parameters:
  - program_id: string (optional) - Filter by program
  - limit: integer (1-1000, default 100)
  - offset: integer (default 0)

Response:
{
  "violations": [
    {
      "id": "uuid",
      "program_id": "uuid",
      "scan_id": "uuid",
      "violation_type": "endpoint_out_of_scope",
      "reason": "Endpoint /admin not in scope",
      "target": "/admin",
      "detected_at": "2026-04-14T12:00:00Z",
      "created_by": "scope_validator"
    }
  ],
  "total": 42,
  "limit": 100,
  "offset": 0
}
```

#### List Violations for Program
```http
GET /api/v1/safety/violations/{program_id}
Query Parameters:
  - limit: integer (1-1000, default 100)
  - offset: integer (default 0)
  - violation_type: string (optional) - Filter by type

Response:
{
  "program_id": "uuid",
  "violations": [...],
  "total": 42,
  "limit": 100,
  "offset": 0
}
```

#### Violation Types
- `endpoint_out_of_scope` — Endpoint not in scope list
- `domain_out_of_scope` — Domain not in allowed list
- `ip_out_of_scope` — IP not in allowed IPs/CIDRs
- `port_out_of_scope` — Port not in allowed list
- `parameter_out_of_scope` — Parameter in exclusion list
- `sensitive_path` — Absolute block (e.g., /admin, /config)
- `rate_limit_threshold` — Rate limit hit

---

## PROMPT 8: Validation & Analyst Control

### Validation Queue Management

#### Get Pending Findings Queue
```http
GET /api/v1/validation/queue
Query Parameters:
  - analyst_id: string (required)
  - limit: integer (optional, default 50)
  - offset: integer (optional, default 0)

Response:
{
  "analyst_id": "analyst-001",
  "queue_size": 12,
  "findings": [
    {
      "finding_id": "uuid",
      "vulnerability_type": "XSS",
      "severity": "high",
      "cvss_score": 7.5,
      "endpoint": "/api/users",
      "parameter": "name",
      "payload": "<script>alert(1)</script>",
      "description": "Stored XSS in user profile",
      "proof_of_concept": "POST profile → GET profile → XSS triggered",
      "confidence_score": 0.95,
      "estimated_payout": 500.00,
      "false_positive_confidence": 0.15,
      "false_positive_reason": null
    }
  ]
}
```

#### Get Queue Statistics
```http
GET /api/v1/validation/stats

Response:
{
  "pending_review": 12,
  "approved_for_submission": 45,
  "excluded": 3,
  "total_findings": 60
}
```

### Analyst Review Decisions

#### Submit Finding Review
```http
POST /api/v1/validation/findings/{finding_id}/review
Body:
{
  "decision": "approve|exclude|force_include",
  "reason": "Manual override reason (optional)",
  "notes": "Additional analyst notes"
}

Response:
{
  "status": "success",
  "decision": "approved|excluded|force_included",
  "finding_id": "uuid",
  "created_override_record": "uuid"
}
```

#### Quick Exclude Finding
```http
POST /api/v1/validation/findings/{finding_id}/exclude
Body:
{
  "reason": "False positive - expected behavior"
}

Response:
{
  "status": "success",
  "finding_id": "uuid",
  "validation_status": "excluded",
  "finding_state": "false_positive"
}
```

#### Quick Approve Finding
```http
POST /api/v1/validation/findings/{finding_id}/approve
Body:
{
  "notes": "Confirmed vulnerable"
}

Response:
{
  "status": "success",
  "finding_id": "uuid",
  "validation_status": "approved_for_submission"
}
```

### Batch Operations

#### Batch Approve Multiple Findings
```http
POST /api/v1/validation/batch-approve
Body:
{
  "finding_ids": ["uuid1", "uuid2", "uuid3", ...],
  "analyst_id": "analyst-001"
}

Response:
{
  "status": "success",
  "approved": 20,
  "failed": 0,
  "total": 20
}
```

**Note**: Maximum 20 findings per batch (prevents accidental bulk approvals)

### Audit Trail

#### Get Override History
```http
GET /api/v1/validation/findings/{finding_id}/overrides

Response:
{
  "finding_id": "uuid",
  "overrides": [
    {
      "id": "uuid",
      "override_decision": "exclude",
      "reason": "False positive - expected behavior in error page",
      "analyst_notes": "Reviewed logs, confirmed expected behavior",
      "overridden_by": "analyst-001",
      "overridden_at": "2026-04-14T12:00:00Z",
      "immutable": true
    },
    {
      "id": "uuid",
      "override_decision": "force_include",
      "reason": "AI detection incorrect, finding is valid",
      "analyst_notes": "Tested manually, vulnerability confirmed",
      "overridden_by": "analyst-002",
      "overridden_at": "2026-04-14T13:30:00Z",
      "immutable": true
    }
  ]
}
```

---

## Finding Validation States

### validation_status (ScanFinding column)
- `pending_analyst_review` — Awaiting analyst decision
- `approved_for_submission` — Approved, can be submitted
- `excluded` — Rejected as false positive, will not be submitted

### finding_state (ScanFinding column)
- `valid` — Real vulnerability
- `false_positive` — Not a real vulnerability
- `duplicate` — Same as another finding
- `out_of_scope` — Outside authorized scope

### False Positive Confidence Levels
- 0.0–0.19 — Very likely real (analyst priority: lower)
- 0.20–0.39 — Probably real
- 0.40–0.59 — Could be either way
- 0.60–0.79 — Likely false positive (analyst priority: higher)
- 0.80–1.00 — Very likely false positive (analyst priority: highest)

---

## False Positive Detection Heuristics

### Scoring System
Each heuristic adds to confidence score (max 1.0):

| Heuristic | Score | Trigger |
|-----------|-------|---------|
| Not reproducible | +0.30 | No PoC OR no endpoint OR no payload |
| Expected behavior | +0.25 | XSS in error page OR open redirect same-site |
| Input validation | +0.20 | Description mentions "encoded", "escaped", "sanitized" |
| Mitigating controls | +0.15 | Description mentions "WAF", "CSP", "firewall" |
| Third-party code | +0.10 | Endpoint/description contains "jquery", "vendor", "node_modules" |
| WAF blocked | +0.20 | Description/PoC contains "blocked by waf" |

**Threshold**: 0.60+ = flagged as likely false positive (informational, analyst decides)

### Example Calculations

**Finding: Real stored XSS**
```
Checks:
  ✓ Reproducible (has PoC, endpoint, payload) → +0.0
  ✓ Not expected behavior (not in error page) → +0.0
  ✓ No mitigating controls mentioned → +0.0
  ✓ First-party code (not vendor) → +0.0
  ✓ Not WAF blocked → +0.0

Total: 0.0 (flagged as likely real)
Primary reason: None
```

**Finding: XSS in error page (false positive)**
```
Checks:
  ✓ Reproducible → +0.0
  ✓ Expected behavior (XSS in error page) → +0.25
  ✓ Not validated in description → +0.0
  ✓ Not mitigated → +0.0
  ✓ Not third-party → +0.0

Total: 0.25 (likely real, but watch for expected behavior)
Primary reason: expected_behavior
```

**Finding: Non-reproducible XSS (false positive)**
```
Checks:
  ✗ Not reproducible (no payload) → +0.30
  ✓ Not expected behavior → +0.0
  ✓ Not validated → +0.0
  ✓ Not mitigated → +0.0
  ✓ Not third-party → +0.0

Total: 0.30 (likely real, but needs PoC)
Primary reason: not_reproducible
```

---

## Authentication

All endpoints require:
```http
Authorization: Bearer <session_token>
X-CSRF-Token: <csrf_token>
```

Authenticated via `get_current_user` dependency. User identity tracked in:
- Abort requests: `abort_requested_by`
- Override decisions: `overridden_by` (FindingOverride record)
- All operations logged for audit trail

---

## Error Responses

### Finding Not Found
```http
404 Not Found
{
  "detail": "Finding not found: {finding_id}"
}
```

### Invalid Decision
```http
400 Bad Request
{
  "detail": "Invalid decision: {decision}. Must be: approve, exclude, force_include"
}
```

### Authorization Failure
```http
403 Forbidden
{
  "detail": "Not authorized"
}
```

### Batch Size Exceeded
```http
400 Bad Request
{
  "detail": "Batch too large: 25 findings. Maximum 20 per batch"
}
```

---

## Rate Limits

- Validation queue: 100 requests/minute per analyst
- Override decisions: 200 requests/minute per analyst
- Batch approve: 50 requests/minute per analyst

---

## Example Workflows

### Analyst Reviewing Queue

**1. Get pending findings**
```bash
curl -X GET "http://localhost:8080/api/v1/validation/queue?analyst_id=analyst-001" \
  -H "Authorization: Bearer $TOKEN"
```

**2. Review each finding**
```bash
# Option A: Quick approve
curl -X POST "http://localhost:8080/api/v1/validation/findings/{finding_id}/approve" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"notes": "Confirmed vulnerable"}'

# Option B: Quick exclude
curl -X POST "http://localhost:8080/api/v1/validation/findings/{finding_id}/exclude" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"reason": "False positive"}'

# Option C: Detailed review
curl -X POST "http://localhost:8080/api/v1/validation/findings/{finding_id}/review" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "decision": "force_include",
    "reason": "AI detection wrong, but manually confirmed vulnerable",
    "notes": "Tested with custom payload, confirmed XSS"
  }'
```

**3. Bulk approve low-risk findings**
```bash
curl -X POST "http://localhost:8080/api/v1/validation/batch-approve" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "finding_ids": ["uuid1", "uuid2", "uuid3", ...],
    "analyst_id": "analyst-001"
  }'
```

**4. Check stats**
```bash
curl -X GET "http://localhost:8080/api/v1/validation/stats" \
  -H "Authorization: Bearer $TOKEN"
```

### Emergency Scan Abort

**1. Request abort**
```bash
curl -X POST "http://localhost:8080/api/v1/safety/scans/{scan_id}/abort" \
  -H "Authorization: Bearer $TOKEN" \
  -d "reason=Scope%20violation%20detected"
```

**2. Check abort status**
```bash
curl -X GET "http://localhost:8080/api/v1/safety/scans/{scan_id}/abort-status" \
  -H "Authorization: Bearer $TOKEN"
```

**3. List violations**
```bash
curl -X GET "http://localhost:8080/api/v1/safety/violations?program_id={program_id}" \
  -H "Authorization: Bearer $TOKEN"
```

---

## Integration with Submission Pipeline

The submission pipeline checks `ensure_finding_approved_for_submission()` before submitting:

```python
# In submission_service.py
finding, validation_error = await ensure_finding_approved_for_submission(db, finding_id)
if validation_error:
    # Finding not approved, submission blocked
    return validation_error
# Finding approved, submission proceeds
```

**Result**:
- ✓ Approved findings submitted to bounty platform
- ✓ Excluded findings blocked (not submitted)
- ✓ Pending findings queued (awaiting analyst)

---

## Dashboard Integration

### Queue Summary (for analyst dashboard)
```javascript
// Fetch queue stats
const response = await fetch('/api/v1/validation/stats');
const stats = await response.json();

// Display
Pending Review: stats.pending_review
Approved: stats.approved_for_submission
Excluded: stats.excluded
Total: stats.total_findings
```

### Queue Display (for finding list)
```javascript
// Fetch queue
const response = await fetch('/api/v1/validation/queue?analyst_id=analyst-001');
const queue = await response.json();

// Display findings sorted by FP confidence
queue.findings.sort((a, b) => 
  b.false_positive_confidence - a.false_positive_confidence
);

// Show FP confidence as badge
findings.map(f => ({
  ...f,
  fpBadge: f.false_positive_confidence >= 0.6 ? '⚠️ Likely FP' : '✓ Likely Real'
}));
```

---

**Last Updated**: 2026-04-14  
**API Version**: v1  
**Status**: Production Ready
