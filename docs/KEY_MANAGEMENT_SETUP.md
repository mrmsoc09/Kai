# Kai Key Management & PGP Approval System Setup Guide

## Overview

Project Kai v7.5 introduces a comprehensive cryptographic key management system with Human-in-the-Loop (HiL) approval workflows using PGP signatures. This enables:

- **Admin PGP Keys**: For signing high-risk action approvals
- **User Keys**: SSH keys, API keys, and personal PGP keys for authentication
- **Key Rotation**: Secure key lifecycle management with rollback
- **Audit Trail**: Complete tracking of all key operations and approvals

## Directory Structure

```
/var/lib/k1/
├── keys/                           # Encrypted key storage
│   ├── pgp_keys/                   # Admin PGP keys
│   ├── user_keys/                  # User SSH/API keys
│   └── rotation_backups/           # Key rotation backups
└── audit_logs/                     # Key and approval audit trails
```

## 1. Initial Setup: Admin PGP Keys

### Step 1: Generate Admin PGP Key (if not already present)

```bash
# Install GPG
apt-get install gnupg2

# Generate key with no passphrase (stored encrypted in Kai)
gpg --gen-key
# Follow prompts:
# - Name: Your Admin Name
# - Email: admin@yourdomain.com
# - No passphrase (Kai handles encryption)

# Export public and private keys
gpg --export --armor admin@yourdomain.com > admin_public.asc
gpg --export-secret-keys --armor admin@yourdomain.com > admin_private.asc

# Secure the files
chmod 600 admin_private.asc
```

### Step 2: Import Admin PGP Key into Kai

**Via API:**

```bash
curl -X POST http://localhost:8000/api/keys/admin/import \
  -H "Content-Type: application/json" \
  -d '{
    "admin_id": "admin_01",
    "pgp_key_content": "-----BEGIN PGP PRIVATE KEY BLOCK-----\n...\n-----END PGP PRIVATE KEY BLOCK-----",
    "is_primary": true,
    "description": "Primary admin signing key"
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Admin PGP key imported successfully: 8F7E6D5C4B3A2F1E",
  "key_id": "pgp_xyz123",
  "fingerprint": "8F7E6D5C4B3A2F1E",
  "created_at": "2026-02-02T12:00:00",
  "is_primary": true
}
```

### Step 3: Verify Admin Key Import

```bash
curl -X GET http://localhost:8000/api/keys/admin/admin_01/primary-key
```

Response:
```json
{
  "key_id": "pgp_xyz123",
  "fingerprint": "8F7E6D5C4B3A2F1E",
  "algorithm": "RSA",
  "created_at": "2026-02-02T12:00:00",
  "status": "active",
  "is_primary": true
}
```

## 2. Admin Key Rotation

### Scenario: Quarterly Key Rotation

**Step 1: Generate New Key**
```bash
gpg --gen-key
# Generate new key for same admin
```

**Step 2: Schedule Rotation (Future)**
```bash
curl -X POST http://localhost:8000/api/keys/rotation/plan \
  -H "Content-Type: application/json" \
  -d '{
    "key_id": "pgp_xyz123",
    "new_key_content": "-----BEGIN PGP PRIVATE KEY BLOCK-----\n...\n-----END PGP PRIVATE KEY BLOCK-----",
    "scheduled_for": "2026-02-09T00:00:00",
    "reason": "Quarterly rotation - 90 day schedule",
    "authorized_by": "security_team"
  }'
```

**Step 3: Execute Rotation (when scheduled)**
```bash
curl -X POST http://localhost:8000/api/keys/rotation/ROTATION_ID/execute \
  -H "Content-Type: application/json" \
  -d '{
    "rotation_id": "rotation_abc123",
    "new_key_content": "-----BEGIN PGP PRIVATE KEY BLOCK-----\n...\n-----END PGP PRIVATE KEY BLOCK-----",
    "authorized_by": "admin_01"
  }'
```

**Step 4: If Needed - Rollback Rotation**
```bash
curl -X POST http://localhost:8000/api/keys/rotation/ROTATION_ID/rollback \
  -H "Content-Type: application/json" \
  -d '{
    "rotation_id": "rotation_abc123",
    "reason": "New key validation failed"
  }'
```

## 3. User Key Management

### Step 1: Import User Keys (SSH, API, PGP)

