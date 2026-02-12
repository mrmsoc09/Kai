# Vulnerability Repair Pipeline Integration

## Overview

The Vulnerability Repair Pipeline provides an end-to-end automated workflow for discovering, analyzing, repairing, and validating security vulnerabilities with intelligent cost optimization.

**Status**: ✅ Integrated (v7.6+)

## Architecture

### Workflow Phases

```
Discovery → Analysis → Repair → Validation → Report
   (Local)  (Hybrid)  (Paid API) (Local)    (Generated)
   $0        $0-$1     $0.30-$0.50 $0       $0
```

### Phase Details

1. **Discovery** (OSINTAgent + Local Models)
   - Uses local Ollama models exclusively
   - No API costs ($0)
   - Discovers vulnerabilities via automated scanning
   - Complexity: 1-4 (trivial to basic)

2. **Analysis** (ReasoningAgent + Hybrid)
   - Simple findings (complexity < 7): Local models ($0)
   - Complex findings (complexity ≥ 7): Paid APIs ($0.15-$0.50)
   - Deep analysis, false positive filtering
   - CVSS scoring and prioritization

3. **Repair** (RepairAgent + Codex/Claude Code)
   - Generates secure fix code using Codex API
   - Applies fixes via Claude Code CLI (if auto_repair=True)
   - Cost: ~$0.30 per fix
   - Creates before/after code snapshots

4. **Validation** (FixValidator + Local)
   - Multi-layer validation (static analysis, LLM review, tests)
   - Uses local models only ($0)
   - Confidence scoring (0.0-1.0)
   - OWASP best practices checks

5. **Report Generation**
   - Comprehensive post-review report
   - Before/after code diffs
   - Cost breakdown by phase
   - Rollback instructions
   - Next steps recommendations

## API Endpoints

### Execute Pipeline

```bash
POST /findings/repair/discover-and-repair
```

**Payload**:
```json
{
  "target": "example.com",
  "auto_repair": true,
  "session_id": "optional-session-id"
}
```

**Response**:
```json
{
  "ok": true,
  "target": "example.com",
  "vulnerabilities_found": 5,
  "repairs_generated": 5,
  "repairs_applied": 4,
  "total_cost_cents": 150,
  "total_cost_usd": 1.50,
  "local_percentage": 70.0,
  "paid_percentage": 30.0,
  "execution_time_ms": 45231,
  "post_review_report": { ... },
  "timestamp": "2025-01-15T10:30:00Z"
}
```

### Health Check

```bash
GET /findings/repair/health
```

**Response**:
```json
{
  "ok": true,
  "repair_pipeline_available": true,
  "cli_tools": {
    "claude_code": true,
    "codex": true,
    "gemini": false
  },
  "specialized_agents": {
    "osint_agent": true,
    "reasoning_agent": true,
    "repair_agent": true
  }
}
```

## Frontend Integration

### Components

**RepairPipelinePanel** (`apps/frontend/src/components/repair/RepairPipelinePanel.tsx`)
- Full-featured React dashboard
- Real-time pipeline execution
- Cost breakdown visualization
- Before/after code diff view
- Validation results display

**Usage**:
```tsx
import { RepairPipelinePanel } from '@/components/repair';

<RepairPipelinePanel defaultTarget="example.com" />
```

### API Client

**repair.ts** (`apps/frontend/src/api/repair.ts`)
```typescript
import { discoverAndRepair, getRepairPipelineHealth } from '@/api/repair';

// Execute pipeline
const result = await discoverAndRepair(
  'example.com',
  true,  // auto_repair
  'session-123'  // optional session_id
);

// Check health
const health = await getRepairPipelineHealth();
```

## Cost Optimization

### Budget Integration

The repair pipeline is fully integrated with the budget tracking system:

- **Session Budget**: Each session has a $10 default limit
- **Daily Budget**: Platform-wide $100 daily limit
- **Alert Thresholds**: 80% warning, 95% critical
- **Automatic Fallback**: When budget exceeded, uses local models only

### Cost Breakdown

Typical repair pipeline execution for 5 vulnerabilities:

| Phase | Model | Cost |
|-------|-------|------|
| Discovery | Ollama (local) | $0.00 |
| Analysis (3 simple) | Ollama (local) | $0.00 |
| Analysis (2 complex) | Claude 3.5 Sonnet | $0.30 |
| Repair (5 fixes) | Codex | $1.50 |
| Validation | Ollama (local) | $0.00 |
| **Total** | | **$1.80** |

