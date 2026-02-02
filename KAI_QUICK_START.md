# Kai Security Quick Start (10 minutes)

---

## For Local Development

### 1. Start Backend with Kai Security

```bash
cd apps/backend

# Install dependencies (if not already done)
pip install -r requirements.txt

# Run the backend (includes Kai security endpoints)
python -m uvicorn src.main:app --reload --port 8000
```

### 2. Create Authorization Certificate

```bash
# Register to scan a domain (HackerOne program)
curl -X POST http://localhost:8000/api/v1/kai/authorize \
  -d 'authorization_type=bug_bounty_platform' \
  -d 'target=example.com' \
  -d 'authorized_by=you@example.com' \
  -d 'methods=osint,vulnerability_scanning,web_testing'

# Response will include certificate_id like:
# "certificate_id": "550e8400-e29b-41d4-a716-446655440000"
```

### 3. Start Authorized Scanning

```bash
# OSINT scan (public information only)
curl -X POST http://localhost:8000/api/v1/kai/scan/osint \
  -d 'user_id=you@example.com' \
  -d 'target=example.com'

# Vulnerability scan (if authorized)
curl -X POST http://localhost:8000/api/v1/kai/scan/vulnerability \
  -d 'user_id=you@example.com' \
  -d 'target=example.com' \
  -d 'scan_type=bug_bounty'
```

### 4. Check Audit Trail

```bash
# View all your scans
curl http://localhost:8000/api/v1/kai/audit-logs?user_id=you@example.com

# Generate compliance report
curl http://localhost:8000/api/v1/kai/compliance-report
```

---

## For GCP Deployment

### Prerequisites

```bash
# Install gcloud CLI
gcloud --version  # Must be >= 400

# Authenticate
gcloud auth login
gcloud config set project YOUR-PROJECT-ID
```

### 1. Run Setup Script

```bash
# Run all GCP setup (creates KMS, secrets, service account, etc.)
bash scripts/setup-kai-gcp.sh

# This will:
# - Create service account
# - Set up KMS keys
# - Create Secret Manager entries
# - Create Artifact Registry
# - Create BigQuery dataset
# - Apply IAM policy
```

### 2. Deploy to Cloud Run

```bash
# Deploy using secure Cloud Build pipeline
gcloud builds submit \
  --config=cloudbuild-kai-secure.yaml \
  --project=$(gcloud config get-value project)
```

### 3. Test Deployment

```bash
# Get Cloud Run URL
SERVICE_URL=$(gcloud run services describe kai-security-engine \
  --region us-central1 \
  --format 'value(status.url)')

# Check health
curl $SERVICE_URL/api/v1/kai/health
```

### 4. Create Authorization

```bash
# Use the same authorization creation as local
curl -X POST $SERVICE_URL/api/v1/kai/authorize \
  -d 'authorization_type=bug_bounty_platform' \
  -d 'target=example.com' \
  -d 'authorized_by=you@example.com' \
  -d 'methods=osint,vulnerability_scanning,web_testing'
```

---

## Common Operations

### List Active Authorizations

```bash
curl http://localhost:8000/api/v1/kai/authorizations
```

### Revoke Authorization (Admin)

```bash
curl -X POST http://localhost:8000/api/v1/kai/admin/revoke-authorization \
  -d 'certificate_id=550e8400-e29b-41d4-a716-446655440000' \
  -d 'revoked_by=admin@example.com' \
  -d 'reason=Testing complete'
```

### Export Audit Logs

```bash
# Export as JSON
curl http://localhost:8000/api/v1/kai/audit-logs?days=30 | jq . > audit-30days.json

# Export as CSV (pipe through jq)
curl http://localhost:8000/api/v1/kai/audit-logs?days=30 | \
  jq -r '.data.logs[] | [.user_id, .timestamp, .target, .status] | @csv' > audit.csv
```

---

## Troubleshooting

### Authorization Denied

**Problem**: "No valid authorization found for target"

**Solution**:
1. Verify certificate is registered: `curl /api/v1/kai/authorizations`
2. Check target matches: Certificate scope must include your target
3. Check methods: Method must be in allowed_methods
4. Check expiration: Certificate must not be expired