```bash
# Export user's SSH public key
cat ~/.ssh/id_rsa.pub > user_ssh_key.pub

# Export user's PGP public key (if applicable)
gpg --export --armor user@example.com > user_pgp.asc

# Prepare API keys (e.g., from platforms)
# EXAMPLE: HackerOne API token, etc.
```

**Import via API:**
```bash
curl -X POST http://localhost:8000/api/keys/users/import \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_alice_01",
    "pgp_public_key": "-----BEGIN PGP PUBLIC KEY BLOCK-----\n...\n-----END PGP PUBLIC KEY BLOCK-----",
    "ssh_public_key": "ssh-rsa AAAAB3NzaC1yc2E... user@example.com",
    "api_keys": {
      "hackerone": "api_key_here_abc123xyz",
      "bugcrowd": "api_key_here_def456uvw"
    },
    "description": "Alice - Security Researcher"
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Imported 4 keys for user",
  "imported_keys": {
    "pgp_public": {
      "key_id": "pgp_user_123",
      "fingerprint": "9A8B7C6D5E4F3A2B",
      "algorithm": "RSA",
      "status": "active"
    },
    "ssh_public": {
      "key_id": "ssh_user_456",
      "fingerprint": "ssh-rsa:1234567890",
      "algorithm": "ED25519",
      "status": "active"
    },
    "api_key_hackerone": {
      "key_id": "api_hacker_789",
      "fingerprint": "sha256:abcd1234",
      "status": "active"
    },
    "api_key_bugcrowd": {
      "key_id": "api_bugcrowd_012",
      "fingerprint": "sha256:efgh5678",
      "status": "active"
    }
  }
}
```

### Step 2: List User Keys

```bash
curl -X GET http://localhost:8000/api/keys/users/user_alice_01/keys
```

Response:
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
  ...
]
```

### Step 3: Revoke User Key (if compromised)

```bash
curl -X POST http://localhost:8000/api/keys/users/user_alice_01/keys/pgp_user_123/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "User reported key compromise - requesting replacement"
  }'
```

## 4. Human-in-the-Loop Approval Workflow

### Overview of Approval Flow

```
1. High-risk action detected (e.g., exploit execution)
              ↓
2. Kai creates approval request with PGP requirement
              ↓
3. Request enters admin approval queue
              ↓
4. Admin receives notification and reviews
              ↓
5. Admin signs decision with their PGP key
              ↓
6. Kai verifies signature against admin's stored key
              ↓
7. If valid: Action approved and execution proceeds
   If invalid: Rejection with audit trail
              ↓
8. Complete audit trail recorded
```

### Example 1: Approving a Weaponizer Action (Exploitation)

**Stage 1: Action Requiring Approval**

System detects high-risk action (weaponizer creating exploit payload):

```
Action: exploitation_attempt
Target: target.example.com
Risk Level: critical
Description: Generate RCE payload for CVE-2025-XXXX
```

**Stage 2: Request Approval**

```bash
curl -X POST http://localhost:8000/api/approvals/request \
  -H "Content-Type: application/json" \
  -d '{
    "action_id": "weaponizer_attack_001",
    "target_domain": "target.example.com",
    "action_type": "exploitation",
    "description": "Generate RCE payload for CVE-2025-XXXX with base64 encoding obfuscation",
    "risk_level": "critical",
    "requires_pgp": true,
    "metadata": {
      "vuln_type": "Remote Code Execution",
      "cvss_score": 9.8,
      "scope": "authorized_target"
    }
  }'
```

**Response:**
```json
{
  "success": true,
  "approval_id": "approval_xyz789",
  "message": "Approval request created",
  "requires_pgp": true,
  "expires_in_hours": 24
}
```

**Stage 3: Check Pending Approvals**

```bash
curl -X GET http://localhost:8000/api/approvals/pending
```

Response:
```json
[
  {
    "approval_id": "approval_xyz789",
    "action_id": "weaponizer_attack_001",
    "target_domain": "target.example.com",
    "action_type": "exploitation",
    "description": "Generate RCE payload for CVE-2025-XXXX with base64 encoding obfuscation",
    "risk_level": "critical",
    "created_at": "2026-02-02T12:00:00",
    "expires_at": "2026-02-03T12:00:00",
    "time_pending_hours": 0.5
  }
]
```

**Stage 4: Admin Signs Approval with PGP Key**

First, admin creates the PGP signature:

```bash
# Create message to sign (ID:Action:Domain)
echo "approval_xyz789:weaponizer_attack_001:target.example.com" > approval_message.txt

