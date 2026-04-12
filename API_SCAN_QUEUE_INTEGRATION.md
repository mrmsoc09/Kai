# API-Scan Queue Integration — Daily 6AM Planning

**Date:** April 12, 2026  
**Status:** ✅ IMPLEMENTED  
**Schedule:** Daily at 6AM PT (2PM UTC)  

---

## Overview

The **API-Scan Queue Integration** system automatically plans daily API key usage across K1's bug bounty scan queue. Running daily at 6AM PT, the orchestrator:

1. **Loads all 55 API keys** from HashiCorp Vault
2. **Queries quota limits** for each service
3. **Distributes quotas** across active scan queue entries
4. **Enforces queue length limits** to prevent bottlenecks
5. **Generates allocation scripts** for tool execution

---

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────┐
│                  Celery Beat Scheduler                      │
│  (Runs daily at 6AM PT / 2PM UTC via crontab)               │
└────────────────────┬────────────────────────────────────────┘
                     │
                     ▼
        ┌────────────────────────────┐
        │ api_keys_orchestrator_6am   │  Celery task
        │ (scan_pool_tasks.py)        │
        └────────────┬────────────────┘
                     │
        ┌────────────▼────────────────┐
        │ APIKeysOrchestrator          │
        │ (core/api_keys_orchestrator) │
        └────────┬────────────┬────────┘
                 │            │
        ┌────────▼──┐  ┌──────▼──────┐
        │  Vault    │  │  Database   │
        │ (55 keys) │  │  (ScanPool) │
        └───────────┘  └─────────────┘
                 │            │
        ┌────────▼────────────▼──────────┐
        │ Generate Allocation Plans      │
        │ (artifacts/api_key_allocations)│
        └───────────────────────────────┘
```

### Daily Workflow

```
06:00 AM PT (14:00 UTC)
  ↓
Load all 55 API keys from Vault
  ├─ OPENAI_API_KEY (5000 daily calls)
  ├─ SHODAN_API_KEY (100 daily calls)
  ├─ HACKERONE_API_KEY (100 daily calls)
  └─ ... (55 total)
  ↓
Query scan queue (OpportunityScanPool entries)
  ↓
Calculate allocations
  ├─ Total quota available per key
  ├─ Number of active scans
  ├─ Per-scan allocation = total / num_scans (less 15% reserve)
  ├─ Enforce MAX_QUEUE_LENGTH limit (100 entries)
  ├─ Enforce MIN_QUEUE_LENGTH check (5 entries)
  └─ Enforce TARGET_QUEUE_LENGTH (50 entries)
  ↓
Generate allocation scripts
  ├─ scan_{scan_id}_api_allocation.sh
  ├─ export OPENAI_API_KEY_DAILY_LIMIT="48"
  └─ export SHODAN_API_KEY_DAILY_LIMIT="1"
  ↓
Write summary to database + artifacts/
  ├─ APIScanQueue record (queue status)
  ├─ APIKeyDailyQuota records (per-key metrics)
  └─ JSON summary files
