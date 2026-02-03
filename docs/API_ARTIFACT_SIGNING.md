# Artifact Signing & Chain of Custody API Reference

## Overview

The Artifact Signing API provides automated PGP signature generation and verification for vulnerability reports, scan logs, and other critical artifacts. This ensures tamper-proof chain of custody for all Kai operations.

**Base URL**: `http://localhost:8000/api/artifacts`

---

## Endpoints

### Initialization

#### Initialize Crypto System

**Endpoint**: `POST /api/artifacts/init`

**Purpose**: Load all Kaisonai PGP keys and initialize the signing infrastructure

**Query Parameters**:
- `gpg_home` (optional): Custom GPG home directory path (default: `~/.kai/gpg_home`)
- `key_source_dir` (optional): Custom key source directory (default: `/home/user/kai/Kai PGP-Keys`)

**Response (200 OK)**:
```json
{
  "success": true,
  "message": "Initialized crypto system: 4 keys imported",
  "import_results": {
    "total_files": 4,
    "total_keys_imported": 4,
    "identities": {
      "admin-kaisonai@pm.me": {
        "fingerprint": "8F7E6D5C4B3A2F1E",
        "status": "imported"
      },
      "user-kaisonai@pm.me": {
        "fingerprint": "9A8B7C6D5E4F3A2B",
        "status": "imported"
      },
      "infra-kaisonai@pm.me": {
        "fingerprint": "7B6C5D4E3F2A1B0C",
        "status": "imported"
      },
      "machine-kaisonai@pm.me": {
        "fingerprint": "ABC123DEF456789",
        "status": "imported"
      }
    },
    "errors": []
  },
  "system_status": {
    "gpg_home": "/home/user/.kai/gpg_home",
    "gpg_home_permissions": "700",
    "machine_identity": "machine-kaisonai@pm.me",
    "available_keys": 4,
    "signature_operations": 0,
    "verification_operations": 0,
    "trusted_identities": [
      "admin-kaisonai@pm.me",
      "user-kaisonai@pm.me",
      "infra-kaisonai@pm.me",
      "machine-kaisonai@pm.me"
    ]
  }
}
```

---

### Artifact Signing

#### Sign Artifact

**Endpoint**: `POST /api/artifacts/sign`

**Purpose**: Create a detached PGP signature for a vulnerability report or scan log

**Request**:
```json
{
  "artifact_path": "/var/lib/kai/reports/CVE-2025-12345_report.json",
  "output_path": "/var/lib/kai/reports/CVE-2025-12345_report.json.sig",
  "passphrase": "machine_passphrase"
}
```

**Response (200 OK)**:
```json
{
  "success": true,
  "message": "Artifact signed: /var/lib/kai/reports/CVE-2025-12345_report.json.sig",
  "signature": {
    "artifact_path": "/var/lib/kai/reports/CVE-2025-12345_report.json",
    "signature_path": "/var/lib/kai/reports/CVE-2025-12345_report.json.sig",
    "signer_identity": "machine-kaisonai@pm.me",
    "signer_fingerprint": "ABC123DEF456789",
    "signed_at": "2026-02-02T12:00:30.123456",
    "artifact_hash": "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6a7b8c9d0e1",
    "algorithm": "RSA"
  }
}
```

**Error Response (400 Bad Request)**:
```json
{
  "detail": "Artifact not found: /var/lib/kai/reports/nonexistent.json"
}
```

---

### Artifact Verification

#### Verify Artifact

**Endpoint**: `POST /api/artifacts/verify`

**Purpose**: Verify a signed artifact against imported public keys - detects tampering

**Request**:
```json
{
  "artifact_path": "/var/lib/kai/reports/CVE-2025-12345_report.json",
  "signature_path": "/var/lib/kai/reports/CVE-2025-12345_report.json.sig"
}
```

**Response (200 OK) - Valid Signature**:
```json
{
  "success": true,
  "message": "VERIFIED: Signed by Machine Kaisonai <machine-kaisonai@pm.me>",
  "artifact_path": "/var/lib/kai/reports/CVE-2025-12345_report.json",
  "signature_path": "/var/lib/kai/reports/CVE-2025-12345_report.json.sig",
  "status": "valid",
  "signer_identity": "Machine Kaisonai <machine-kaisonai@pm.me>",
  "signer_fingerprint": "ABC123DEF456789",
  "tamper_detected": false,
  "verified_at": "2026-02-02T12:01:00.123456"
}
```

**Response (200 OK) - TAMPER DETECTED**:
```json
{
  "success": false,
  "message": "TAMPER ALERT: Artifact signature verification failed",
  "artifact_path": "/var/lib/kai/reports/CVE-2025-12345_report.json",
  "signature_path": "/var/lib/kai/reports/CVE-2025-12345_report.json.sig",
  "status": "tampered",
  "signer_identity": "unknown",
  "signer_fingerprint": "unknown",
  "tamper_detected": true,
  "verified_at": "2026-02-02T12:02:00.123456",
  "alert": "TAMPER DETECTION: Artifact signature verification failed",
  "action": "EXECUTION HALTED"
}
```