# Sign with GPG (admin's private key)
gpg --sign --armor --detach-sign approval_message.txt
# Prompts for passphrase (use your GPG passphrase, or configure for automation)

# Export signature
cat approval_message.txt.asc > signature.asc
```

Then submit the signed approval:

```bash
SIGNATURE=$(cat signature.asc)

curl -X POST http://localhost:8000/api/approvals/decide \
  -H "Content-Type: application/json" \
  -d '{
    "approval_id": "approval_xyz789",
    "admin_id": "admin_01",
    "decision": "approved",
    "pgp_signature": "'"$SIGNATURE"'",
    "justification": "Target confirmed in scope, RoE authorized, CVE-2025-XXXX verified exploitable"
  }'
```

**Response:**
```json
{
  "success": true,
  "decision": "approved",
  "admin_id": "admin_01",
  "signed": true,
  "signed_at": "2026-02-02T12:15:30"
}
```

**Stage 5: Action Execution Proceeds**

System verifies PGP signature:
✓ Signature valid
✓ Signed by admin_01
✓ Fingerprint matches stored key
→ **ACTION APPROVED FOR EXECUTION**

### Example 2: Rejecting a High-Risk Action

If admin determines target is out-of-scope or RoE not met:

```bash
SIGNATURE=$(cat rejection_signature.asc)

curl -X POST http://localhost:8000/api/approvals/decide \
  -H "Content-Type: application/json" \
  -d '{
    "approval_id": "approval_xyz789",
    "admin_id": "admin_01",
    "decision": "rejected",
    "pgp_signature": "'"$SIGNATURE"'",
    "justification": "Target IP 10.0.0.5 is not in authorized scope per RoE. Request in-scope target or updated authorization."
  }'
```

Response:
```json
{
  "success": true,
  "decision": "rejected",
  "admin_id": "admin_01",
  "signed": true,
  "signed_at": "2026-02-02T12:20:00"
}
```

→ **ACTION REJECTED - EXECUTION BLOCKED**

### Example 3: Escalation to Senior Admin

If approval requires additional review:

```bash
curl -X POST http://localhost:8000/api/approvals/approval_xyz789/escalate \
  -H "Content-Type: application/json" \
  -d '{
    "approval_id": "approval_xyz789",
    "escalation_reason": "Target ambiguous scope - escalating to security chief for RoE clarification",
    "escalate_to_admins": ["admin_security_chief", "admin_legal"]
  }'
```

## 5. Monitoring & Audit

### Check Approval Status

```bash
curl -X GET http://localhost:8000/api/approvals/approval_xyz789/status
```

### View Approval History

```bash
curl -X GET http://localhost:8000/api/approvals/history/approval_xyz789
```

### Get Complete Audit Trail

```bash
curl -X GET http://localhost:8000/api/approvals/audit-trail
```

### Key Management Dashboard

```bash
curl -X GET http://localhost:8000/api/keys/dashboard/summary
```

Response:
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

### Approval Workflow Dashboard

```bash
curl -X GET http://localhost:8000/api/approvals/dashboard/summary
```

Response:
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

## 6. Key Expiration & Rotation

### Check Expiring Keys

```bash
curl -X GET "http://localhost:8000/api/keys/expiring?days=30"
```

Response:
```json
[
  {
    "key_id": "pgp_admin_old",
    "owner_id": "admin_01",
    "owner_type": "admin",
    "fingerprint": "OLD_FINGERPRINT",
    "expires_at": "2026-02-15T00:00:00",
    "days_until_expiry": 13
  }
]
```

### Automatic Rotation Workflow

```bash
# 1. Plan rotation
curl -X POST http://localhost:8000/api/keys/rotation/plan \
  -d '{"key_id": "pgp_admin_old", "new_key_content": "...", ...}'

# 2. Execute when scheduled
curl -X POST http://localhost:8000/api/keys/rotation/ROTATION_ID/execute \
  -d '{"rotation_id": "...", "new_key_content": "...", ...}'

