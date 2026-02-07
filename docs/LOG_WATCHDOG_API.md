# Log Watchdog API Reference

## Overview

The Log Watchdog API monitors hunting logs for missing or invalid PGP signatures, ensuring cryptographic chain of custody for all Project Kai operations. The watchdog automatically detects unsigned logs and alerts on critical operations.

**Base URL**: `http://localhost:8000/logs/watchdog`

**Authentication**: Requires ROLE_OPERATOR authentication

---

## Endpoints

### Initialization

#### Initialize Log Watchdog

**Endpoint**: `POST /logs/watchdog/init`

**Purpose**: Initialize the log watchdog system and configure monitoring

**Query Parameters**:
- `log_directory` (optional, default: `/var/lib/kai/logs`): Directory containing hunting logs
- `crypto_system_available` (optional, default: `true`): Enable cryptographic signature verification

**Response (200 OK)**:
```json
{
  "success": true,
  "message": "Log watchdog initialized",
  "config": {
    "log_directory": "/var/lib/kai/logs",
    "critical_operations": [
      "exploitation",
      "payload_execution",
      "remote_code_execution",
      "privilege_escalation"
    ],
    "crypto_system_available": true,
    "timestamp": "2026-02-02T12:00:00.000000"
  }
}
```

---

### Log Scanning

#### Scan for Unsigned Logs

**Endpoint**: `POST /logs/watchdog/scan`

**Purpose**: Scan log directory and detect unsigned or invalid signature entries

**Response (200 OK)**:
```json
{
  "success": true,
  "scan_results": {
    "total_logs": 42,
    "signed_logs": 40,
    "unsigned_logs": 2,
    "signature_coverage": 95.238
  },
  "alerts": [
    {
      "alert_id": "alert_2026020212000",
      "log_id": "log_cve_2025_001",
      "operation": "exploitation",
      "severity": "critical",
      "message": "UNSIGNED LOG: exploitation_attempt_2026.log",
      "detected_at": "2026-02-02T12:00:05.123456",
      "action_required": "Generate signature for exploitation_attempt_2026.log"
    },
    {
      "alert_id": "alert_2026020212001",
      "log_id": "log_recon_001",
      "operation": "reconnaissance",
      "severity": "medium",
      "message": "UNSIGNED LOG: recon_scan_2026.log",
      "detected_at": "2026-02-02T12:00:10.123456",
      "action_required": "Generate signature for recon_scan_2026.log"
    }
  ],
  "new_alerts_count": 2,
  "timestamp": "2026-02-02T12:00:15.123456"
}
```

**Error Response (500 Server Error)**:
```json
{
  "detail": "Scan failed: [error description]"
}
```

---

### Reports

#### Get Comprehensive Report

**Endpoint**: `GET /logs/watchdog/report`

**Purpose**: Get detailed watchdog report with all statistics and alert breakdown

**Response (200 OK)**:
```json
{
  "success": true,
  "report": {
    "scan_timestamp": "2026-02-02T12:00:15.123456",
    "summary": {
      "total_logs": 42,
      "signed_logs": 40,
      "unsigned_logs": 2,
      "signature_coverage": 95.238
    },
    "alerts": {
      "total": 2,
      "critical": 1,
      "high": 0,
      "medium": 1,
      "info": 0
    },
    "alert_details": [
      {
        "alert_id": "alert_2026020212000",
        "operation": "exploitation",
        "severity": "critical",
        "message": "UNSIGNED LOG: exploitation_attempt_2026.log",
        "action": "Generate signature for exploitation_attempt_2026.log"
      }
    ],
    "status": "CRITICAL"
  }
}
```

---

### Remediation

#### Attempt to Sign Unsigned Logs

**Endpoint**: `POST /logs/watchdog/remediate`

**Purpose**: Automatically sign unsigned critical and high-severity logs

**Response (200 OK)**:
```json
{
  "success": true,
  "remediation_results": {
    "unsigned": 2,
    "signed": 2,
    "failed": 0
  },
  "timestamp": "2026-02-02T12:01:00.123456"
}
```

