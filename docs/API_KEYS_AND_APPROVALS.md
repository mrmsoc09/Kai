# Kai Key Management & Approval API Reference

## Base URL

```
http://localhost:8000/api
```

## Authentication

All endpoints require proper API authentication (to be implemented). For testing, endpoints are accessible to authenticated users.

---

## Key Management API (`/api/keys`)

### Admin Key Management

#### Import Admin PGP Key

**Endpoint:** `POST /api/keys/admin/import`

**Purpose:** Import a PGP key for an admin to use for signing HiL approvals

**Request:**
```json
{
  "admin_id": "admin_01",
  "pgp_key_content": "-----BEGIN PGP PRIVATE KEY BLOCK-----\n...\n-----END PGP PRIVATE KEY BLOCK-----",
  "is_primary": true,
  "description": "Admin's primary signing key"
}
```

**Response (201 Created):**
```json
{
  "success": true,
  "message": "Admin PGP key imported successfully: 8F7E6D5C4B3A2F1E",
  "key_id": "pgp_admin_xyz123",
  "fingerprint": "8F7E6D5C4B3A2F1E",
  "created_at": "2026-02-02T12:00:00",
  "is_primary": true
}
```

**Error Responses:**
- `400 Bad Request`: Invalid key content
- `500 Internal Server Error`: Import failed

---

#### Rotate Admin PGP Key

**Endpoint:** `POST /api/keys/admin/rotate`

**Purpose:** Rotate an admin's key with automatic rollback capability

**Request:**
```json
{
  "current_key_id": "pgp_admin_xyz123",
  "new_pgp_key_content": "-----BEGIN PGP PRIVATE KEY BLOCK-----\n...\n-----END PGP PRIVATE KEY BLOCK-----",
  "reason": "Quarterly rotation",
  "authorized_by": "admin_security_chief"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Admin PGP key rotated successfully. Old key: 8F7E6D5C4B3A2F1E",
  "rotation_id": "rotation_abc789",
  "old_key_fingerprint": "8F7E6D5C4B3A2F1E",
  "new_key_fingerprint": "9A8B7C6D5E4F3A2B",
  "completed_at": "2026-02-02T12:15:30",
  "rollback_available": true
}
```

---

#### Get Admin Primary Key

**Endpoint:** `GET /api/keys/admin/{admin_id}/primary-key`

**Purpose:** Get metadata of the primary key for an admin (not the key content itself)

**Response (200 OK):**
```json
{
  "key_id": "pgp_admin_xyz123",
  "fingerprint": "8F7E6D5C4B3A2F1E",
  "algorithm": "RSA",
  "created_at": "2026-02-02T12:00:00",
  "status": "active",
  "is_primary": true
}
```

**Error Responses:**
- `404 Not Found`: Admin or primary key not found

---

#### List Admin Keys

**Endpoint:** `GET /api/keys/admin/{admin_id}/keys`

**Purpose:** List all keys (active and inactive) for an admin

**Response (200 OK):**
```json
[
  {
    "key_id": "pgp_admin_xyz123",
    "key_type": "pgp_private",
    "status": "active",
    "fingerprint": "8F7E6D5C4B3A2F1E",
    "algorithm": "RSA",
    "created_at": "2026-02-02T12:00:00",
    "is_primary": true
  },
  {
    "key_id": "pgp_admin_old456",
    "key_type": "pgp_private",
    "status": "inactive",
    "fingerprint": "OLD_FINGERPRINT",
    "algorithm": "RSA",
    "created_at": "2025-11-01T00:00:00",
    "is_primary": false
  }
]
```

---

### User Key Management

#### Import User Keys

**Endpoint:** `POST /api/keys/users/import`

**Purpose:** Import one or multiple keys for a user (SSH, PGP public, API keys)

**Request:**
```json
{
  "user_id": "user_alice_01",
  "pgp_public_key": "-----BEGIN PGP PUBLIC KEY BLOCK-----\n...\n-----END PGP PUBLIC KEY BLOCK-----",
  "ssh_public_key": "ssh-rsa AAAAB3NzaC1yc2E... user@example.com",
  "api_keys": {
    "hackerone": "h1_abc123xyz789",
    "bugcrowd": "bc_def456uvw012",
    "intigriti": "integriti_ghi789rst345"
  },
  "description": "Alice - Security Researcher"
}
```

