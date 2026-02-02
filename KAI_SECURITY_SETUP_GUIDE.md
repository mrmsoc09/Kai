# Kai Security Setup & Operations Guide

**Enterprise-Ready OSINT & Vulnerability Discovery Platform**

---

## Overview

Kai is a defensive security platform designed for:
- ✅ **Authorized vulnerability discovery** on authorized targets
- ✅ **Bug bounty hunting** on bug bounty platforms
- ✅ **OSINT reconnaissance** for security research
- ✅ **Safe, compliant scanning** with built-in guardrails
- ✅ **Complete audit trails** for compliance

**NOT FOR:**
- ❌ Unauthorized access
- ❌ Credential harvesting
- ❌ Malware distribution
- ❌ Data exfiltration
- ❌ Any use outside authorized scope

---

## Part 1: GCP Infrastructure Setup

### Prerequisites

```bash
# Install required tools
gcloud --version  # >= 400.0.0
bq --version      # BigQuery CLI
kubectl version   # For GKE

# Authenticate
gcloud auth login
gcloud config set project YOUR-PROJECT-ID
```

### Step 1: Create Service Account

```bash
PROJECT_ID="your-project-id"

# Create service account
gcloud iam service-accounts create kai-executor \
  --display-name="Kai Security Engine Executor" \
  --description="Runs Kai OSINT and vulnerability scanning with authorization checks"

# Get the email
SA_EMAIL="kai-executor@${PROJECT_ID}.iam.gserviceaccount.com"
echo "Service Account: $SA_EMAIL"
```

### Step 2: Set Up KMS Keys (for encryption)

```bash
# Create KMS keyring
gcloud kms keyrings create kai-keyring \
  --location us-central1

# Create KMS keys
gcloud kms keys create kai-cert-key \
  --location us-central1 \
  --keyring kai-keyring \
  --purpose encryption

gcloud kms keys create kai-env-key \
  --location us-central1 \
  --keyring kai-keyring \
  --purpose encryption

# Grant service account KMS access
gcloud kms keys add-iam-policy-binding kai-cert-key \
  --location us-central1 \
  --keyring kai-keyring \
  --member serviceAccount:$SA_EMAIL \
  --role roles/cloudkms.cryptoKeyDecrypter

gcloud kms keys add-iam-policy-binding kai-env-key \
  --location us-central1 \
  --keyring kai-keyring \
  --member serviceAccount:$SA_EMAIL \
  --role roles/cloudkms.cryptoKeyDecrypter
```

### Step 3: Create Secrets Manager Entries

```bash
# Store authorization certificates (encrypted)
echo "Creating authorization certificates secret..."
gcloud secrets create kai-authorization-certs \
  --replication-policy="automatic" \
  --description="Signed authorization certificates for Kai scanning"

# Store API keys
echo "Creating API keys secret..."
gcloud secrets create kai-api-keys \
  --replication-policy="automatic" \
  --description="API keys for external services (CTI feeds, vulnerability databases)"

# Grant service account access
gcloud secrets add-iam-policy-binding kai-authorization-certs \
  --member serviceAccount:$SA_EMAIL \
  --role roles/secretmanager.secretAccessor

gcloud secrets add-iam-policy-binding kai-api-keys \
  --member serviceAccount:$SA_EMAIL \
  --role roles/secretmanager.secretAccessor
```

### Step 4: Apply IAM Policy

```bash
# Apply the least-privilege IAM policy
gcloud projects set-iam-policy $PROJECT_ID iam-kai-executor-policy.json

# Verify permissions
echo "Service account permissions:"
gcloud projects get-iam-policy $PROJECT_ID \
  --flatten="bindings[].members" \
  --filter="bindings.members:serviceAccount:$SA_EMAIL" \
  --format='table(bindings.role)'
```

### Step 5: Create Artifact Registry

```bash
# Create Artifact Registry repository
gcloud artifacts repositories create kai-repo \
  --repository-format=docker \
  --location=us-central1 \
  --description="Docker images for Kai security engine"

# Configure authentication
gcloud auth configure-docker us-central1-docker.pkg.dev
```

### Step 6: Create BigQuery Audit Dataset

```bash
# Create dataset for audit logs
bq mk --dataset \
  --location=us-central1 \
  --description="Kai security audit trail and compliance logs" \
  kai_audit

# Create audit table
bq mk --table \
  kai_audit:scanning_operations \
  schema.json
```

### Step 7: Create GCS Buckets