**Error Response (400 Bad Request)**:
```json
{
  "detail": "Crypto system not available. Cannot remediate without signature capability."
}
```

---

### Alert Management

#### Get Current Alerts

**Endpoint**: `GET /logs/watchdog/alerts`

**Query Parameters**:
- `severity_filter` (optional): Filter by severity (`critical`, `high`, `medium`, `info`)
- `limit` (optional, default: 100, max: 1000): Maximum alerts to return

**Response (200 OK)**:
```json
{
  "success": true,
  "total_alerts": 42,
  "filtered_alerts": 2,
  "alerts": [
    {
      "alert_id": "alert_2026020212000",
      "log_id": "log_cve_2025_001",
      "operation": "exploitation",
      "severity": "critical",
      "message": "UNSIGNED LOG: exploitation_attempt_2026.log",
      "detected_at": "2026-02-02T12:00:05.123456",
      "action_required": "Generate signature for exploitation_attempt_2026.log"
    }
  ]
}
```

**Example: Filter by severity**:
```bash
curl "http://localhost:8000/logs/watchdog/alerts?severity_filter=critical&limit=50"
```

---

#### Clear Specific Alert

**Endpoint**: `DELETE /logs/watchdog/alerts/{alert_id}`

**Purpose**: Acknowledge/clear a specific alert from the system

**Response (200 OK)**:
```json
{
  "success": true,
  "message": "Alert cleared: alert_2026020212000",
  "alerts_remaining": 41
}
```

**Error Response (404 Not Found)**:
```json
{
  "detail": "Alert not found: alert_2026020212000"
}
```

---

### System Status

#### Get Watchdog Status

**Endpoint**: `GET /logs/watchdog/status`

**Purpose**: Get current watchdog system status and health metrics

**Response (200 OK)**:
```json
{
  "success": true,
  "status": {
    "overall_status": "CRITICAL",
    "log_monitoring": {
      "total_logs": 42,
      "signed_logs": 40,
      "unsigned_logs": 2,
      "coverage": 95.238
    },
    "alerts": {
      "total": 2,
      "critical": 1,
      "high": 0,
      "medium": 1,
      "info": 0
    },
    "last_scan": "2026-02-02T12:00:15.123456",
    "crypto_system_available": true,
    "critical_operations": [
      "exploitation",
      "payload_execution",
      "remote_code_execution",
      "privilege_escalation"
    ]
  }
}
```

**Status Values**:
- `CRITICAL`: One or more critical-severity alerts
- `WARNING`: High-severity or medium-severity alerts (no critical)
- `NORMAL`: No alerts or only info-level alerts

---

### Configuration

#### Set Crypto System

**Endpoint**: `POST /logs/watchdog/set-crypto-system`

**Purpose**: Configure the crypto system for signature verification (called by application startup)

**Request**:
```json
{
  "crypto_system": "<CryptoSystem instance>"
}
```

**Response (200 OK)**:
```json
{
  "success": true,
  "message": "Crypto system configured",
  "crypto_system_available": true
}
```

---

## Alert Severity Levels

### CRITICAL
Applied to unsigned or invalid logs from operations:
- `exploitation`
- `payload_execution`
- `remote_code_execution`
- `privilege_escalation`

**Action**: Immediate investigation and signature required

### HIGH
Applied to unsigned logs from operations:
- `analysis`
- `reporting`

**Action**: Review and signature within standard timeframe

### MEDIUM
Applied to unsigned logs from operations:
- `reconnaissance`

**Action**: Sign when practical

### INFO
Applied to unsigned logs from all other operations

**Action**: Informational, no immediate action required

---

## Complete Workflow Example

### 1. Initialize Watchdog

```bash
curl -X POST "http://localhost:8000/logs/watchdog/init"
```

### 2. Scan for Unsigned Logs

```bash
curl -X POST "http://localhost:8000/logs/watchdog/scan"
```

### 3. Check Status

```bash
curl -X GET "http://localhost:8000/logs/watchdog/status"
```

### 4. View Alerts by Severity

```bash
curl -X GET "http://localhost:8000/logs/watchdog/alerts?severity_filter=critical"
```