# 3. View rotation history
curl -X GET http://localhost:8000/api/keys/rotation/pgp_admin_old/history
```

## 7. Security Best Practices

### Admin Key Security

- **Storage**: Keys stored encrypted in `/var/lib/k1/keys/`
- **Access Control**: Only system processes and authorized admins
- **Rotation**: Every 90 days (quarterly)
- **Backup**: Automatic backups for rollback capability
- **Monitoring**: All key operations logged with timestamps

### Approval Workflow Security

- **PGP Verification**: All high-risk approvals must be signed
- **Audit Trail**: Immutable record of all approval decisions
- **Expiration**: Approval requests expire after 24 hours
- **Escalation**: Critical decisions escalate to senior admins
- **Integration**: Tied to orchestration graph for complete tracking

### Key Lifecycle

1. **Import**: Key added to system, encrypted at rest
2. **Active**: Key available for use, monitored for expiration
3. **Rotation Planning**: New key prepared, schedule set
4. **Rotation Execution**: Old key deactivated, new key activated
5. **Backup Retention**: Old key backup kept for rollback (30 days)
6. **Expiration**: Expired keys marked as inactive
7. **Revocation**: Compromised keys immediately revoked

## 8. Integration with K1 Workflow

Key management integrates at these points:

1. **Orchestration Graph**: HiL approvals recorded in phase transitions
2. **Finding Validation**: Admin PGP keys sign approval of high-severity findings
3. **Weaponizer**: Exploitation actions require PGP-signed approval
4. **Auditor**: Uses key management for RoE validation and signature verification
5. **Agent Training**: PGP keys authorize training curriculum changes

## 9. Database Migration (Future)

Current implementation: In-memory storage (suitable for testing)

For production, migrate to PostgreSQL:

```sql
CREATE TABLE crypto_keys (
  key_id TEXT PRIMARY KEY,
  key_type TEXT NOT NULL,
  owner_type TEXT NOT NULL,
  owner_id TEXT NOT NULL,
  status TEXT NOT NULL,
  key_content BYTEA NOT NULL, -- encrypted
  fingerprint TEXT,
  created_at TIMESTAMP,
  expires_at TIMESTAMP,
  audit_log JSONB,
  UNIQUE(owner_id, key_type)
);

CREATE TABLE approval_requests (
  approval_id TEXT PRIMARY KEY,
  action_id TEXT NOT NULL,
  target_domain TEXT NOT NULL,
  risk_level TEXT,
  status TEXT NOT NULL,
  pgp_signature TEXT,
  admin_id TEXT,
  created_at TIMESTAMP,
  decided_at TIMESTAMP,
  metadata JSONB
);
```

## 10. Troubleshooting

### Issue: "Key not found"
**Solution**: Verify key was imported with `GET /api/keys/admin/{admin_id}/keys`

### Issue: "Signature verification failed"
**Solution**: Ensure you're using the same key to sign that was imported

### Issue: "Key expired"
**Solution**: Initiate key rotation or extend expiration date

### Issue: "Approval expired"
**Solution**: Approvals expire after 24 hours. Create new approval request.

---

## Complete Example: From Import to Approval

```bash
#!/bin/bash
# Complete workflow

# 1. Generate and export admin key
gpg --gen-key  # Interactive
gpg --export-secret-keys --armor admin@domain.com > admin_key.asc

# 2. Import into Kai
ADMIN_KEY=$(cat admin_key.asc)
curl -X POST http://localhost:8000/api/keys/admin/import \
  -d "{'admin_id': 'admin_01', 'pgp_key_content': '$ADMIN_KEY', 'is_primary': true}"

# 3. Create approval request
APPROVAL=$(curl -s -X POST http://localhost:8000/api/approvals/request \
  -d '{"action_id": "exploit_001", "target_domain": "target.com", "risk_level": "critical"}' \
  | jq -r '.approval_id')

# 4. Sign approval
echo "$APPROVAL:exploit_001:target.com" > msg.txt
gpg --sign --armor --detach-sign msg.txt
SIGNATURE=$(cat msg.txt.asc)

# 5. Submit signed approval
curl -X POST http://localhost:8000/api/approvals/decide \
  -d "{'approval_id': '$APPROVAL', 'admin_id': 'admin_01', 'decision': 'approved', 'pgp_signature': '$SIGNATURE'}"

# 6. Verify approval recorded
curl -X GET http://localhost:8000/api/approvals/$APPROVAL/status
```

---

For detailed API documentation, see `docs/API_KEYS.md` and `docs/API_APPROVALS.md`.