```bash
# Create bucket for Kai configuration
gsutil mb -l us-central1 gs://kai-config-${PROJECT_ID}/

# Create bucket for scan results
gsutil mb -l us-central1 gs://kai-results-${PROJECT_ID}/

# Set bucket lifecycle (clean up old results)
echo '{
  "lifecycle": {
    "rule": [{
      "action": {"type": "Delete"},
      "condition": {"age": 90}
    }]
  }
}' | gsutil lifecycle set - gs://kai-results-${PROJECT_ID}/
```

---

## Part 2: Authorization Certificate Setup

### Creating Authorization Certificates

Kai requires explicit authorization certificates for all scanning. Certificates prove you have authorization to test a target.

#### Example 1: Bug Bounty Platform Authorization

```bash
# Create authorization for HackerOne program
curl -X POST http://localhost:8000/api/v1/kai/authorize \
  -H "Content-Type: application/json" \
  -d '{
    "authorization_type": "bug_bounty_platform",
    "target": "example.com",
    "authorized_by": "your-email@example.com",
    "duration_days": 365,
    "scope": "domain_wildcard",
    "methods": "osint,vulnerability_scanning,web_testing",
    "metadata": {
      "platform": "hackerone",
      "program_id": "example-program",
      "program_url": "https://hackerone.com/programs/example"
    }
  }'

# Response:
# {
#   "success": true,
#   "data": {
#     "certificate_id": "uuid-12345",
#     "authorization_type": "bug_bounty_platform",
#     "target": "example.com",
#     "expires_at": "2027-02-02T00:00:00",
#     "allowed_methods": ["osint", "vulnerability_scanning", "web_testing"]
#   }
# }
```

#### Example 2: Authorized Assessment Authorization

```bash
# Create authorization for authorized penetration test
curl -X POST http://localhost:8000/api/v1/kai/authorize \
  -H "Content-Type: application/json" \
  -d '{
    "authorization_type": "authorized_assessment",
    "target": "internal-app.company.com",
    "authorized_by": "ciso@company.com",
    "duration_days": 30,
    "scope": "specific_endpoints",
    "methods": "osint,vulnerability_scanning,web_testing,code_analysis",
    "metadata": {
      "authorization_document": "path/to/signed/authorization.pdf",
      "assessment_id": "ASSESS-2026-001",
      "scope_endpoints": ["/api/v1", "/admin"]
    }
  }'
```

#### Example 3: Internal Security Testing

```bash
# Create authorization for internal security team
curl -X POST http://localhost:8000/api/v1/kai/authorize \
  -H "Content-Type: application/json" \
  -d '{
    "authorization_type": "internal_security",
    "target": "*.company.internal",
    "authorized_by": "security-team@company.com",
    "duration_days": 180,
    "scope": "domain_wildcard",
    "methods": "osint,vulnerability_scanning,web_testing,network_testing,code_analysis",
    "metadata": {
      "team": "security",
      "request_id": "REQ-2026-0001",
      "approval_date": "2026-02-02"
    }
  }'
```

---

## Part 3: Using Kai for Authorized Scanning

### Starting an OSINT Scan

```bash
# List current authorizations
curl http://localhost:8000/api/v1/kai/authorizations

# Start OSINT reconnaissance
curl -X POST http://localhost:8000/api/v1/kai/scan/osint \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your-email@example.com",
    "target": "example.com"
  }'

# Response:
# {
#   "success": true,
#   "data": {
#     "scan_id": "scan-uuid",
#     "target": "example.com",
#     "status": "started",
#     "certificate_id": "cert-uuid",
#     "message": "OSINT scan started on example.com"
#   }
# }
```

### Starting a Vulnerability Scan

```bash
# Start comprehensive vulnerability scan
curl -X POST http://localhost:8000/api/v1/kai/scan/vulnerability \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your-email@example.com",
    "target": "example.com",
    "scan_type": "comprehensive"
  }'

# Available scan types:
# - "osint": Open source intelligence only
# - "passive": Passive reconnaissance
# - "active": Active scanning (requires authorization)
# - "comprehensive": Full vulnerability assessment
# - "bug_bounty": Targeted bug bounty scanning
```

### What Happens When You Scan

```
1. Authorization Check
   ├─ Kai checks for valid authorization certificate
   ├─ Verifies target matches authorized scope
   └─ Confirms method is allowed

2. Audit Logging
   ├─ Records scan initiation
   ├─ Logs user, target, time, IP address
   └─ Stores certificate ID

3. Safe Scanning
   ├─ Respects robots.txt and rate limits
   ├─ Identifies as Kai security scanner
   └─ Avoids destructive operations

4. Results Collection
   ├─ Aggregates findings
   ├─ Validates vulnerability descriptions
   └─ Stores with full audit trail

5. Compliance Verification
   ├─ Cross-checks all operations against authorization
   ├─ Generates compliance report
   └─ Alerts on any violations
```