### Scan Blocked

**Problem**: "Scan denied"

**Solution**:
1. Check audit logs: `curl /api/v1/kai/audit-logs`
2. Look for "denied" status entries
3. Check error_message field
4. Create new authorization if expired

### Cloud Run Deployment Fails

**Problem**: Build fails with secret errors

**Solution**:
1. Verify secrets exist: `gcloud secrets list | grep kai-`
2. Verify service account has access: `gcloud secrets get-iam-policy kai-authorization-certs`
3. Check KMS keys exist: `gcloud kms keys list --location us-central1 --keyring kai-keyring`

---

## Example: Complete Bug Bounty Workflow

```bash
#!/bin/bash
set -e

TARGET="example.com"
USER_EMAIL="hunter@example.com"

echo "🚀 Kai Bug Bounty Workflow"
echo "========================"

# Step 1: Authorize
echo "1️⃣  Creating authorization for $TARGET..."
CERT=$(curl -s -X POST http://localhost:8000/api/v1/kai/authorize \
  -d "authorization_type=bug_bounty_platform" \
  -d "target=$TARGET" \
  -d "authorized_by=$USER_EMAIL" \
  -d "methods=osint,vulnerability_scanning,web_testing")

CERT_ID=$(echo $CERT | jq -r '.data.certificate_id')
echo "✅ Certificate created: $CERT_ID"

# Step 2: OSINT
echo ""
echo "2️⃣  Running OSINT reconnaissance..."
OSINT=$(curl -s -X POST http://localhost:8000/api/v1/kai/scan/osint \
  -d "user_id=$USER_EMAIL" \
  -d "target=$TARGET")

OSINT_SCAN=$(echo $OSINT | jq -r '.data.scan_id')
echo "✅ OSINT scan: $OSINT_SCAN"

# Step 3: Vulnerability Scan
echo ""
echo "3️⃣  Running vulnerability scan..."
VULN=$(curl -s -X POST http://localhost:8000/api/v1/kai/scan/vulnerability \
  -d "user_id=$USER_EMAIL" \
  -d "target=$TARGET" \
  -d "scan_type=bug_bounty")

VULN_SCAN=$(echo $VULN | jq -r '.data.scan_id')
echo "✅ Vulnerability scan: $VULN_SCAN"

# Step 4: View Results
echo ""
echo "4️⃣  Viewing audit logs..."
curl -s http://localhost:8000/api/v1/kai/audit-logs?user_id=$USER_EMAIL | \
  jq '.data.logs | map({timestamp, scan_type, target, status})'

# Step 5: Generate Report
echo ""
echo "5️⃣  Generating compliance report..."
curl -s http://localhost:8000/api/v1/kai/compliance-report | \
  jq '.data.summary'

echo ""
echo "✅ Workflow complete! All operations are audited and compliant."
```

Save as `kai-workflow.sh` and run:
```bash
chmod +x kai-workflow.sh
./kai-workflow.sh
```

---

## API Reference

| Operation | Endpoint | Method |
|-----------|----------|--------|
| Create Authorization | `/api/v1/kai/authorize` | POST |
| List Authorizations | `/api/v1/kai/authorizations` | GET |
| Start OSINT Scan | `/api/v1/kai/scan/osint` | POST |
| Start Vuln Scan | `/api/v1/kai/scan/vulnerability` | POST |
| View Audit Logs | `/api/v1/kai/audit-logs` | GET |
| Check Security Alerts | `/api/v1/kai/security-alerts` | GET |
| Compliance Report | `/api/v1/kai/compliance-report` | GET |
| Revoke Authorization | `/api/v1/kai/admin/revoke-authorization` | POST |

---

## Next Steps

1. **Read Full Guide**: `KAI_SECURITY_SETUP_GUIDE.md`
2. **Understanding Security**: `KAI_SECURITY_IMPLEMENTATION_SUMMARY.md`
3. **Production Deploy**: Follow GCP setup in full guide
4. **Integration**: Integrate with K1 tools and K-9 components

---

**Kai: Enterprise OSINT & Vulnerability Scanning** | v1.0 | 2026-02-02
