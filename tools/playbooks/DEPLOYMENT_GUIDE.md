# Chain Playbook Production Deployment Guide
## OPTION A PROMPT 4 Integration & Deployment

**Version:** 1.0  
**Date:** 2026-04-12  
**Audience:** DevOps, Operations, Platform Engineers  
**Status:** Production-Ready  

---

## Quick Start

```bash
# 1. Verify integration registry
grep "integration_status.*COMPLETE" tools/playbooks/chain_playbook_registry_integration.yaml

# 2. Run test suite
pytest tests/test_chain_playbook_integration.py -v

# 3. Sync CVEs to Vault (if needed)
python3 scripts/vault_cve_sync.py --cve-knowledge-base tools/knowledge/cve_knowledge.yaml

# 4. Deploy chain playbooks
./k1 deploy --component chain-playbooks --version latest

# 5. Verify deployment
./k1 status --component chain-playbooks
```

---

## Prerequisites

- KAISON AI platform deployed and operational
- PostgreSQL 14+ database running
- Redis 6.0+ cache available
- Vault 1.10+ with auth configured
- Python 3.11+ installed
- Docker available (for containerized execution)
- 4+ CPU cores, 2+ GB RAM available

---

## Integration Verification

Before deploying, verify all integration components:

```bash
# Check registry integrity
python3 -c "
import yaml
with open('tools/playbooks/chain_playbook_registry_integration.yaml') as f:
    r = yaml.safe_load(f)
    print(f'✅ Registry loaded: {r[\"chain_playbook_integration\"][\"metadata\"][\"integration_status\"]}')
    print(f'✅ Security: {r[\"chain_playbook_integration\"][\"metadata\"][\"security_clearance\"]}')
    print(f'✅ Approval: {r[\"chain_playbook_integration\"][\"metadata\"][\"production_approval\"]}')
"

# Verify all test files present
ls -la tools/playbooks/chain_playbook_registry_integration.yaml
ls -la tests/test_chain_playbook_integration.py
ls -la tools/playbooks/OPTION_A_SECURITY_AUDIT_REPORT.md
ls -la tools/playbooks/OPTION_A_PERFORMANCE_VALIDATION_REPORT.md
```

---

## Step-by-Step Deployment

### Step 1: Pre-Deployment Checks

```bash
# Verify platform health
./k1 health-check --full

# Check database connectivity
psql -h localhost -U kaison_db_user -d kaison_db -c "SELECT version();"

# Verify Vault connectivity
vault status -format=json | jq '.sealed'

# Test Redis connectivity
redis-cli ping
```

### Step 2: Load Registry into Database

```bash
# Parse registry and load into playbook table
python3 scripts/load_chain_registry.py \
  --registry tools/playbooks/chain_playbook_registry_integration.yaml \
  --database kaison_db

# Verify loading
psql -h localhost -d kaison_db -c \
  "SELECT COUNT(*) FROM playbooks WHERE type='chain';"
```

Expected output: `35` (35 chain playbooks loaded)

### Step 3: Sync CVEs to Vault

```bash
# Extract CVEs from chains
python3 scripts/extract_chain_cves.py \
  --registry tools/playbooks/chain_playbook_registry_integration.yaml \
  --output cves_to_sync.json

# Sync to Vault KV v2
python3 scripts/vault_cve_sync.py \
  --cve-data cves_to_sync.json \
  --vault-address https://vault.kaison.ai:8200 \
  --vault-path secret/data/kaison/cve-library

# Verify sync (sample)
vault kv get secret/kaison/cve-library/CVE-2020-5902
```

### Step 4: Copy Playbook Files

```bash
# Copy skeleton playbooks to chain_orchestration directory
mkdir -p tools/playbooks/chain_orchestration
cp tools/playbooks/skeletons/*.yaml tools/playbooks/chain_orchestration/

# Index playbooks
python3 scripts/index_playbooks.py \
  --source tools/playbooks/chain_orchestration \
  --output tools/playbooks/playbook_index.json
```

### Step 5: Run Pre-Deployment Tests

```bash
# Run full test suite
pytest tests/test_chain_playbook_integration.py -v --tb=short

# Expected output: 27+ tests PASSED

# Run security scan
bandit -r tools/playbooks/chain_orchestration/ -f txt

# Expected output: 0 issues found

# Run YAML validation
yamllint tools/playbooks/chain_orchestration/*.yaml

# Expected output: 0 problems
```

### Step 6: Deploy to Staging

```bash
# Create staging deployment
./k1 deploy \
  --component chain-playbooks \
  --environment staging \
  --version 1.0.0 \
  --dry-run

# Review deployment plan
# (manual approval required)

# Execute staging deployment
./k1 deploy \
  --component chain-playbooks \
  --environment staging \
  --version 1.0.0 \
  --confirm
```

### Step 7: Staging Validation

```bash
# Run smoke tests on staging
./k1 test --environment staging --component chain-playbooks

# Verify playbooks accessible
curl http://staging.kaison.ai:8080/api/playbooks/chain | jq '.count'

# Verify CVE lookups working
curl http://staging.kaison.ai:8080/api/playbooks/chain-exploit-rce-escalation-01/cves | jq '.total'

# Check logs for errors
./k1 logs --environment staging --component chain-playbooks --tail 100
```

### Step 8: Production Deployment

```bash
# Create production deployment
./k1 deploy \
  --component chain-playbooks \
  --environment production \
  --version 1.0.0 \
  --dry-run

# Review and approve
# (manual approval required)

# Execute production deployment
./k1 deploy \
  --component chain-playbooks \
  --environment production \
  --version 1.0.0 \
  --confirm
```