**Response (201 Created):**
```json
{
  "success": true,
  "message": "Imported 5 keys for user",
  "imported_keys": {
    "pgp_public": {
      "key_id": "pgp_user_123",
      "fingerprint": "9A8B7C6D5E4F3A2B",
      "algorithm": "RSA",
      "status": "active"
    },
    "ssh_public": {
      "key_id": "ssh_user_456",
      "fingerprint": "ssh-ed25519:1234567890",
      "algorithm": "ED25519",
      "status": "active"
    },
    "api_key_hackerone": {
      "key_id": "api_h1_789",
      "fingerprint": "sha256:abcd1234",
      "status": "active"
    },
    "api_key_bugcrowd": {
      "key_id": "api_bc_012",
      "fingerprint": "sha256:efgh5678",
      "status": "active"
    },
    "api_key_intigriti": {
      "key_id": "api_integriti_345",
      "fingerprint": "sha256:ijkl9012",
      "status": "active"
    }
  }
}
```

---

#### List User Keys

**Endpoint:** `GET /api/keys/users/{user_id}/keys`

**Purpose:** List all keys for a user with full metadata

**Response (200 OK):**
```json
[
  {
    "key_id": "pgp_user_123",
    "key_type": "pgp_public",
    "status": "active",
    "fingerprint": "9A8B7C6D5E4F3A2B",
    "algorithm": "RSA",
    "created_at": "2026-02-02T12:00:00",
    "expires_at": null,
    "last_used_at": "2026-02-02T15:30:00",
    "tags": [],
    "description": "Alice PGP public key"
  },
  {
    "key_id": "ssh_user_456",
    "key_type": "ssh_public",
    "status": "active",
    "fingerprint": "ssh-ed25519:1234567890",
    "algorithm": "ED25519",
    "created_at": "2026-02-02T12:00:00",
    "expires_at": "2027-02-02",
    "last_used_at": "2026-02-02T14:00:00",
    "tags": ["workstation"],
    "description": "Alice workstation SSH key"
  }
]
```

---

#### Revoke User Key

**Endpoint:** `POST /api/keys/users/{user_id}/keys/{key_id}/revoke`

**Purpose:** Revoke a user's key (e.g., if compromised)