---

## Part 4: Bug Bounty Hunter Guide

### Getting Started

**Step 1: Register on Bug Bounty Platform**
- Create account on HackerOne, Bugcrowd, Intigriti, etc.
- Find programs you want to participate in
- Review their scope and rules

**Step 2: Create Authorization in Kai**

```bash
# Example: Setting up for HackerOne program
curl -X POST http://localhost:8000/api/v1/kai/authorize \
  --data-urlencode 'authorization_type=bug_bounty_platform' \
  --data-urlencode 'target=target-domain.com' \
  --data-urlencode 'authorized_by=your-email@example.com' \
  --data-urlencode 'scope=domain_wildcard' \
  --data-urlencode 'methods=osint,vulnerability_scanning,web_testing'
```

**Step 3: Start Scanning**

```bash
# Stage 1: Reconnaissance
curl -X POST http://localhost:8000/api/v1/kai/scan/osint \
  -d '{"user_id":"your-email@example.com", "target":"target-domain.com"}'

# Stage 2: Vulnerability Discovery
curl -X POST http://localhost:8000/api/v1/kai/scan/vulnerability \
  -d '{"user_id":"your-email@example.com", "target":"target-domain.com", "scan_type":"bug_bounty"}'

# Stage 3: Analysis & Remediation Recommendations
curl -X POST http://localhost:8000/api/v1/kai/analyze/findings \
  -d '{"user_id":"your-email@example.com", "findings":[...]}'
```

### Best Practices

✅ **DO:**
- Always check platform rules before scanning
- Use Kai's authorization system
- Report findings through the platform's system
- Respect disclosed vulnerabilities
- Follow responsible disclosure timelines

❌ **DON'T:**
- Scan outside authorized scope
- Access data not required for security research
- Disrupt services or user data
- Report the same finding multiple times
- Use automation excessively (follow rate limits)

### Example: Complete Bug Bounty Workflow

```bash
#!/bin/bash
TARGET_DOMAIN="acme-corp.com"
USER_EMAIL="hunter@example.com"
CERT_ID=""

# Step 1: Authorize scanning for this program
CERT_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/kai/authorize \
  -d "authorization_type=bug_bounty_platform" \
  -d "target=$TARGET_DOMAIN" \
  -d "authorized_by=$USER_EMAIL" \
  -d "methods=osint,vulnerability_scanning,web_testing")

CERT_ID=$(echo $CERT_RESPONSE | jq -r '.data.certificate_id')
echo "✅ Authorization created: $CERT_ID"

# Step 2: Run OSINT
echo "🔍 Starting OSINT reconnaissance..."
OSINT_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/kai/scan/osint \
  -d "user_id=$USER_EMAIL" \
  -d "target=$TARGET_DOMAIN")

SCAN_ID=$(echo $OSINT_RESPONSE | jq -r '.data.scan_id')
echo "OSINT scan ID: $SCAN_ID"

# Step 3: Run vulnerability scan
echo "🛡️  Starting vulnerability scan..."
VULN_RESPONSE=$(curl -s -X POST http://localhost:8000/api/v1/kai/scan/vulnerability \
  -d "user_id=$USER_EMAIL" \
  -d "target=$TARGET_DOMAIN" \
  -d "scan_type=bug_bounty")

VULN_SCAN_ID=$(echo $VULN_RESPONSE | jq -r '.data.scan_id')
echo "Vulnerability scan ID: $VULN_SCAN_ID"

# Step 4: Generate compliance report
echo "📊 Generating compliance report..."
REPORT=$(curl -s http://localhost:8000/api/v1/kai/compliance-report?days=1)

echo $REPORT | jq '.data.summary'

# Step 5: Download findings with audit trail
echo "📥 Retrieving audit-logged findings..."
curl -s http://localhost:8000/api/v1/kai/audit-logs?user_id=$USER_EMAIL | jq '.data.logs'
```

---

## Part 5: Compliance & Audit

### Viewing Audit Logs

```bash
# Get all audit logs for the last 30 days
curl http://localhost:8000/api/v1/kai/audit-logs

# Filter by specific user
curl http://localhost:8000/api/v1/kai/audit-logs?user_id=hunter@example.com

# Filter by specific time period
curl "http://localhost:8000/api/v1/kai/audit-logs?days=7"
```

### Security Alerts