**Response (200 OK) - Untrusted Signer**:
```json
{
  "success": false,
  "message": "WARNING: Signed by untrusted identity",
  "status": "untrusted",
  "signer_identity": "unknown-user@example.com",
  "signer_fingerprint": "UNKNOWN",
  "tamper_detected": false
}
```

---

### Chain of Custody

#### Get Chain of Custody

**Endpoint**: `GET /api/artifacts/chain-of-custody/{artifact_path}`

**Purpose**: Get complete signing and verification history for an artifact

**URL Parameters**:
- `artifact_path`: Path to the artifact file

**Response (200 OK)**:
```json
{
  "success": true,
  "artifact": "/var/lib/kai/reports/CVE-2025-12345_report.json",
  "chain": {
    "artifact": "/var/lib/kai/reports/CVE-2025-12345_report.json",
    "signatures": [
      {
        "signed_at": "2026-02-02T12:00:30.123456",
        "signer": "machine-kaisonai@pm.me",
        "fingerprint": "ABC123DEF456789",
        "artifact_hash": "a1b2c3d4e5f6g7h8..."
      }
    ],
    "verifications": [
      {
        "verified_at": "2026-02-02T12:01:00.123456",
        "status": "valid",
        "signer": "machine-kaisonai@pm.me",
        "tamper_detected": false
      },
      {
        "verified_at": "2026-02-02T13:00:00.123456",
        "status": "valid",
        "signer": "machine-kaisonai@pm.me",
        "tamper_detected": false
      }
    ],
    "chain_intact": true
  }
}
```

---

### Key Management

#### List Available Keys

**Endpoint**: `GET /api/artifacts/keys`

**Purpose**: List all imported PGP keys

**Response (200 OK)**:
```json
{
  "success": true,
  "total_keys": 4,
  "keys": [
    {
      "fingerprint": "ABC123DEF456789",
      "keyid": "ABC123DEF456789",
      "uids": ["Machine Kaisonai <machine-kaisonai@pm.me>"],
      "type": "sec",
      "length": "4096",
      "expires": "2028-02-02",
      "validity": "u"
    },
    {
      "fingerprint": "8F7E6D5C4B3A2F1E",
      "keyid": "8F7E6D5C4B3A2F1E",
      "uids": ["Admin Kaisonai <admin-kaisonai@pm.me>"],
      "type": "pub",
      "length": "4096",
      "expires": "2027-02-02",
      "validity": "u"
    }
  ]
}
```

---

### Audit & Diagnostics

#### Get Crypto System Status

**Endpoint**: `GET /api/artifacts/status`

**Purpose**: Get current crypto system health and diagnostics

**Response (200 OK)**:
```json
{
  "success": true,
  "status": {
    "gpg_home": "/home/user/.kai/gpg_home",
    "gpg_home_permissions": "700",
    "machine_identity": "machine-kaisonai@pm.me",
    "available_keys": 4,
    "signature_operations": 42,
    "verification_operations": 156,
    "trusted_identities": [
      "admin-kaisonai@pm.me",
      "user-kaisonai@pm.me",
      "infra-kaisonai@pm.me",
      "machine-kaisonai@pm.me"
    ]
  }
}
```

#### Get Audit Trail

**Endpoint**: `GET /api/artifacts/audit-trail`

**Query Parameters**:
- `limit` (optional, default=100): Number of events to return

**Response (200 OK)**:
```json
{
  "success": true,
  "total_operations": 42,
  "recent_operations": [
    {
      "timestamp": "2026-02-02T12:00:30.123456",
      "operation": "sign_artifact",
      "details": {
        "artifact": "CVE-2025-12345_report.json",
        "identity": "machine-kaisonai@pm.me",
        "hash": "a1b2c3d4e5f6g7h8..."
      }
    },
    {
      "timestamp": "2026-02-02T12:01:00.123456",
      "operation": "verify_artifact",
      "details": {
        "artifact": "CVE-2025-12345_report.json",
        "status": "valid",
        "tamper_detected": false,
        "signer": "machine-kaisonai@pm.me"
      }
    }
  ]
}
```

#### Get Signature Log

**Endpoint**: `GET /api/artifacts/signatures`

**Query Parameters**:
- `limit` (optional, default=100): Number of signatures to return

**Response (200 OK)**:
```json
{
  "success": true,
  "total_signatures": 42,
  "recent_signatures": [
    {
      "artifact": "/var/lib/kai/reports/CVE-2025-12345_report.json",
      "signed_at": "2026-02-02T12:00:30.123456",
      "signer": "machine-kaisonai@pm.me",
      "hash": "a1b2c3d4e5f6g7h8..."
    },
    {
      "artifact": "/var/lib/kai/reports/CVE-2025-54321_report.json",
      "signed_at": "2026-02-02T11:50:00.123456",
      "signer": "machine-kaisonai@pm.me",
      "hash": "z9y8x7w6v5u4t3s2..."
    }
  ]
}
```