**Query Parameters:**
- `reason` (optional): Reason for revocation

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Key pgp_user_123 revoked",
  "key_id": "pgp_user_123"
}
```

---

### Key Rotation

#### Plan Key Rotation

**Endpoint:** `POST /api/keys/rotation/plan`

**Purpose:** Schedule a key rotation for future execution

**Request:**
```json
{
  "key_id": "pgp_admin_xyz123",
  "new_key_content": "-----BEGIN PGP PRIVATE KEY BLOCK-----\n...\n-----END PGP PRIVATE KEY BLOCK-----",
  "scheduled_for": "2026-02-09T00:00:00",
  "reason": "Quarterly rotation schedule",
  "authorized_by": "admin_security_chief"
}
```

**Response (201 Created):**
```json
{
  "success": true,
  "message": "Key rotation planned: rotation_xyz789",
  "rotation_id": "rotation_xyz789",
  "key_id": "pgp_admin_xyz123",
  "status": "initiated",
  "scheduled_for": "2026-02-09T00:00:00",
  "reason": "Quarterly rotation schedule",
  "rollback_available": true
}
```

---

#### Execute Key Rotation

**Endpoint:** `POST /api/keys/rotation/{rotation_id}/execute`

**Purpose:** Execute a planned key rotation

**Request:**
```json
{
  "rotation_id": "rotation_xyz789",
  "new_key_content": "-----BEGIN PGP PRIVATE KEY BLOCK-----\n...\n-----END PGP PRIVATE KEY BLOCK-----",
  "authorized_by": "admin_01"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Key rotation completed: pgp_admin_new789",
  "rotation_id": "rotation_xyz789"
}
```

---

#### Rollback Key Rotation

**Endpoint:** `POST /api/keys/rotation/{rotation_id}/rollback`

**Purpose:** Rollback a completed rotation to restore the previous key

**Request:**
```json
{
  "rotation_id": "rotation_xyz789",
  "reason": "New key validation failed"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Key rotation rolled back: rotation_xyz789",
  "rotation_id": "rotation_xyz789"
}
```

---

#### Get Key Rotation History

**Endpoint:** `GET /api/keys/rotation/{key_id}/history`

**Purpose:** Get complete rotation history for a key

**Response (200 OK):**
```json
[
  {
    "rotation_id": "rotation_xyz789",
    "initiated_at": "2026-02-02T10:00:00",
    "scheduled_for": "2026-02-09T00:00:00",
    "completed_at": "2026-02-09T00:15:30",
    "status": "completed",
    "reason": "Quarterly rotation schedule",
    "authorized_by": "admin_01"
  },
  {
    "rotation_id": "rotation_abc123",
    "initiated_at": "2025-11-01T10:00:00",
    "scheduled_for": "2025-11-08T00:00:00",
    "completed_at": "2025-11-08T00:12:00",
    "status": "completed",
    "reason": "Quarterly rotation schedule",
    "authorized_by": "admin_01"
  }
]
```

---

### Key Verification

#### Verify PGP Signature

**Endpoint:** `POST /api/keys/verify/pgp-signature`

**Purpose:** Verify a PGP signature using stored keys

**Request:**
```json
{
  "signature": "-----BEGIN PGP SIGNATURE-----\n...\n-----END PGP SIGNATURE-----",
  "message": "Message that was signed",
  "expected_key_id": "pgp_admin_xyz123"
}
```

**Response (200 OK):**
```json
{
  "valid": true,
  "message": "Signature verified",
  "signer_key_id": "pgp_admin_xyz123",
  "verified_at": "2026-02-02T12:30:00"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid signature or message
- `404 Not Found`: Key not found

---

### Monitoring & Audit

#### Get Expiring Keys

**Endpoint:** `GET /api/keys/expiring`

**Query Parameters:**
- `days` (optional, default=30): Days until expiration to check

**Response (200 OK):**
```json
[
  {
    "key_id": "pgp_admin_old",
    "owner_id": "admin_01",
    "owner_type": "admin",
    "fingerprint": "OLD_FINGERPRINT",
    "expires_at": "2026-02-15T00:00:00",
    "days_until_expiry": 13
  },
  {
    "key_id": "ssh_user_678",
    "owner_id": "user_bob",
    "owner_type": "user",
    "fingerprint": "ssh-ed25519:abc123",
    "expires_at": "2026-02-10T00:00:00",
    "days_until_expiry": 8
  }
]
```

---

#### Get Key Audit Trail

**Endpoint:** `GET /api/keys/keys/{key_id}/audit-trail`

**Purpose:** Get complete audit trail of operations on a key

**Response (200 OK):**
```json
[
  {
    "timestamp": "2026-02-02T12:00:00",
    "operation": "import",
    "details": {
      "admin_id": "admin_01",
      "fingerprint": "8F7E6D5C4B3A2F1E"
    }
  },
  {
    "timestamp": "2026-02-02T12:15:30",
    "operation": "rotate",
    "details": {
      "new_key_id": "pgp_admin_new789",
      "reason": "Quarterly rotation"
    }
  }
]
```

---

#### Get Key Usage Logs

**Endpoint:** `GET /api/keys/usage-logs`

**Query Parameters:**
- `key_id` (optional): Filter by specific key
- `owner_id` (optional): Filter by owner
- `limit` (optional, default=100): Number of logs to return

**Response (200 OK):**
```json
[
  {
    "timestamp": "2026-02-02T12:15:30",
    "key_id": "pgp_admin_xyz123",
    "operation": "verify",
    "success": true,
    "user_id": "approval_workflow",
    "details": {
      "message_length": 52
    }
  },
  {
    "timestamp": "2026-02-02T12:10:00",
    "key_id": "api_h1_789",
    "operation": "decrypt",
    "success": true,
    "user_id": "user_alice_01",
    "details": {
      "source": "bounty_submission"
    }
  }
]
```

---

#### Get Key Management Dashboard Summary

**Endpoint:** `GET /api/keys/dashboard/summary`

**Purpose:** Get overall key management status

**Response (200 OK):**
```json
{
  "total_keys": 42,
  "active_keys": 40,
  "by_owner_type": {
    "admin": 3,
    "user": 35,
    "agent": 4
  },
  "keys_expiring_in_30_days": 2,
  "pending_rotations": 1,
  "recent_usage_count": 156,
  "timestamp": "2026-02-02T12:30:00"
}
```

---

## Approval API (`/api/approvals`)

### Approval Management

#### Request Approval

**Endpoint:** `POST /api/approvals/request`

**Purpose:** Create an approval request for a high-risk action

**Request:**
```json
{
  "action_id": "weaponizer_exploit_001",
  "target_domain": "target.example.com",
  "action_type": "exploitation",
  "description": "Generate RCE payload for CVE-2025-XXXX with base64 encoding",
  "risk_level": "critical",
  "requires_pgp": true,
  "metadata": {
    "vuln_type": "Remote Code Execution",
    "cvss_score": 9.8,
    "scope": "authorized_target"
  }
}
```

**Response (201 Created):**
```json
{
  "success": true,
  "approval_id": "approval_xyz789",
  "message": "Approval request created",
  "requires_pgp": true,
  "expires_in_hours": 24
}
```

---

#### Make Approval Decision

**Endpoint:** `POST /api/approvals/decide`

**Purpose:** Approve or reject an action with optional PGP signature

**Request (Approval):**
```json
{
  "approval_id": "approval_xyz789",
  "admin_id": "admin_01",
  "decision": "approved",
  "pgp_signature": "-----BEGIN PGP SIGNATURE-----\n...\n-----END PGP SIGNATURE-----",
  "justification": "Target confirmed in scope, RoE authorized, CVE verified exploitable"
}
```

**Request (Rejection):**
```json
{
  "approval_id": "approval_xyz789",
  "admin_id": "admin_01",
  "decision": "rejected",
  "pgp_signature": "-----BEGIN PGP SIGNATURE-----\n...\n-----END PGP SIGNATURE-----",
  "justification": "Target IP not in authorized scope per RoE"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "decision": "approved",
  "admin_id": "admin_01",
  "signed": true,
  "signed_at": "2026-02-02T12:15:30"
}
```

---

#### Get Pending Approvals

**Endpoint:** `GET /api/approvals/pending`

**Purpose:** Get list of approval requests awaiting decision

**Response (200 OK):**
```json
[
  {
    "approval_id": "approval_xyz789",
    "action_id": "weaponizer_exploit_001",
    "target_domain": "target.example.com",
    "action_type": "exploitation",
    "description": "Generate RCE payload for CVE-2025-XXXX with base64 encoding",
    "risk_level": "critical",
    "created_at": "2026-02-02T12:00:00",
    "expires_at": "2026-02-03T12:00:00",
    "time_pending_hours": 0.5
  },
  {
    "approval_id": "approval_abc123",
    "action_id": "reconnaissance_scan_002",
    "target_domain": "scope.example.com",
    "action_type": "reconnaissance",
    "description": "Port scan and service enumeration",
    "risk_level": "low",
    "created_at": "2026-02-02T11:00:00",
    "expires_at": "2026-02-03T11:00:00",
    "time_pending_hours": 1.5
  }
]
```

---

#### Get Approval Status

**Endpoint:** `GET /api/approvals/{approval_id}/status`

**Purpose:** Check current status of an approval request

**Response (200 OK):**
```json
{
  "approval_id": "approval_xyz789",
  "status": "decided",
  "decision": "approved",
  "admin_id": "admin_01",
  "signed_at": "2026-02-02T12:15:30"
}
```

**Alternate Response (Still Pending):**
```json
{
  "approval_id": "approval_xyz789",
  "status": "pending",
  "decision": null,
  "expires_at": "2026-02-03T12:00:00"
}
```

---

### Escalation

#### Escalate Approval

**Endpoint:** `POST /api/approvals/{approval_id}/escalate`

**Purpose:** Escalate an approval request to senior admins

**Request:**
```json
{
  "approval_id": "approval_xyz789",
  "escalation_reason": "Target scope ambiguous - requires legal review per RoE",
  "escalate_to_admins": ["admin_security_chief", "admin_legal", "admin_ciso"]
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "approval_id": "approval_xyz789",
  "message": "Approval escalated to 3 admins",
  "escalated_at": "2026-02-02T12:30:00"
}
```

---

### Audit & History

#### Get Approval History

**Endpoint:** `GET /api/approvals/history/{approval_id}`

**Purpose:** Get complete decision record for an approval

**Response (200 OK):**
```json
{
  "approval_id": "approval_xyz789",
  "action_id": "weaponizer_exploit_001",
  "decision": "approved",
  "admin_id": "admin_01",
  "admin_key_fingerprint": "8F7E6D5C4B3A2F1E",
  "signed_at": "2026-02-02T12:15:30",
  "justification": "Target confirmed in scope, RoE authorized, CVE verified exploitable",
  "pgp_signature_present": true
}
```

---

#### Get Approval Audit Trail

**Endpoint:** `GET /api/approvals/audit-trail`

**Query Parameters:**
- `event_type` (optional): Filter by event type
- `limit` (optional, default=100): Number of events to return

**Response (200 OK):**
```json
[
  {
    "timestamp": "2026-02-02T12:15:30",
    "event_type": "approval_granted",
    "details": {
      "approval_id": "approval_xyz789",
      "action_id": "weaponizer_exploit_001",
      "admin_id": "admin_01",
      "admin_fingerprint": "8F7E6D5C4B3A2F1E"
    }
  },
  {
    "timestamp": "2026-02-02T12:00:00",
    "event_type": "approval_requested",
    "details": {
      "approval_id": "approval_xyz789",
      "action_id": "weaponizer_exploit_001",
      "target_domain": "target.example.com",
      "risk_level": "critical"
    }
  }
]
```

---

### Dashboard

#### Get Approval Workflow Dashboard Summary

**Endpoint:** `GET /api/approvals/dashboard/summary`

**Purpose:** Get approval workflow metrics and statistics

**Response (200 OK):**
```json
{
  "pending_count": 3,
  "approved_count": 127,
  "rejected_count": 8,
  "escalated_count": 2,
  "total_decisions": 135,
  "average_decision_time_minutes": 15,
  "approval_rate": 94.07,
  "timestamp": "2026-02-02T12:30:00"
}
```

---

## Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request (validation error) |
| 404 | Not Found |
| 500 | Internal Server Error |

---

## Common Error Responses

### Invalid Key Content
```json
{
  "detail": "Failed to import admin PGP key: Invalid key format"
}
```

### Key Not Found
```json
{
  "detail": "Key not found"
}
```

### Signature Verification Failed
```json
{
  "detail": "Signature verification failed: Invalid signature or mismatched key"
}
```

### Approval Expired
```json
{
  "detail": "Approval request not found or expired"
}
```

---

## Integration Examples

### Example 1: Complete Approval Flow in Python

```python
import requests
import json

API_BASE = "http://localhost:8000/api"

# 1. Request approval
response = requests.post(
    f"{API_BASE}/approvals/request",
    json={
        "action_id": "exploit_001",
        "target_domain": "target.com",
        "action_type": "exploitation",
        "description": "Generate payload",
        "risk_level": "critical",
        "requires_pgp": True
    }
)
approval_id = response.json()["approval_id"]

# 2. Get approval status
response = requests.get(f"{API_BASE}/approvals/{approval_id}/status")
print(f"Status: {response.json()['status']}")

# 3. Admin signs and submits decision
import subprocess
message = f"{approval_id}:exploit_001:target.com"
signature_result = subprocess.run(
    ["gpg", "--sign", "--armor", "--detach-sign"],
    input=message.encode(),
    capture_output=True
)
signature = signature_result.stdout.decode()

response = requests.post(
    f"{API_BASE}/approvals/decide",
    json={
        "approval_id": approval_id,
        "admin_id": "admin_01",
        "decision": "approved",
        "pgp_signature": signature,
        "justification": "Approved"
    }
)
print(f"Decision: {response.json()['decision']}")
```

---

For implementation details, see `apps/backend/src/core/key_management.py` and `apps/backend/src/core/approval_workflow.py`.