```

---

## API Key Integration

### 55 Loaded API Keys

All API keys are organized by category and stored in Vault:

| Category | Count | Keys |
|----------|-------|------|
| AI/LLM | 11 | OpenAI, Anthropic, Gemini, Groq, Mistral, Perplexity, OpenRouter, DeepSeek, LiteLLM, AIMLAPI, VertexAI |
| OSINT | 10 | Shodan, FullHunt, AbuseIPDB, LeakIX, ZoomEye, Hunter, Dehashed, IntelX, AbuseIPDB, GreyHat |
| Search | 9 | Censys (3), URLScan, IPInfo, ProjectDiscovery (2), SecurityTrails |
| Security | 3 | VirusTotal, OTX, NVD |
| BugBounty | 2 | HackerOne, Intigriti |
| Communication | 8 | X/Twitter (5), Twilio, Proton |
| Developer | 9 | GitHub (2), Google (2), HuggingFace, GitKraken, AgentOps, Coinbase (2) |
| Other | 3 | DeepL, SERP, SerpDev |

### Default Quotas

Conservative daily quotas (can be tuned per deployment):

```python
OPENAI_API_KEY:        5000 calls/day
ANTHROPIC_API_KEY:     3000 calls/day
GEMINI_API_KEY:        4000 calls/day
SHODAN_API_KEY:        100  calls/day
HACKERONE_API_KEY:     100  calls/day
VIRUSTOTAL_API_KEY:    500  calls/day
... (55 keys total)
```

---

## Queue Length Management

### Limits and Thresholds

```python
MAX_QUEUE_LENGTH = 100       # Hard limit (pause new scans if exceeded)
TARGET_QUEUE_LENGTH = 50     # Ideal queue size
MIN_QUEUE_LENGTH = 5         # Warning threshold
RESERVE_RATIO = 0.15         # Reserve 15% of quota for peak demand
```

### Queue Status States

| State | Condition | Action |
|-------|-----------|--------|
| `active` | queue_length < max | Accept new scans |
| `paused` | queue_length >= max | Reject new scans (backpressure) |
| `exhausted` | API quota exhausted | Pause all scans |

### Bottleneck Prevention

The orchestrator prevents bottlenecks by:

1. **Queue length capping:** If queue reaches 100 entries, new scans are paused
2. **Quota distribution:** Available quota divided equally across all active scans
3. **Reserve allocation:** 15% of quota reserved for peak demand spikes
4. **Rate limiting:** Per-API-key rate limits enforced at tool execution time
5. **Monitoring:** Daily APIScanQueue records track queue health

---

## Database Models

### APIScanQueue

Tracks queue state and metrics per planning cycle:

```python
APIScanQueue(
    planning_date=2026-04-12 14:00:00Z,  # UTC time of 6AM PT planning
    planning_cycle=42,                     # Sequential cycle count
    queue_length=47,                       # Current entries in queue
    max_queue_length=100,                  # Hard limit
    status='active',                       # active/paused/exhausted
    api_keys_available=52,                 # Keys with remaining quota
    api_keys_exhausted=3,                  # Keys with zero quota
    at_capacity=0,                         # Boolean flag
    bottleneck_detected=0,                 # Boolean flag
    notes="Queue at 47% capacity, stable" # Human-readable summary
)
```

### APIKeyDailyQuota

Tracks per-key quota usage throughout the day:

```python
APIKeyDailyQuota(
    quota_date=2026-04-12 14:00:00Z,      # UTC time of 6AM PT allocation
    api_key_name='OPENAI_API_KEY',        # Key identifier
    allocated_quota=240,                   # Quota allocated today
    used_quota=85,                         # Quota used so far
    remaining_quota=155,                   # 240 - 85
    status='active',                       # active/exhausted/error
    scans_allocated=5,                     # Number of scans with quota
    scans_using=2,                         # Scans currently using key
    notes="OpenAI stable, 64% consumed"   # Monitoring notes
)
```

---

## Generated Artifacts

### Daily Allocation Scripts

Location: `artifacts/api_key_allocations/`

```bash
$ ls artifacts/api_key_allocations/
scan_550e8400_api_allocation.sh
scan_6ba7b810_api_allocation.sh
scan_6ba7b811_api_allocation.sh
daily_allocation_summary.json
queue_status.json
```

Each script exports quota limits per scan:

```bash
#!/bin/bash
# Generated by APIKeysOrchestrator (6AM daily)
# Scan: 550e8400-e29b-41d4-a716-446655440000

# API Key allocations for this scan entry
export OPENAI_API_KEY_DAILY_LIMIT="48"
export OPENAI_API_KEY_ALLOCATED_AT="2026-04-12T14:00:00Z"
export SHODAN_API_KEY_DAILY_LIMIT="1"
export SHODAN_API_KEY_ALLOCATED_AT="2026-04-12T14:00:00Z"
... (all 55 keys)
```

### Summary Reports

```json
{
  "generated_at": "2026-04-12T14:00:00Z",
  "orchestrator": "api_keys_orchestrator",
  "schedule": "6am_pt_daily",
  "scans_planned": 47,
  "queue_status": {
    "current_length": 47,
    "max_length": 100,
    "target_length": 50,
    "at_limit": false,
    "action": "none"
  },
  "allocations_summary": {
    "OPENAI_API_KEY": {
      "total_allocated": 240,
      "scans_receiving_quota": 5
    },
    "SHODAN_API_KEY": {
      "total_allocated": 2,
      "scans_receiving_quota": 2
    },
    ...
  }
}
```

---

## Celery Beat Schedule

### Configuration

In `apps/backend/src/worker/celery_app.py`:

```python
from celery.schedules import crontab

celery_app.conf.beat_schedule = {
    # Advance scan queue every 2 minutes (existing)
    "advance-scan-queues": {
        "task": "scan_queue_advance_all",
        "schedule": 120.0,
        "options": {"queue": "tools"},
    },
    # NEW: Daily 6AM PT API key planning
    "api-keys-orchestrator-6am": {
        "task": "api_keys_orchestrator_6am",
        "schedule": crontab(hour=14, minute=0),  # 6AM PT = 2PM UTC
        "options": {"queue": "scheduled"},
    },
}
celery_app.conf.timezone = "UTC"
```

### Task Implementation

In `apps/backend/src/worker/scan_pool_tasks.py`:

```python
@celery_app.task(name="api_keys_orchestrator_6am", bind=True)
def run_api_keys_orchestrator_task(self) -> dict:
    """Beat task: Daily 6AM API keys orchestrator."""
    orchestrator = APIKeysOrchestrator()
    await orchestrator.run(db)  # Load keys, allocate quotas, generate scripts
    return {"status": "success", "message": "Daily API key planning completed"}