#### Get Verification Log

**Endpoint**: `GET /api/artifacts/verifications`

**Query Parameters**:
- `limit` (optional, default=100): Number of verifications to return

**Response (200 OK)**:
```json
{
  "success": true,
  "total_verifications": 156,
  "recent_verifications": [
    {
      "artifact": "/var/lib/kai/reports/CVE-2025-12345_report.json",
      "verified_at": "2026-02-02T12:01:00.123456",
      "status": "valid",
      "tamper_detected": false,
      "signer": "machine-kaisonai@pm.me"
    },
    {
      "artifact": "/var/lib/kai/reports/CVE-2025-54321_report.json",
      "verified_at": "2026-02-02T12:00:45.123456",
      "status": "valid",
      "tamper_detected": false,
      "signer": "machine-kaisonai@pm.me"
    }
  ],
  "tamper_alerts": 0
}
```

---

### Dashboard

#### Get Crypto Dashboard Summary

**Endpoint**: `GET /api/artifacts/dashboard/summary`

**Purpose**: Get overall crypto system metrics and health

**Response (200 OK)**:
```json
{
  "success": true,
  "summary": {
    "total_signatures": 42,
    "total_verifications": 156,
    "verification_success_rate": 100.0,
    "tamper_alerts": 0,
    "alert_status": "NORMAL"
  },
  "timestamp": "2026-02-02T12:30:00.123456"
}
```

---

## Complete Workflow Example

### 1. Initialize System

```bash
curl -X POST http://localhost:8000/api/artifacts/init
```

### 2. Sign a Report

```bash
curl -X POST http://localhost:8000/api/artifacts/sign \
  -H "Content-Type: application/json" \
  -d '{
    "artifact_path": "/var/lib/kai/reports/CVE-2025-12345.json",
    "passphrase": "machine_passphrase"
  }'
```

### 3. Verify the Signature

```bash
curl -X POST http://localhost:8000/api/artifacts/verify \
  -H "Content-Type: application/json" \
  -d '{
    "artifact_path": "/var/lib/kai/reports/CVE-2025-12345.json",
    "signature_path": "/var/lib/kai/reports/CVE-2025-12345.json.sig"
  }'
```

### 4. Get Chain of Custody

```bash
curl -X GET "http://localhost:8000/api/artifacts/chain-of-custody//var/lib/kai/reports/CVE-2025-12345.json"
```

### 5. Check System Status

```bash
curl -X GET http://localhost:8000/api/artifacts/status
```

### 6. View Audit Trail

```bash
curl -X GET "http://localhost:8000/api/artifacts/audit-trail?limit=50"
```

### 7. Get Dashboard

```bash
curl -X GET http://localhost:8000/api/artifacts/dashboard/summary
```

---

## Python Integration Example

```python
import requests
import json

API_BASE = "http://localhost:8000/api/artifacts"

# 1. Initialize
response = requests.post(f"{API_BASE}/init")
print(f"Init: {response.json()['message']}")

# 2. Sign artifact
response = requests.post(
    f"{API_BASE}/sign",
    json={
        "artifact_path": "/var/lib/kai/reports/report.json",
        "passphrase": "passphrase"
    }
)
sig_record = response.json()["signature"]
print(f"Signed: {sig_record['signature_path']}")

# 3. Verify artifact
response = requests.post(
    f"{API_BASE}/verify",
    json={
        "artifact_path": "/var/lib/kai/reports/report.json",
        "signature_path": sig_record["signature_path"]
    }
)

if response.json()["tamper_detected"]:
    print("[X] TAMPER ALERT!")
    exit(1)
else:
    print(f"[OK] Verified by {response.json()['signer_identity']}")

# 4. Get chain of custody
response = requests.get(
    f"{API_BASE}/chain-of-custody//var/lib/kai/reports/report.json"
)
print(f"Chain intact: {response.json()['chain']['chain_intact']}")
```

---

## Error Handling

| Status Code | Error | Meaning |
|------------|-------|---------|
| 400 | Bad Request | Invalid parameters or missing artifact |
| 404 | Not Found | Artifact or signature file not found |
| 500 | Server Error | Crypto operation failed |

### Error Response Example

```json
{
  "detail": "Artifact not found: /path/to/nonexistent/file.json"
}
```

---

## Security Notes

1. **Passphrase Handling**: Pass via request body or environment variable, never in URL
2. **Tamper Detection**: Automatic execution halt on signature verification failure
3. **Key Import**: Only `machine-kaisonai@pm.me` private key imported locally
4. **Audit Trail**: All operations logged with timestamp and identity
5. **GPG Home Permissions**: Automatically set to `700` for security

---

For implementation details, see `BUILDING_AGENT_PROMPT.md` and `crypto_artifact_signing.py`.
