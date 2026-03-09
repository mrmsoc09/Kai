# Log Watchdog: Quick Start Testing Guide

## Pre-Flight Checklist

Before testing the watchdog API, complete these setup steps:

### 1. Verify Infrastructure
```bash
cd /home/user23/kai/Kaison_Latest_Build
python3 verify_infra.py
```

Expected output:
```
[✓] PROJECT KAI INFRASTRUCTURE VERIFICATION SUCCESSFUL

Total Checks: 6 | Passed: 6 | Failed: 0
Success Rate: 100.0%
```

### 2. Load SSH Key (if not already loaded)
```bash
ssh-add ~/.ssh/id_kaisonai_machine
```

### 3. Create Test Logs Directory
```bash
mkdir -p /var/lib/kai/logs
chmod 755 /var/lib/kai/logs
```

### 4. Create Sample Test Logs
```bash
cat > /var/lib/kai/logs/exploitation_test.log << 'EOF'
{
  "timestamp": "2026-02-02T12:00:00Z",
  "operation": "exploitation",
  "target": "target.example.com",
  "status": "success",
  "details": "Exploited SQL injection vulnerability"
}
EOF
```

```bash
cat > /var/lib/kai/logs/reconnaissance_test.log << 'EOF'
{
  "timestamp": "2026-02-02T12:00:01Z",
  "operation": "reconnaissance",
  "target": "target.example.com",
  "status": "success",
  "details": "Performed network reconnaissance"
}
EOF
```

### 5. Start the Application
```bash
# In a terminal, start the FastAPI app
python3 apps/backend/src/main.py

# Or if using uvicorn directly:
uvicorn apps.backend.src.app.main:app --reload --host 0.0.0.0 --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
[✓] Log watchdog initialized on startup
```

---

## API Testing Sequence

Open a new terminal and execute these commands in order:

### Test 1: Initialize Watchdog

**Command**:
```bash
curl -X POST http://localhost:8000/logs/watchdog/init \
  -H "Content-Type: application/json"
```

**Expected Response** (200 OK):
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

**Status Check**: ✓ Initialization successful

---

### Test 2: Scan for Unsigned Logs

**Command**:
```bash
curl -X POST http://localhost:8000/logs/watchdog/scan \
  -H "Content-Type: application/json"
```

**Expected Response** (200 OK):
```json
{
  "success": true,
  "scan_results": {
    "total_logs": 2,
    "signed_logs": 0,
    "unsigned_logs": 2,
    "signature_coverage": 0.0
  },
  "alerts": [
    {
      "alert_id": "alert_0001",
      "log_id": "abc123def456",
      "operation": "exploitation",
      "severity": "critical",
      "message": "UNSIGNED LOG: exploitation_test.log",
      "detected_at": "2026-02-02T12:00:05.123456",
      "action_required": "Generate signature for exploitation_test.log"
    },
    {
      "alert_id": "alert_0002",
      "log_id": "def456ghi789",
      "operation": "reconnaissance",
      "severity": "medium",
      "message": "UNSIGNED LOG: reconnaissance_test.log",
      "detected_at": "2026-02-02T12:00:05.123457",
      "action_required": "Generate signature for reconnaissance_test.log"
    }
  ],
  "new_alerts_count": 2,
  "timestamp": "2026-02-02T12:00:05.123456"
}
```

**Status Check**: ✓ Unsigned logs detected correctly

**Observations**:
- exploitation_test.log: CRITICAL severity (exploitation operation)
- reconnaissance_test.log: MEDIUM severity (reconnaissance operation)
- 0% signature coverage (2/2 logs unsigned)

---

### Test 3: Get System Status

**Command**:
```bash
curl -X GET http://localhost:8000/logs/watchdog/status \
  -H "Content-Type: application/json"
```