### 5. Remediate Unsigned Logs

```bash
curl -X POST "http://localhost:8000/logs/watchdog/remediate"
```

### 6. Clear an Alert (after remediation)

```bash
curl -X DELETE "http://localhost:8000/logs/watchdog/alerts/{alert_id}"
```

### 7. Generate Full Report

```bash
curl -X GET "http://localhost:8000/logs/watchdog/report"
```

---

## Python Integration Example

```python
import httpx
import json

API_BASE = "http://localhost:8000/logs/watchdog"

async def monitor_logs():
    async with httpx.AsyncClient() as client:
        # 1. Initialize
        init_resp = await client.post(f"{API_BASE}/init")
        print(f"Init: {init_resp.json()['message']}")

        # 2. Scan
        scan_resp = await client.post(f"{API_BASE}/scan")
        scan_data = scan_resp.json()
        print(f"Unsigned logs: {scan_data['scan_results']['unsigned_logs']}")

        # 3. Check for critical alerts
        alerts_resp = await client.get(
            f"{API_BASE}/alerts?severity_filter=critical"
        )
        critical_alerts = alerts_resp.json()['alerts']

        if critical_alerts:
            print(f"[!] Found {len(critical_alerts)} critical alerts!")

            # 4. Attempt remediation
            remediate_resp = await client.post(f"{API_BASE}/remediate")
            remediation = remediate_resp.json()['remediation_results']
            print(f"Signed {remediation['signed']} logs")

        # 5. Get full report
        report_resp = await client.get(f"{API_BASE}/report")
        report = report_resp.json()['report']
        print(f"\nFinal Status: {report['status']}")
        print(f"Coverage: {report['summary']['signature_coverage']:.1f}%")

# Run the monitor
import asyncio
asyncio.run(monitor_logs())
```

---

## Integration with Artifact Signing API

The Log Watchdog integrates seamlessly with the Artifact Signing API:

1. **Signature Verification**: Uses the crypto_system from the Artifact Signing module
2. **Chain of Custody**: Watchdog tracks complete signing/verification history
3. **Automated Remediation**: Can trigger artifact signing for unsigned logs

**Integration example**:

```python
from apps.backend.src.core.crypto_artifact_signing import CryptoSystem
from apps.backend.src.routers.watchdog import set_crypto_system

# Initialize crypto system
crypto = CryptoSystem()
await crypto.initialize()

# Configure watchdog with crypto system
await set_crypto_system(crypto_system=crypto)

# Now watchdog can verify signatures
watchdog.crypto_system = crypto
total, signed, alerts = await watchdog.scan_logs()
```

---

## Error Handling

| Status Code | Error | Meaning |
|-------------|-------|---------|
| 200 | OK | Successful operation |
| 400 | Bad Request | Invalid parameters or missing crypto system |
| 404 | Not Found | Alert or log not found |
| 500 | Server Error | Scan, verification, or remediation failed |

### Error Response Format

```json
{
  "detail": "Error description here"
}
```

---

## Security Notes

1. **Authentication**: All endpoints require ROLE_OPERATOR authentication
2. **Audit Trail**: All watchdog operations are logged
3. **Signature Verification**: Uses PGP keys from ~/.kai/gpg_home
4. **Crypto System**: Requires integration with initialized CryptoSystem instance
5. **Alert Clearing**: Clears alert from system but doesn't resolve underlying signature issue

---

## Performance Considerations

- **Scan Time**: Depends on number of logs. Typical: ~50ms per log file
- **Memory**: Stores all logs and signatures in memory during scan
- **API Responses**: All operations are async and non-blocking
- **Large Directories**: For >10,000 logs, consider filtering by timestamp

---

## Related Documentation

- [Artifact Signing & Chain of Custody API](./API_ARTIFACT_SIGNING.md)
- [Log Watchdog Implementation](../apps/backend/src/core/log_watchdog.py)
- [Infrastructure Verification Script](../verify_infra.py)
- [Security-First Builder Prompt](./BUILDING_AGENT_PROMPT.md)

---

For implementation questions, refer to the inline documentation in `log_watchdog.py` and `watchdog.py` router.