**Savings**: 65-75% vs all-paid-API approach ($5-7)

## CLI Tools

### Required Tools

1. **Claude Code** (Code analysis and repair)
   - Install: `npm install -g @anthropic-ai/claude-code`
   - Verify: `claude-code --version`

2. **Codex** (OpenAI API for fix generation)
   - Requires: `OPENAI_API_KEY` environment variable
   - No CLI installation needed

3. **Gemini CLI** (Optional, long-context analysis)
   - Install: Follow Google AI CLI setup
   - Verify: `gemini-cli --version`

### Initialization

CLI tools are initialized on platform startup. Check logs:

```bash
[✓] Claude Code CLI initialized
[✓] Codex (OpenAI) initialized
[!] Gemini not available (install CLI or set GOOGLE_API_KEY)
[✓] CLI Tools initialized: 2/3 available
[✓] Vulnerability Repair Pipeline initialized
```

## Configuration

### Environment Variables

```bash
# Budget Limits
KAI_SESSION_BUDGET_CENTS=1000  # $10 per session
KAI_DAILY_BUDGET_CENTS=10000   # $100 per day

# API Keys
OPENAI_API_KEY=sk-...          # Required for Codex
ANTHROPIC_API_KEY=sk-ant-...   # Required for Claude
GOOGLE_API_KEY=...             # Optional for Gemini

# Repair Pipeline Settings
REPAIR_AUTO_APPLY=true         # Auto-apply fixes (default: true)
```

### Auto-Repair Behavior

**When `auto_repair=True` (default)**:
- Fixes are automatically applied to codebase
- Full post-review report generated
- Rollback instructions included
- Git changes recommended for review

**When `auto_repair=False`**:
- Fixes are generated but not applied
- Report includes proposed changes only
- User reviews and manually applies fixes

## Post-Review Report

### Report Structure

```json
{
  "header": "[AI-GENERATED CODE CHANGES: AUTO-APPLIED WITH POST-REVIEW]",
  "timestamp": "2025-01-15T10:30:00Z",
  "target": "example.com",
  "summary": {
    "vulnerabilities_found": 5,
    "repairs_applied": 4,
    "total_cost_usd": 1.80,
    "local_model_usage": 70.0,
    "paid_api_usage": 30.0
  },
  "changes": [
    {
      "file": "login.php",
      "vulnerability": "SQL Injection",
      "severity": "high",
      "before_code": "...",
      "after_code": "...",
      "validation": {
        "is_valid": true,
        "confidence": 0.95,
        "issues": []
      },
      "rollback_command": "git checkout login.php"
    }
  ],
  "cost_breakdown": {
    "discovery_cost": 0.0,
    "analysis_cost": 0.3,
    "repair_cost": 1.5,
    "validation_cost": 0.0
  },
  "next_steps": [
    "Review all changes in git diff",
    "Run full test suite to verify fixes",
    "Deploy to staging environment",
    "Monitor for any regressions"
  ]
}
```

## Integration Points

### Backend Initialization

**main.py startup sequence**:
```python
# Initialize Repair Pipeline
try:
    from ..core.repair_pipeline import get_repair_pipeline
    pipeline = get_repair_pipeline()
    print("[✓] Vulnerability Repair Pipeline initialized")
except Exception as e:
    print(f"[!] Repair Pipeline startup error: {str(e)}")
```

### Router Integration

**findings.py endpoints**:
- `POST /findings/repair/discover-and-repair` - Execute pipeline
- `GET /findings/repair/health` - Health check

### Dashboard Integration

**Dashboard.tsx tabs**:
- New "🔧 Repair Pipeline" tab added to navigation
- Full-featured panel with execution controls
- Real-time progress and results display
- Cost tracking and breakdown

## Usage Examples

### Example 1: Quick Vulnerability Scan and Repair

```typescript
// Frontend
const result = await discoverAndRepair('staging.example.com', true);

console.log(`Found ${result.vulnerabilities_found} vulnerabilities`);
console.log(`Applied ${result.repairs_applied} fixes`);
console.log(`Total cost: $${result.total_cost_usd.toFixed(2)}`);
console.log(`Savings: ${result.local_percentage.toFixed(1)}% local`);
```

