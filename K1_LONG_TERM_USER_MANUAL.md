# Kaison K1 - Long Term User Manual

**Advanced Operations, Optimization, and Mastery**

This guide covers ongoing use, advanced features, optimization, and troubleshooting for experienced users.

---

## Table of Contents

1. [System Architecture](#system-architecture)
2. [Advanced Tool Operations](#advanced-tool-operations)
3. [Multi-Tool Workflows](#multi-tool-workflows)
4. [Performance Optimization](#performance-optimization)
5. [Maintenance & Monitoring](#maintenance--monitoring)
6. [Troubleshooting Guide](#troubleshooting-guide)
7. [Production Deployment](#production-deployment)
8. [Security Best Practices](#security-best-practices)

---

## System Architecture

### Components Overview

```
┌─────────────────────────────────────────────────┐
│              Frontend (React/TS)                 │
│    Dashboard, Tools UI, Programs, Security      │
└────────────────────┬────────────────────────────┘
                     │ HTTP/WebSocket
┌────────────────────▼────────────────────────────┐
│            FastAPI Backend (Python)             │
│                                                  │
│  ┌──────────────┐  ┌──────────────┐            │
│  │Tool Routers  │  │Program API   │            │
│  ├──────────────┤  ├──────────────┤            │
│  │Validators    │  │Scrapers      │            │
│  │Analyzers     │  │Discovery     │            │
│  │Orchestration │  │Matching      │            │
│  └──────────────┘  └──────────────┘            │
│                                                  │
│  ┌──────────────────────────────────────────┐  │
│  │     Core Systems                         │  │
│  │  LLM Client | Tool Framework |Embeddings│  │
│  │  Kai Security Guardrails     │Auth      │  │
│  └──────────────────────────────────────────┘  │
│                                                  │
│  Middleware: Auth | CORS | Rate Limit | Audit  │
└────────────────────┬────────────────────────────┘
                     │ SQL/Redis
┌────────────────────▼────────────────────────────┐
│         Data Layer                              │
│  PostgreSQL | pgvector | Redis | GCS           │
└─────────────────────────────────────────────────┘
```

### Data Flow

```
User Request
    ↓
Authentication & Rate Limiting
    ↓
Authorization Check (Kai Guardrails)
    ↓
Tool Routing & Execution
    ↓
LLM Processing (with tool calling)
    ↓
Result Aggregation
    ↓
Audit Logging
    ↓
Response to User
```

---

## Advanced Tool Operations

### Tool Categories & Usage

#### 1. Quick Classifier (FAST)
**Speed**: <1 second | **Autonomy**: TIER 0 (automatic)

```bash
# Fast finding categorization
curl -X POST http://localhost:8000/api/v1/tools/quick_classifier/execute \
  -d '{
    "finding_text": "SQL injection in search parameter"
  }'

# Use case: Bulk classification of large finding lists
for finding in findings_list.txt; do
  curl -s -X POST http://localhost:8000/api/v1/tools/quick_classifier/execute \
    -d "{\"finding_text\": \"$finding\"}"
done
```

#### 2. Finding Validator (DEEP)
**Speed**: 15-20 seconds | **Autonomy**: TIER 2 (approval required)

```bash
# Deep multi-step validation with reasoning
curl -X POST http://localhost:8000/api/v1/tools/finding_validator/execute \
  -d '{
    "finding_title": "Unauthenticated File Upload",
    "finding_description": "Can upload arbitrary files without authentication",
    "asset_type": "web",
    "evidence": ["screenshot1.jpg", "request_log.txt"],
    "estimated_severity": "critical"
  }'

# Result includes:
# - 5-step reasoning trace
# - Reproducibility score
# - CVSS severity
# - False positive check
# - Confidence level
```

#### 3. Vulnerability Analyzer (CONTEXT)
**Speed**: 15-20 seconds | **Autonomy**: TIER 2

```bash
# Comprehensive vulnerability analysis
curl -X POST http://localhost:8000/api/v1/tools/vulnerability_analyzer/execute \
  -d '{
    "vulnerability_type": "rce",
    "affected_technology": "Node.js v12.0.0",
    "attack_description": "Unbounded shell command execution via eval()",
    "impact_description": "Complete system compromise possible",
    "exploitation_difficulty": "easy"
  }'

# Returns:
# - Technical analysis
# - Technology assessment
# - Exploitation likelihood
# - Impact calculation
# - Overall risk score
```

#### 4. Chain Analyzer (PATTERNS)
**Speed**: 15-30 seconds | **Autonomy**: TIER 2

```bash
# Identify multi-step attack chains
curl -X POST http://localhost:8000/api/v1/tools/chain_analyzer/execute \
  -d '{
    "findings": [
      "Authentication bypass in login",
      "SQL injection in profile query",
      "Data exposure in API response"
    ],
    "target_scope": "api.example.com"
  }'

# Returns:
# - Correlated findings
# - Attack sequences
# - Chain severity
# - Estimated payout increase
```

#### 5. Program Matcher (TARGETING)
**Speed**: 2-3 seconds | **Autonomy**: TIER 2

```bash
# Intelligent bug bounty program targeting
curl -X POST http://localhost:8000/api/v1/tools/program_matcher/execute \
  -d '{
    "finding_title": "Remote Code Execution",
    "finding_scope": "api.acme.com",
    "vulnerability_type": "rce",
    "severity": "critical"
  }'

# Returns:
# - Matched programs ranked by fit
# - Estimated payouts
# - Scope compatibility
# - Recommendation
```

### Tool Configuration

```bash
# View tool schema (for LLM integration)
curl http://localhost:8000/api/v1/tools/finding_validator/schema

# Get tool statistics
curl http://localhost:8000/api/v1/tools

# Filter tools by category
curl 'http://localhost:8000/api/v1/tools?category=validation'

# List tools by autonomy tier
curl 'http://localhost:8000/api/v1/tools?autonomy_tier=0'  # Auto only
```

---

## Multi-Tool Workflows

### Workflow 1: Complete Finding Lifecycle

```bash
#!/bin/bash
# End-to-end processing of a single finding

FINDING="SQL injection in search"
TARGET="example.com"
USER="hunter@example.com"

echo "🔄 Finding Lifecycle Workflow"

# Step 1: Quick classification
echo "1️⃣  Classifying..."
CLASS=$(curl -s -X POST http://localhost:8000/api/v1/tools/quick_classifier/execute \
  -d "{\"finding_text\": \"$FINDING\"}")
CATEGORY=$(echo $CLASS | jq -r '.data.primary_category')
echo "   Category: $CATEGORY"

# Step 2: Deep validation
echo "2️⃣  Validating..."
VALID=$(curl -s -X POST http://localhost:8000/api/v1/tools/finding_validator/execute \
  -d "{
    \"finding_title\": \"$FINDING\",
    \"finding_description\": \"Potential SQL injection attack\",
    \"asset_type\": \"web\",
    \"estimated_severity\": \"high\"
  }")
IS_VALID=$(echo $VALID | jq -r '.data.is_valid')
CONFIDENCE=$(echo $VALID | jq -r '.data.confidence')
echo "   Valid: $IS_VALID (confidence: $CONFIDENCE)"

# Step 3: Analyze if valid
if [ "$IS_VALID" == "true" ]; then
  echo "3️⃣  Analyzing..."
  ANALYSIS=$(curl -s -X POST http://localhost:8000/api/v1/tools/vulnerability_analyzer/execute \
    -d "{
      \"vulnerability_type\": \"sqli\",
      \"affected_technology\": \"Web Application\",
      \"attack_description\": \"$FINDING\",
      \"exploitation_difficulty\": \"easy\"
    }")
  RISK=$(echo $ANALYSIS | jq -r '.data.overall_risk_score')
  echo "   Risk Score: $RISK"

  # Step 4: Find programs
  echo "4️⃣  Matching programs..."
  PROGRAMS=$(curl -s -X POST http://localhost:8000/api/v1/tools/program_matcher/execute \
    -d "{
      \"finding_title\": \"$FINDING\",
      \"finding_scope\": \"$TARGET\",
      \"severity\": \"high\"
    }")
  RECOMMENDED=$(echo $PROGRAMS | jq -r '.data.recommended_program.program_name')
  PAYOUT=$(echo $PROGRAMS | jq -r '.data.recommended_program.estimated_payout')
  echo "   Recommended: $RECOMMENDED (Est. $PAYOUT)"

  echo ""
  echo "✅ Ready to submit!"
else
  echo "❌ Finding not valid - rejected"
fi
```

### Workflow 2: Batch Program Analysis

```bash
#!/bin/bash
# Analyze all available programs and rank by opportunity

echo "📊 Program Analysis Workflow"

# Get all programs
PROGRAMS=$(curl -s http://localhost:8000/api/v1/programs)

# Extract program IDs
PROG_IDS=$(echo $PROGRAMS | jq -r '.data.programs[].id')

for PROG_ID in $PROG_IDS; do
  PROG=$(echo $PROGRAMS | jq -r ".data.programs[] | select(.id==\"$PROG_ID\")")
  NAME=$(echo $PROG | jq -r '.name')
  PAYOUT=$(echo $PROG | jq -r '.average_payout')

  echo "🎯 $NAME - Max: \$$PAYOUT"
done

# Sort by payout
PROGRAMS_SORTED=$(echo $PROGRAMS | jq '.data.programs | sort_by(.average_payout) | reverse')
echo ""
echo "💰 Top 3 by payout:"
echo $PROGRAMS_SORTED | jq '.[0:3] | .[] | "\(.name) - $\(.average_payout)"'
```

### Workflow 3: Continuous Monitoring

```bash
#!/bin/bash
# Monitor system health and run periodic scans

MONITOR_INTERVAL=300  # 5 minutes

while true; do
  echo "[$(date)] Running monitoring cycle..."

  # Check system health
  HEALTH=$(curl -s http://localhost:8000/api/v1/tools/health)
  STATUS=$(echo $HEALTH | jq -r '.data.status')
  TOOLS=$(echo $HEALTH | jq -r '.data.security_stats.total_authorizations')

  echo "  System Status: $STATUS"
  echo "  Active Tools: $TOOLS"

  # Check security alerts
  ALERTS=$(curl -s http://localhost:8000/api/v1/kai/security-alerts)
  ALERT_COUNT=$(echo $ALERTS | jq '.data.alert_count')

  if [ "$ALERT_COUNT" -gt 0 ]; then
    echo "  ⚠️  Security Alerts: $ALERT_COUNT"
    echo $ALERTS | jq '.data.alerts[0]'
  fi

  # Check programs
  PROGRAMS=$(curl -s http://localhost:8000/api/v1/programs)
  PROG_COUNT=$(echo $PROGRAMS | jq '.data.total')
  echo "  Programs Available: $PROG_COUNT"

  echo ""
  echo "Next check in $MONITOR_INTERVAL seconds..."
  sleep $MONITOR_INTERVAL
done
```

---

## Performance Optimization

### 1. Caching Strategy

```bash
# Cache tool schemas (don't request every time)
curl -s http://localhost:8000/api/v1/tools | jq '.data.tools' > tools_cache.json

# Use cached data
TOOL_ID="quick_classifier"
cat tools_cache.json | jq ".[] | select(.id==\"$TOOL_ID\")"

# Cache programs (refresh daily)
curl -s http://localhost:8000/api/v1/programs?limit=1000 > programs_cache.json

# Batch requests to reduce API calls
# BAD: Loop with individual requests
# GOOD: Batch multiple operations
```

### 2. Batch Processing

```bash
#!/bin/bash
# Process multiple findings in batches

BATCH_SIZE=10
findings_file="findings.txt"
processed=0

while IFS= read -r finding; do
  # Process finding
  curl -s -X POST http://localhost:8000/api/v1/tools/quick_classifier/execute \
    -d "{\"finding_text\": \"$finding\"}" &

  ((processed++))

  # Wait after batch
  if [ $((processed % BATCH_SIZE)) -eq 0 ]; then
    wait
    echo "Processed batch of $BATCH_SIZE"
  fi
done < "$findings_file"

wait
echo "All findings processed"
```

### 3. Query Optimization

```bash
# Get only needed fields
curl 'http://localhost:8000/api/v1/programs' \
  -d 'fields=id,name,platform,average_payout'

# Use filtering to reduce data
curl 'http://localhost:8000/api/v1/programs?min_payout=5000&max_payout=50000'

# Limit results
curl 'http://localhost:8000/api/v1/programs?limit=50&offset=0'

# Pagination for large datasets
PAGE=1
while true; do
  OFFSET=$((($PAGE - 1) * 50))
  RESULT=$(curl -s "http://localhost:8000/api/v1/programs?limit=50&offset=$OFFSET")
  COUNT=$(echo $RESULT | jq '.data | length')

  if [ $COUNT -eq 0 ]; then
    break
  fi

  # Process page
  echo $RESULT | jq '.data[]'

  ((PAGE++))
done
```

### 4. Async Operations

```bash
# Use async endpoints for long-running operations
curl -X POST http://localhost:8000/api/v1/tools/finding_validator/execute/async \
  -d '{
    "finding_title": "...",
    "finding_description": "..."
  }'

# Returns execution_id
# Check status later
curl http://localhost:8000/api/v1/tools/execution-status/execution-id-123
```

### 5. Database Optimization

```bash
# Monitor database performance
# Create indexes on frequently queried columns
psql $DATABASE_URL << EOF
CREATE INDEX idx_findings_severity ON findings(severity);
CREATE INDEX idx_programs_payout ON programs(average_payout);
CREATE INDEX idx_audit_timestamp ON audit_logs(timestamp);
EOF

# Vacuum database
VACUUM ANALYZE;

# Check slow queries
SELECT query, mean_time, calls
FROM pg_stat_statements
ORDER BY mean_time DESC
LIMIT 10;
```

---

## Maintenance & Monitoring

### Daily Maintenance

```bash
#!/bin/bash
# Daily maintenance checklist

echo "🔧 Daily Maintenance"

# 1. Check disk space
DISK=$(df -h / | awk 'NR==2 {print $5}')
echo "Disk usage: $DISK"

# 2. Backup database
pg_dump $DATABASE_URL > backup-$(date +%Y%m%d).sql
echo "✅ Database backed up"

# 3. Clean old audit logs (keep 90 days)
psql $DATABASE_URL << EOF
DELETE FROM audit_logs
WHERE timestamp < NOW() - INTERVAL '90 days';
EOF
echo "✅ Old logs cleaned"

# 4. Check system health
curl -s http://localhost:8000/api/v1/tools/health | jq '.'
echo "✅ System health verified"

# 5. Test all tools
TOOLS=$(curl -s http://localhost:8000/api/v1/tools | jq -r '.data.tools[].id')
for tool in $TOOLS; do
  STATUS=$(curl -s http://localhost:8000/api/v1/tools/$tool | jq '.success')
  echo "  $tool: $STATUS"
done
echo "✅ All tools operational"
```

### Weekly Monitoring

```bash
#!/bin/bash
# Weekly monitoring report

echo "📊 Weekly Report: $(date +%Y-%m-%d)"

# Stats
STATS=$(curl -s http://localhost:8000/api/v1/kai/admin/security-stats)

echo ""
echo "Authorizations:"
echo "  Total: $(echo $STATS | jq '.data.stats.total_authorizations')"
echo "  Active: $(echo $STATS | jq '.data.stats.active_authorizations')"

echo ""
echo "Audit Trail:"
echo "  Total logs: $(echo $STATS | jq '.data.stats.total_audit_logs')"
echo "  Blocked ops: $(echo $STATS | jq '.data.stats.blocked_operations')"

echo ""
echo "Security:"
ALERTS=$(echo $STATS | jq '.data.alerts')
if [ $(echo $ALERTS | jq 'length') -eq 0 ]; then
  echo "  Alerts: None (✅ Good)"
else
  echo "  Alerts: $(echo $ALERTS | jq 'length')"
  echo $ALERTS | jq '.[] | "    - \(.type): \(.severity)"'
fi

# Generate compliance report
COMPLIANCE=$(curl -s http://localhost:8000/api/v1/kai/compliance-report?days=7)
echo ""
echo "Compliance (7 days):"
echo "  Scans: $(echo $COMPLIANCE | jq '.data.summary.total_scans')"
echo "  Success rate: $(echo $COMPLIANCE | jq '.data.summary.success_rate')%"
```

### Log Management

```bash
# View recent errors
docker logs kai-security-engine --tail 100 | grep -i error

# Archive old logs
tar -czf logs-archive-$(date +%Y%m%d).tar.gz /var/log/k1/

# Monitor log size
du -sh /var/log/k1/

# Enable log rotation
# Add to /etc/logrotate.d/k1
/var/log/k1/*.log {
  daily
  rotate 30
  compress
  delaycompress
  notifempty
  create 0640 k1 k1
}
```

---

## Troubleshooting Guide

### API Errors

#### Error: "No valid authorization found"

**Cause**: Scan target not in authorized scope

**Solution**:
```bash
# Check active authorizations
curl http://localhost:8000/api/v1/kai/authorizations

# Create new authorization with correct scope
curl -X POST http://localhost:8000/api/v1/kai/authorize \
  -d "target=*.example.com"  # Use wildcard for subdomains

# Verify authorization
curl http://localhost:8000/api/v1/kai/authorizations
```

#### Error: "Rate limit exceeded"

**Cause**: Too many requests from same user

**Solution**:
```bash
# Check rate limit status
curl -i http://localhost:8000/api/v1/tools | grep -i rate

# Wait before retrying
sleep 60

# For bulk operations, add delays
for finding in findings_list; do
  process_finding "$finding"
  sleep 1  # 1 second between requests
done
```

#### Error: "Tool execution timeout"

**Cause**: Deep tools take 15-20 seconds

**Solution**:
```bash
# Increase timeout
curl --max-time 30 -X POST http://localhost:8000/api/v1/tools/finding_validator/execute

# Use async execution
curl -X POST http://localhost:8000/api/v1/tools/finding_validator/execute/async

# Check status later
curl http://localhost:8000/api/v1/tools/execution-status/execution-id
```

### Database Issues

#### Error: "Connection pool exhausted"

**Cause**: Too many concurrent connections

**Solution**:
```bash
# Check connections
psql -d $DATABASE_URL -c "SELECT count(*) FROM pg_stat_activity;"

# Increase pool size in .env
DATABASE_POOL_SIZE=50

# Kill idle connections
psql -d $DATABASE_URL -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE idle_in_transaction;"
```

#### Error: "Disk quota exceeded"

**Cause**: Database or logs too large

**Solution**:
```bash
# Find large tables
psql -d $DATABASE_URL << EOF
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname != 'pg_catalog'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
EOF

# Archive old data
DELETE FROM audit_logs WHERE timestamp < NOW() - INTERVAL '180 days';

# Vacuum
VACUUM FULL;
```

### Performance Issues

#### Slow Tool Execution

**Diagnosis**:
```bash
# Check tool execution time
curl -X POST http://localhost:8000/api/v1/tools/finding_validator/execute \
  -d '{"finding_title": "test", ...}' \
  | jq '.data.execution_time_ms'

# Should be:
# - Quick Classifier: < 1000ms
# - Finding Validator: 15000-20000ms
# - Vulnerability Analyzer: 15000-20000ms
```

**Solutions**:
- Use Quick Classifier for fast classification
- Batch similar operations
- Use local embeddings if OpenAI is slow
- Check API rate limits

#### Slow API Responses

**Diagnosis**:
```bash
# Measure request latency
time curl http://localhost:8000/api/v1/tools

# Check backend logs
docker logs kai-security-engine | grep -i duration
```

**Solutions**:
- Add caching layer (Redis)
- Optimize database queries
- Add indexes
- Scale horizontally (multiple instances)

---

## Production Deployment

### Environment Checklist

```bash
# Before going to production, verify:

# 1. Environment variables
echo "🔐 Checking secrets..."
test -n "$ANTHROPIC_API_KEY" && echo "✅ ANTHROPIC_API_KEY set"
test -n "$DATABASE_URL" && echo "✅ DATABASE_URL set"
test -n "$REDIS_URL" && echo "✅ REDIS_URL set"

# 2. Database migrations
echo "🗄️  Running migrations..."
python manage.py migrate

# 3. SSL certificates
echo "🔒 Checking SSL..."
ls -la /etc/ssl/certs/

# 4. Monitoring configured
echo "📊 Checking monitoring..."
curl -s http://prometheus:9090/api/v1/status/config | jq '.status'

# 5. Backups configured
echo "💾 Checking backups..."
ls -la /backups/

# 6. Log aggregation
echo "📝 Checking logs..."
curl -s http://elasticsearch:9200/_cluster/health | jq '.status'

# 7. CDN configured
echo "📡 Checking CDN..."
curl -I https://cdn.example.com/static/app.js

# 8. Load balancer
echo "⚖️  Checking load balancer..."
curl -s http://localhost:8000/health | jq '.status'
```

### Scaling

```yaml
# kubernetes deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: kai-backend
spec:
  replicas: 3  # Start with 3
  selector:
    matchLabels:
      app: kai-backend
  template:
    metadata:
      labels:
        app: kai-backend
    spec:
      containers:
      - name: kai-backend
        image: us-central1-docker.pkg.dev/PROJECT/kai-repo/kai-engine:latest
        resources:
          requests:
            memory: "1Gi"
            cpu: "1"
          limits:
            memory: "2Gi"
            cpu: "2"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 10
          periodSeconds: 5
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: kai-backend-autoscale
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: kai-backend
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

---

## Security Best Practices

### 1. Regular Security Updates

```bash
# Check for dependency vulnerabilities
pip audit
npm audit

# Update dependencies
pip install --upgrade -r requirements.txt
npm update
```

### 2. Secrets Management

```bash
# Never commit secrets
git status | grep .env

# Use environment variables
export ANTHROPIC_API_KEY=$(gcloud secrets versions access latest --secret="anthropic-key")

# Rotate secrets regularly
# Change API keys monthly
# Regenerate database passwords quarterly
```

### 3. Access Control

```bash
# Monitor who has access
gcloud projects get-iam-policy PROJECT_ID --flatten="bindings[].members" | grep serviceAccount

# Remove unused service accounts
gcloud iam service-accounts list
gcloud iam service-accounts delete ACCOUNT@PROJECT_ID.iam.gserviceaccount.com

# Use MFA for admin access
gcloud config set account ACCOUNT
gcloud auth login
```

### 4. Audit Logging

```bash
# Review audit logs regularly
curl http://localhost:8000/api/v1/kai/audit-logs?days=7 > weekly-audit.json

# Export for compliance
curl http://localhost:8000/api/v1/kai/compliance-report > compliance.json

# Archive securely
gpg --encrypt --recipient key-id weekly-audit.json
tar -czf audit-archive-$(date +%Y%m).tar.gz audit-*.json
```

### 5. Network Security

```bash
# Firewall rules (GCP example)
gcloud compute firewall-rules create allow-k1-api \
  --allow=tcp:8000 \
  --source-ranges=TRUSTED_IP/32

# VPN for admin access
gcloud compute vpns create k1-vpn

# Rate limiting
gcloud compute backend-services update kai-backend \
  --rate-limiting-config request-count=100 --rate-limiting-period=60s
```

---

## Appendix: Common Commands

```bash
# System health
curl http://localhost:8000/health

# List tools
curl http://localhost:8000/api/v1/tools

# List programs
curl http://localhost:8000/api/v1/programs

# View audit logs
curl http://localhost:8000/api/v1/kai/audit-logs

# Security alerts
curl http://localhost:8000/api/v1/kai/security-alerts

# Compliance report
curl http://localhost:8000/api/v1/kai/compliance-report

# Database backup
pg_dump $DATABASE_URL > backup.sql

# View logs
docker logs kai-security-engine --follow

# Restart system
docker restart kai-security-engine

# Scale up
kubectl scale deployment kai-backend --replicas=5
```

---

**Master Kaison K1. Optimize your workflows. Secure your operations. Happy hunting! 🚀**

**Questions?** Check code comments or reach out to the community.

**Version**: 1.0 | **Last Updated**: 2026-02-02