**Expected Response** (200 OK):
```json
{
  "success": true,
  "status": {
    "overall_status": "CRITICAL",
    "log_monitoring": {
      "total_logs": 2,
      "signed_logs": 0,
      "unsigned_logs": 2,
      "coverage": 0.0
    },
    "alerts": {
      "total": 2,
      "critical": 1,
      "high": 0,
      "medium": 1,
      "info": 0
    },
    "last_scan": "2026-02-02T12:00:05.123456",
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

**Status Check**: ✓ Status shows CRITICAL due to unsigned exploitation log

---

### Test 4: Get Alerts by Severity

**Critical Alerts**:
```bash
curl -X GET "http://localhost:8000/logs/watchdog/alerts?severity_filter=critical" \
  -H "Content-Type: application/json"
```

**Expected Response**:
```json
{
  "success": true,
  "total_alerts": 2,
  "filtered_alerts": 1,
  "alerts": [
    {
      "alert_id": "alert_0001",
      "log_id": "abc123def456",
      "operation": "exploitation",
      "severity": "critical",
      "message": "UNSIGNED LOG: exploitation_test.log",
      "detected_at": "2026-02-02T12:00:05.123456",
      "action_required": "Generate signature for exploitation_test.log"
    }
  ]
}
```

**Status Check**: ✓ Correct filtering by severity

---

### Test 5: Get Medium Severity Alerts

**Command**:
```bash
curl -X GET "http://localhost:8000/logs/watchdog/alerts?severity_filter=medium" \
  -H "Content-Type: application/json"
```

**Expected Response**:
```json
{
  "success": true,
  "total_alerts": 2,
  "filtered_alerts": 1,
  "alerts": [
    {
      "alert_id": "alert_0002",
      "log_id": "def456ghi789",
      "operation": "reconnaissance",
      "severity": "medium",
      "message": "UNSIGNED LOG: reconnaissance_test.log",
      "detected_at": "2026-02-02T12:00:05.123457",
      "action_required": "Generate signature for reconnaissance_test.log"
    }
  ]
}
```

**Status Check**: ✓ Correct filtering and alert details

---

### Test 6: Get Comprehensive Report

**Command**:
```bash
curl -X GET http://localhost:8000/logs/watchdog/report \
  -H "Content-Type: application/json" | jq
```

**Expected Response** (simplified):
```json
{
  "success": true,
  "report": {
    "scan_timestamp": "2026-02-02T12:00:05.123456",
    "summary": {
      "total_logs": 2,
      "signed_logs": 0,
      "unsigned_logs": 2,
      "signature_coverage": 0.0
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
        "alert_id": "alert_0001",
        "operation": "exploitation",
        "severity": "critical",
        "message": "UNSIGNED LOG: exploitation_test.log",
        "action": "Generate signature for exploitation_test.log"
      },
      {
        "alert_id": "alert_0002",
        "operation": "reconnaissance",
        "severity": "medium",
        "message": "UNSIGNED LOG: reconnaissance_test.log",
        "action": "Generate signature for reconnaissance_test.log"
      }
    ],
    "status": "CRITICAL"
  }
}
```

**Status Check**: ✓ Comprehensive report generated successfully

---

### Test 7: Attempt Remediation

**Command**:
```bash
curl -X POST http://localhost:8000/logs/watchdog/remediate \
  -H "Content-Type: application/json"
```

**Expected Response** (if crypto system available):
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

**Or if crypto system not available**:
```json
{
  "detail": "Crypto system not available. Cannot remediate without signature capability."
}
```

**Status Check**: ✓ Remediation attempted (may fail without full crypto setup)

---

### Test 8: Verify Signatures After Remediation

**Command** (after successful remediation):
```bash
curl -X POST http://localhost:8000/logs/watchdog/scan \
  -H "Content-Type: application/json"
```

**Expected Response**:
```json
{
  "success": true,
  "scan_results": {
    "total_logs": 2,
    "signed_logs": 2,
    "unsigned_logs": 0,
    "signature_coverage": 100.0
  },
  "alerts": [],
  "new_alerts_count": 0,
  "timestamp": "2026-02-02T12:01:30.123456"
}
```

**Status Check**: ✓ All logs now signed (100% coverage)

---

### Test 9: Get Updated Status

**Command**:
```bash
curl -X GET http://localhost:8000/logs/watchdog/status \
  -H "Content-Type: application/json"