```bash
# Check for suspicious activities
curl http://localhost:8000/api/v1/kai/security-alerts

# Response includes:
# - Repeated authorization failures
# - Rapid-fire scanning attempts
# - Out-of-scope targeting
# - Other anomalies
```

### Compliance Reports

```bash
# Generate compliance report
curl http://localhost:8000/api/v1/kai/compliance-report

# Report includes:
# - Scan summary (completed, failed, denied)
# - Security statistics
# - Alerts and recommendations
# - Complete audit trail
```

### Exporting for Audits

```bash
# Export 90 days of audit logs as JSON
curl http://localhost:8000/api/v1/kai/audit-logs?days=90 | jq . > kai-audit-90days.json

# Export compliance report
curl http://localhost:8000/api/v1/kai/compliance-report?days=90 | jq . > compliance-report.json
```

---

## Part 6: Deployment

### Deploy to Cloud Run

```bash
# Build and deploy using Cloud Build
gcloud builds submit \
  --config=cloudbuild-kai-secure.yaml \
  --project=$PROJECT_ID

# Monitor deployment
gcloud run services describe kai-security-engine \
  --region us-central1 \
  --project $PROJECT_ID
```

### Monitor Security

```bash
# View Cloud Logging for Kai
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=kai-security-engine" \
  --limit 50 \
  --format json

# View security alerts
gcloud monitoring policies list --filter='displayName:Kai'
```

### Health Checks

```bash
# Check Kai system health
curl https://kai-security-engine-<hash>.a.run.app/api/v1/kai/health

# Should return:
# {
#   "success": true,
#   "data": {
#     "status": "healthy",
#     "security_stats": {
#       "total_authorizations": 5,
#       "active_authorizations": 4,
#       "total_audit_logs": 128,
#       "blocked_operations": 2,
#       "suspicious_activities": 0
#     }
#   }
# }
```

---

## Part 7: Preventing Misuse

### Built-in Guardrails

**1. Authorization Required**
- Every scan requires a valid certificate
- Certificates expire and must be renewed
- Out-of-scope targets are automatically blocked

**2. Audit Trail**
- Every operation is logged
- User, time, IP address, method recorded
- Immutable log for compliance

**3. Anomaly Detection**
- Repeated authorization failures → flagged
- Rapid-fire scanning → rate limited
- Out-of-scope attempts → logged and blocked

**4. Prompt Injection Prevention**
- No user input directly in prompts
- Structured request validation
- LLM chains isolated from untrusted data

**5. Rate Limiting**
- Max 100 scans per hour per user
- Automatic backoff on failures
- Progressive delays for repeated attempts

### What Gets Blocked

```
❌ Scanning without authorization
❌ Scanning outside authorized scope
❌ Using methods not authorized
❌ Scanning after authorization expires
❌ Repeated failed authorization attempts
❌ Rapid-fire scanning (rate limited)
❌ Accessing restricted data
❌ Attempts to bypass guardrails
```

### What's Allowed

```
✅ OSINT on public information
✅ Vulnerability scanning on authorized targets
✅ Security research within scope
✅ Bug bounty hunting on authorized programs
✅ Authorized penetration testing
✅ Internal security assessments
✅ Responsible disclosure
```

---

## Part 8: Support & Compliance

### Maintaining Compliance

```bash
# Regular compliance checks
1. Weekly: Review audit logs for anomalies
2. Monthly: Generate compliance reports
3. Quarterly: Review authorization certificates
4. Annually: Security audit of entire system
```

### Documentation

All scans must be documented with:
- ✅ Authorization certificate ID
- ✅ Scope of testing
- ✅ Scan type and methods
- ✅ Findings discovered
- ✅ Timestamps

### Questions?

- **Technical**: Check code comments in guardrails implementation
- **Authorization**: Review authorization certificates
- **Compliance**: Generate compliance report
- **Security Issues**: File a security report

---

## Quick Reference

| Operation | Command |
|-----------|---------|
| Create Authorization | `curl -X POST /api/v1/kai/authorize` |
| Start OSINT Scan | `curl -X POST /api/v1/kai/scan/osint` |
| Start Vulnerability Scan | `curl -X POST /api/v1/kai/scan/vulnerability` |
| View Audit Logs | `curl /api/v1/kai/audit-logs` |
| Check Security Alerts | `curl /api/v1/kai/security-alerts` |
| Generate Compliance Report | `curl /api/v1/kai/compliance-report` |
| Revoke Authorization | `curl -X POST /api/v1/kai/admin/revoke-authorization` |

---

**Kai: Enterprise-ready, compliant, and secure OSINT & vulnerability discovery.**

Version: 1.0 | Last Updated: 2026-02-02