### Step 9: Post-Deployment Verification

```bash
# Verify deployment completed
./k1 status --component chain-playbooks --environment production

# Check all 35 playbooks loaded
curl http://api.kaison.ai:8080/api/playbooks/chain | jq '.count'

# Expected: 35

# Test critical chains
curl -X POST http://api.kaison.ai:8080/api/playbooks/chain-recon-master-orchestration-01/validate
curl -X POST http://api.kaison.ai:8080/api/playbooks/chain-exploit-rce-escalation-01/validate
curl -X POST http://api.kaison.ai:8080/api/playbooks/chain-persist-establish-access-01/validate

# Expected: all return HTTP 200 OK with validation results
```

---

## Rollback Procedure

If deployment fails or issues discovered:

```bash
# Immediate rollback to previous version
./k1 rollback \
  --component chain-playbooks \
  --environment production \
  --to-version 0.50.0

# Verify rollback completed
./k1 status --component chain-playbooks

# Check logs for issues
./k1 logs --component chain-playbooks --since 30m
```

---

## Operational Monitoring

### Key Metrics to Monitor

```
1. Chain Execution Success Rate
   - Alert if < 85% for reconnaissance cluster
   - Alert if < 75% for exploitation cluster
   - Alert if < 65% for persistence cluster

2. Execution Timing
   - Alert if average > 1.5x expected time
   - Alert if any chain exceeds timeout window

3. Detection Risk Escalation
   - Alert if any chain approaches 0.70+ risk
   - Alert if escalation rate > 0.02 per minute

4. Vault Performance
   - Alert if CVE lookup time > 500ms
   - Alert if Vault connectivity issues

5. Resource Usage
   - Alert if CPU > 80% sustained
   - Alert if Memory > 85% utilization
```

### Monitoring Setup

```bash
# Enable comprehensive monitoring
./k1 monitoring enable --component chain-playbooks

# Configure alerts
./k1 alerts configure \
  --component chain-playbooks \
  --alert-level critical \
  --channel pagerduty

# View dashboard
open http://grafana.kaison.ai:3000/d/chain-playbooks
```

---

## Troubleshooting

### Chain Playbook Not Found

```bash
# Check if playbook registered
psql -h localhost -d kaison_db -c \
  "SELECT * FROM playbooks WHERE id='chain-exploit-rce-escalation-01';"

# If not found, reload registry
python3 scripts/load_chain_registry.py \
  --registry tools/playbooks/chain_playbook_registry_integration.yaml \
  --database kaison_db --force
```

### CVE Lookup Failing

```bash
# Test Vault connectivity
vault status

# Check CVE sync
vault kv list secret/kaison/cve-library/ | grep -c "CVE-"

# Re-sync if needed
python3 scripts/vault_cve_sync.py \
  --cve-data cves_to_sync.json \
  --vault-address https://vault.kaison.ai:8200 \
  --force
```

### Chain Execution Timeout

```bash
# Check if timing window exceeded
grep "execution_time_minutes" tools/playbooks/chain_orchestration/rce_chain.yaml

# Review actual execution logs
grep "TIMING" kaison_logs.jsonl | tail -20

# If legitimate increase needed, update registry
# (requires re-approval)
```

### Detection Risk Too High

```bash
# Check risk escalation logs
grep "DETECTION_RISK" kaison_logs.jsonl | tail -50

# If risk escalating too fast:
# 1. Reduce playbook execution frequency
# 2. Add delays between chains
# 3. Implement evasion chains earlier

# Example: space out exploitations
./k1 config update \
  --component chain-playbooks \
  --exploitation-delay 300s
```

---

## Performance Tuning

### For High-Frequency Execution

```bash
# Increase Vault caching
./k1 config update \
  --component chain-playbooks \
  --vault-cache-ttl 3600

# Pre-cache common chains
python3 scripts/cache_chains.py \
  --chains rce_escalation,auth_bypass,credential_theft \
  --ttl 7200
```

### For Large Organizations

```bash
# Enable parallel execution
./k1 config update \
  --component chain-playbooks \
  --parallel-chains 5

# Scale Vault
./k1 scale vault --instances 3

# Scale playbook service
./k1 scale playbook-service --replicas 5
```

---

## Maintenance

### Weekly Maintenance

```bash
# Verify all playbooks accessible
python3 scripts/verify_playbooks.py \
  --registry tools/playbooks/chain_playbook_registry_integration.yaml

# Clean up old logs
./k1 logs cleanup --older-than 7d --component chain-playbooks

# Test CVE library freshness
curl http://api.kaison.ai:8080/api/playbooks/cve-freshness
```

### Monthly Maintenance

```bash
# Run full security audit
./k1 audit --component chain-playbooks --full

# Review execution metrics
./k1 metrics export \
  --component chain-playbooks \
  --period last-month \
  --format csv > metrics.csv

# Update documentation
# (if procedures changed)
```

### Quarterly Maintenance

```bash
# Test disaster recovery
./k1 dr test --component chain-playbooks

# Review and update threat model
# (security review)

# Capacity planning review
# (performance metrics analysis)
```

---

## Support & Escalation

**For Issues:** `support@kaison.ai`  
**For Security:** `security@kaison.ai`  
**For Performance:** `devops@kaison.ai`  

**On-Call Escalation:**
1. L1: Check deployment status with `./k1 status`
2. L2: Review logs with `./k1 logs`
3. L3: Contact Platform Integration Director
4. Critical: Page on-call security team

---

## Document Control

**Version:** 1.0  
**Last Updated:** 2026-04-12  
**Next Review:** 2026-05-12  
**Maintained By:** Operations Team  

---