### Example 2: Generate Fixes Without Auto-Apply

```bash
curl -X POST http://localhost:8000/findings/repair/discover-and-repair \
  -H "Content-Type: application/json" \
  -d '{
    "target": "example.com",
    "auto_repair": false,
    "session_id": "manual-review-session"
  }'
```

### Example 3: Check Health Before Execution

```typescript
// Check if CLI tools are available
const health = await getRepairPipelineHealth();

if (!health.cli_tools.codex) {
  alert('Codex not available. Set OPENAI_API_KEY to enable repairs.');
  return;
}

if (!health.cli_tools.claude_code) {
  alert('Claude Code not installed. Auto-apply will be disabled.');
}

// Proceed with pipeline execution
const result = await discoverAndRepair(target, health.cli_tools.claude_code);
```

## Troubleshooting

### Common Issues

**1. "Repair pipeline not available"**
- Check backend logs for initialization errors
- Verify specialized agents are loaded
- Ensure budget tracker is initialized

**2. "Codex not available"**
- Set `OPENAI_API_KEY` environment variable
- Restart backend server
- Verify API key is valid

**3. "Claude Code CLI not found"**
- Install: `npm install -g @anthropic-ai/claude-code`
- Verify PATH includes npm global bin directory
- Auto-apply will be disabled, but analysis/repair still works

**4. "Budget exhausted"**
- Check daily budget usage: `GET /api/v1/budget/daily`
- Request emergency increase: `POST /api/v1/budget/session/{id}/increase`
- Wait for daily reset at midnight UTC
- Use `auto_repair=false` to preview fixes without cost

### Debug Mode

Enable verbose logging:
```bash
export LOG_LEVEL=DEBUG
uvicorn apps.backend.src.app.main:app --reload
```

Watch repair pipeline logs:
```bash
tail -f var/lib/kai/logs/repair_pipeline/*.jsonl
```

## Performance Metrics

### Typical Execution Times

| Vulnerabilities | Discovery | Analysis | Repair | Validation | Total |
|----------------|-----------|----------|--------|------------|-------|
| 1-5 | 10s | 15s | 20s | 10s | ~55s |
| 5-10 | 20s | 30s | 40s | 20s | ~110s |
| 10-20 | 40s | 60s | 80s | 40s | ~220s |

### Cost Efficiency

- **Best Case**: 80% cost savings (mostly local execution)
- **Average Case**: 65-70% cost savings (hybrid approach)
- **Worst Case**: 40% cost savings (many complex vulnerabilities)

## Security Considerations

### Audit Trail

All repair pipeline executions are logged with:
- Target scanned
- Vulnerabilities discovered
- Fixes applied
- Cost incurred
- User/session responsible
- Cryptographic signatures (KaiOrchestrator Phase 6)

### Permission Requirements

- **ROLE_OPERATOR** required for all repair endpoints
- Scope validation via `config/authorized_scope.json`
- Permission slips required for production targets

### Code Review

**IMPORTANT**: Even with auto-apply enabled, always review:
1. Git diff of all changes
2. Validation confidence scores
3. Any reported issues
4. Test suite results

Rollback immediately if issues detected:
```bash
git checkout <file>
```

## Future Enhancements

### Planned Features

1. **Batch Repair Mode**
   - Repair multiple targets in parallel
   - Shared session budget pool
   - Progress tracking per target

2. **Learning System**
   - Index successful repair patterns
   - RAG-based fix suggestions
   - Continuous improvement from feedback

3. **Advanced Validation**
   - Runtime testing in sandboxed environment
   - Security regression detection
   - Performance impact analysis

4. **Cost Forecasting**
   - Predict cost before execution
   - Budget-aware target selection
   - Cost optimization recommendations

## Support

For issues or questions:
- GitHub Issues: https://github.com/kaison/k1/issues
- Documentation: `/docs/`
- API Reference: http://localhost:8000/docs

## Version History

- **v7.6** - Initial repair pipeline integration
- **v7.5** - Budget tracking and cost optimization
- **v7.4** - Model bidding and orchestration
- **v7.0-7.3** - Foundation (KaiOrchestrator, agents, CLI tools)

---

**Last Updated**: 2025-01-15
**Status**: Production Ready
**Integration Complete**: ✅