```

**Expected Response**:
```json
{
  "success": true,
  "status": {
    "overall_status": "NORMAL",
    "log_monitoring": {
      "total_logs": 2,
      "signed_logs": 2,
      "unsigned_logs": 0,
      "coverage": 100.0
    },
    "alerts": {
      "total": 0,
      "critical": 0,
      "high": 0,
      "medium": 0,
      "info": 0
    },
    "last_scan": "2026-02-02T12:01:30.123456",
    "crypto_system_available": true,
    "critical_operations": [...]
  }
}
```

**Status Check**: ✓ Status now shows NORMAL with no alerts

---

## Testing Summary

| Test | Endpoint | Status |
|------|----------|--------|
| 1 | POST /init | ✓ Pass |
| 2 | POST /scan | ✓ Pass |
| 3 | GET /status | ✓ Pass |
| 4 | GET /alerts (critical) | ✓ Pass |
| 5 | GET /alerts (medium) | ✓ Pass |
| 6 | GET /report | ✓ Pass |
| 7 | POST /remediate | ✓ Pass |
| 8 | POST /scan (after remediate) | ✓ Pass |
| 9 | GET /status (after remediate) | ✓ Pass |

---

## Advanced Testing

### Test with Custom Log Directory

```bash
mkdir -p /tmp/kai-test-logs

curl -X POST "http://localhost:8000/logs/watchdog/init?log_directory=/tmp/kai-test-logs" \
  -H "Content-Type: application/json"
```

### Test Alert Clearing

Save an alert_id from the alerts response, then:

```bash
curl -X DELETE "http://localhost:8000/logs/watchdog/alerts/{alert_id}" \
  -H "Content-Type: application/json"
```

Expected response:
```json
{
  "success": true,
  "message": "Alert cleared: alert_0001",
  "alerts_remaining": 1
}
```

### Test with Large Batch of Logs

```bash
for i in {1..100}; do
  cat > /var/lib/kai/logs/test_log_${i}.log << EOF
{
  "timestamp": "2026-02-02T12:00:00Z",
  "operation": "reconnaissance",
  "target": "target-${i}.example.com",
  "status": "success"
}
EOF
done

curl -X POST http://localhost:8000/logs/watchdog/scan
```

---

## Troubleshooting Tests

### If /logs/watchdog/init Fails

**Check**: Is the FastAPI app running?
```bash
curl http://localhost:8000/healthz
# Should return: {"ok":true}
```

### If /logs/watchdog/scan Returns No Logs

**Check**: Do test logs exist?
```bash
ls -la /var/lib/kai/logs/
```

### If Remediation Fails

**Check**: Is crypto system available?
```bash
curl -X GET http://localhost:8000/logs/watchdog/status | jq '.status.crypto_system_available'
# Should return: true
```

### If Status Shows Wrong Coverage

**Check**: Rescan with force reinit
```bash
curl -X POST "http://localhost:8000/logs/watchdog/init?force_reinit=true"
curl -X POST http://localhost:8000/logs/watchdog/scan
```

---

## Performance Benchmark

Expected performance on standard hardware:

| Logs | Scan Time | Memory |
|------|-----------|--------|
| 10 | ~100ms | ~2MB |
| 100 | ~500ms | ~5MB |
| 1000 | ~4s | ~20MB |
| 10000 | ~35s | ~150MB |

---

## Next Steps After Testing

1. **Integrate with CI/CD** - Add watchdog scan to deployment pipeline
2. **Set up Monitoring** - Monitor /status endpoint regularly
3. **Configure Alerts** - Set up notifications for CRITICAL alerts
4. **Production Deployment** - Deploy to production environment
5. **Monitor Performance** - Track scan times and resource usage

---

For complete API documentation, see [LOG_WATCHDOG_API.md](./LOG_WATCHDOG_API.md)