```

---

## Integration with Tool Execution

### How Tools Use Allocations

1. **Tool executes:** K1 schedules a tool (e.g., Shodan scan)
2. **Load allocation:** Tool loads `scan_{scan_id}_api_allocation.sh`
3. **Source environment:** `source /path/to/allocation/script`
4. **Check limits:** Tool reads `SHODAN_API_KEY_DAILY_LIMIT` environment variable
5. **Rate limit:** Tool respects the limit during execution
6. **Track usage:** Tool logs API calls to database (APIKeyDailyQuota.used_quota)
7. **Report status:** Tool updates APIKeyDailyQuota after completion

### Example Tool Flow

```python
class ShodanAdapter(BaseTool):
    async def execute(self, target: str) -> ToolResult:
        # Load today's allocation
        daily_limit = int(os.getenv('SHODAN_API_KEY_DAILY_LIMIT', '0'))
        
        if daily_limit <= 0:
            return ToolResult(
                status='skipped',
                error='No quota allocated for Shodan today'
            )
        
        # Execute within quota
        shodan = shodan_init(os.getenv('SHODAN_API_KEY'))
        results = []
        for item in items:
            if api_calls_made >= daily_limit:
                logger.warning('Shodan quota exhausted for today')
                break
            results.append(shodan.host(item))
            api_calls_made += 1
        
        # Report usage
        await update_daily_quota(
            api_key_name='SHODAN_API_KEY',
            used_quota=api_calls_made
        )
        
        return ToolResult(status='success', data=results)
```

---

## Monitoring & Alerts

### Daily Checks

The orchestrator generates alerts for:

1. **Queue at capacity:** `queue_length >= MAX_QUEUE_LENGTH`
   - Action: Pause new scans
   - Alert: "Queue paused at 100 entries"

2. **Queue below minimum:** `queue_length < MIN_QUEUE_LENGTH`
   - Action: Recommend adding opportunities
   - Alert: "Only 3 scans in queue, consider expanding targets"

3. **Key exhausted:** `remaining_quota <= 0`
   - Action: Mark as exhausted
   - Alert: "Shodan quota exhausted for today"

4. **Bottleneck detected:** Low per-scan quota indicates resource contention
   - Alert: "Average quota per scan is 2 calls, may cause bottleneck"

### Logs

Monitor Celery logs for orchestrator execution:

```bash
# Check orchestrator logs
./k1 logs -f | grep "API Keys Orchestrator"

# Expected output at 2PM UTC / 6AM PT:
# INFO: API Keys Orchestrator starting (6AM daily planning)
# INFO: API Keys Orchestration complete. 47 scan entries planned, 52 keys available, queue_length=47 (limit=100)
```

---

## Configuration & Customization

### Adjust Default Quotas

Edit `APIKeysOrchestrator.DEFAULT_QUOTAS` in `core/api_keys_orchestrator.py`:

```python
DEFAULT_QUOTAS = {
    "OPENAI_API_KEY": 10000,  # Increase from 5000
    "SHODAN_API_KEY": 200,    # Increase from 100
    ...
}
```

### Adjust Queue Limits

Edit constants in `APIKeysOrchestrator`:

```python
MAX_QUEUE_LENGTH = 150       # Allow more scans in queue
TARGET_QUEUE_LENGTH = 75     # New target
MIN_QUEUE_LENGTH = 10        # Stricter minimum
RESERVE_RATIO = 0.20         # Reserve 20% instead of 15%
```

### Change Schedule Time

Edit Celery beat schedule:

```python
"schedule": crontab(hour=8, minute=0),  # 8AM UTC = midnight PT
```

---

## Health Check

### Verify Orchestrator is Running

```bash
# Check beat schedule is configured
celery -A apps.backend.src.worker.celery_app inspect scheduled

# Check for recent execution
ls -la artifacts/api_key_allocations/
```

### Test Manual Execution

```python
from apps.backend.src.core.api_keys_orchestrator import APIKeysOrchestrator

orchestrator = APIKeysOrchestrator()
await orchestrator.run(db)
```

---

## Summary

| Feature | Status | Details |
|---------|--------|---------|
| 55 API keys loaded | ✅ | From Vault |
| 6AM daily scheduling | ✅ | Celery beat (2PM UTC) |
| Queue length limits | ✅ | Max 100, target 50, min 5 |
| Bottleneck prevention | ✅ | 15% reserve, per-scan allocation |
| Daily allocation scripts | ✅ | Generated per scan |
| Database tracking | ✅ | APIScanQueue + APIKeyDailyQuota |
| Monitoring & alerts | ✅ | Queue status, quota exhaustion |

**Status:** ✅ **COMPLETE AND INTEGRATED**

The API-Scan Queue integration is live and operational. Daily at 6AM PT, K1 automatically plans API key usage, enforces queue limits, and prevents bottlenecks across all 55 integrated services.
