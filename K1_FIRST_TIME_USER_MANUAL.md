# Kaison K1 - First Time User Manual

**Your First Steps to Unified OSINT & Vulnerability Discovery**

Welcome to Kaison K1! This guide will walk you through getting started in the first 30 minutes.

---

## Table of Contents

1. [System Requirements](#system-requirements)
2. [Installation (5 minutes)](#installation)
3. [Initial Setup (10 minutes)](#initial-setup)
4. [Your First Scan (10 minutes)](#your-first-scan)
5. [Understanding Results (5 minutes)](#understanding-results)
6. [Next Steps](#next-steps)

---

## System Requirements

### Minimum (Local Development)
- **CPU**: 2 cores
- **RAM**: 4GB
- **Storage**: 10GB
- **OS**: Windows, macOS, or Linux

### Recommended (Production)
- **CPU**: 4+ cores
- **RAM**: 8GB+
- **Storage**: 50GB+
- **OS**: Ubuntu 20.04 LTS or similar

### For Cloud Deployment (GCP)
- GCP Account with billing enabled
- gcloud CLI installed
- Cloud Run, Cloud Build, Secret Manager, KMS enabled

---

## Installation

### Step 1: Clone Repository (30 seconds)

```bash
# Clone the repository
git clone https://github.com/kaison-ai/kaison-k1.git
cd Kaison_Latest_Build

# List what you have
ls -la
```

**You should see:**
- `apps/` - Frontend and backend
- `config/` - Configuration files
- `docs/` - Documentation
- `scripts/` - Setup scripts

### Step 2: Install Dependencies (2 minutes)

```bash
# Install Python dependencies (backend)
cd apps/backend
pip install -r requirements.txt

# Install JavaScript dependencies (frontend)
cd ../frontend
npm install

# Go back to root
cd ../..
```

**What this does:**
- Python packages for API, LLM, tools, embeddings
- Node packages for React dashboard

### Step 3: Set Environment Variables (1 minute)

```bash
# Create .env file
cp apps/backend/.env.example apps/backend/.env

# Edit with your settings
nano apps/backend/.env  # or use your editor

# Minimal required:
export ANTHROPIC_API_KEY=your-claude-key
export DATABASE_URL=sqlite:///./k1.db
export DEBUG_MODE=true
```

### Step 4: Verify Installation (1.5 minutes)

```bash
# Test backend
cd apps/backend
python -c "from src.main import app; print('✅ Backend OK')"

# Test frontend
cd ../frontend
npm run build
echo "✅ Frontend OK"

echo ""
echo "🎉 Installation complete!"
```

---

## Initial Setup

### Step 1: Start Backend (2 minutes)

**Terminal 1:**
```bash
cd apps/backend
python -m uvicorn src.main:app --reload --port 8000
```

**You should see:**
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

### Step 2: Initialize Tools (3 minutes)

**Terminal 2:**
```bash
cd apps/backend
python scripts/init_k1_system.py --init-embeddings
```

**This will:**
- Load all 5 tools (Finding Validator, Quick Classifier, etc.)
- Initialize embeddings system (OpenAI + local)
- Create vector store
- Display system statistics

**Expected output:**
```
==== K1 SYSTEM INITIALIZATION SUMMARY ====
Tool Registry ............................ ✅ READY
Embeddings System ....................... ✅ READY
Program Discovery ...................... ✅ READY
Tool Demonstrations .................... ✅ READY
==== K1 System Initialization Complete! ====
```

### Step 3: Start Frontend (2 minutes)

**Terminal 3:**
```bash
cd apps/frontend
npm run dev
```

**You should see:**
```
VITE v... ready in ... ms

➜ Local:   http://localhost:5173/
```

### Step 4: Access Dashboard (1 minute)

Open your browser to: **http://localhost:5173**

You should see:
- **Kaison K1** header (green branding)
- **Overview** tab selected
- System stats showing:
  - 5 Tools Deployed
  - Programs Available
  - Active Authorizations

**Congratulations! System is running!** 🎉

---

## Your First Scan

### Step 1: Create Authorization (5 minutes)

K1 requires explicit authorization before scanning. This proves you have permission.

**Open Dashboard → Security Tab → Create Authorization**

Or use the API:

```bash
curl -X POST http://localhost:8000/api/v1/kai/authorize \
  -H "Content-Type: application/json" \
  -d '{
    "authorization_type": "bug_bounty_platform",
    "target": "example.com",
    "authorized_by": "your-email@example.com",
    "duration_days": 365,
    "scope": "domain_wildcard",
    "methods": "osint,vulnerability_scanning,web_testing"
  }'
```

**Response will include:**
```json
{
  "success": true,
  "data": {
    "certificate_id": "550e8400-e29b-41d4-a716-446655440000",
    "authorization_type": "bug_bounty_platform",
    "target": "example.com",
    "expires_at": "2027-02-02T00:00:00",
    "allowed_methods": ["osint", "vulnerability_scanning", "web_testing"]
  }
}
```

**Save the certificate_id!** You'll need it to verify the scan later.

### Step 2: Run OSINT Scan (3 minutes)

OSINT (Open Source Intelligence) gathers public information about your target.

**Dashboard → Tools → Click "Execute" on Quick Classifier**

Or via API:

```bash
curl -X POST http://localhost:8000/api/v1/kai/scan/osint \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your-email@example.com",
    "target": "example.com"
  }'
```

**Response:**
```json
{
  "success": true,
  "data": {
    "scan_id": "scan-12345",
    "target": "example.com",
    "status": "started",
    "certificate_id": "550e8400-...",
    "message": "OSINT scan started on example.com"
  }
}
```

### Step 3: View Results (2 minutes)

```bash
# View audit logs
curl http://localhost:8000/api/v1/kai/audit-logs \
  ?user_id=your-email@example.com

# View security alerts
curl http://localhost:8000/api/v1/kai/security-alerts

# View compliance report
curl http://localhost:8000/api/v1/kai/compliance-report
```

---

## Understanding Results

### Dashboard Interpretation

**Overview Tab:**
- **5 Tools Deployed**: Quick Classifier, Finding Validator, Vulnerability Analyzer, Chain Analyzer, Program Matcher
- **Active Authorizations**: Shows how many valid certificates you have
- **Recent Scans**: Count of scans this period

**Tools Tab:**
- Shows each available tool
- Tool category (validation, analysis, etc.)
- Usage count
- Last used date

**Programs Tab:**
- Available bug bounty programs
- Platform (HackerOne, Bugcrowd, etc.)
- Maximum payout
- Filter options

**Security Tab:**
- Authorization status breakdown
- Audit logs viewer
- Compliance report generator
- Security features list

### API Response Interpretation

**Successful Authorization:**
```
success: true
certificate_id: Unique ID for this authorization
expires_at: When this certificate expires
allowed_methods: What you can do with this authorization
```

**Successful Scan:**
```
status: "started" (scan is queued)
scan_id: Unique ID to track this scan
certificate_id: Links scan to authorization proof
```

**Audit Log Entry:**
```
user_id: Who performed the action
timestamp: When it happened
target: What was scanned
method: How it was scanned (osint, vulnerability_scanning, etc.)
status: Result (completed, failed, denied)
certificate_id: Authorization proof
```

---

## Troubleshooting First Run

### Problem: "Backend fails to start"

**Solution:**
```bash
# Check Python version (must be 3.9+)
python --version

# Check dependencies
pip list | grep anthropic

# Reinstall dependencies
rm -rf venv
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

### Problem: "Frontend shows "Connection refused"

**Solution:**
```bash
# Check backend is running (should be on port 8000)
curl http://localhost:8000/health

# If not running, restart:
cd apps/backend
python -m uvicorn src.main:app --reload --port 8000
```

### Problem: "Authorization fails with "No API key provided"

**Solution:**
```bash
# Check environment variable
echo $ANTHROPIC_API_KEY

# If empty, set it:
export ANTHROPIC_API_KEY=sk-ant-your-key-here

# Or add to .env file:
echo "ANTHROPIC_API_KEY=sk-ant-your-key-here" >> apps/backend/.env
```

### Problem: "Tools not loading in dashboard"

**Solution:**
```bash
# Reinitialize system
cd apps/backend
python scripts/init_k1_system.py

# Check tools are registered
curl http://localhost:8000/api/v1/tools
```

---

## Next Steps

### 1. Read the Complete User Manual
See `K1_LONG_TERM_USER_MANUAL.md` for:
- Advanced tool configuration
- Multi-tool workflows
- Performance optimization
- Troubleshooting guide

### 2. Try Your First Complete Workflow

```bash
#!/bin/bash
TARGET="example.com"
USER="your-email@example.com"

# Step 1: Authorize
CERT=$(curl -s -X POST http://localhost:8000/api/v1/kai/authorize \
  -d "authorization_type=bug_bounty_platform" \
  -d "target=$TARGET" \
  -d "authorized_by=$USER" \
  -d "methods=osint,vulnerability_scanning")

CERT_ID=$(echo $CERT | jq -r '.data.certificate_id')
echo "✅ Authorization: $CERT_ID"

# Step 2: Run OSINT
OSINT=$(curl -s -X POST http://localhost:8000/api/v1/kai/scan/osint \
  -d "user_id=$USER" \
  -d "target=$TARGET")

SCAN_ID=$(echo $OSINT | jq -r '.data.scan_id')
echo "✅ OSINT Scan: $SCAN_ID"

# Step 3: View results
curl -s http://localhost:8000/api/v1/kai/audit-logs?user_id=$USER | jq '.data.logs[0]'

echo ""
echo "🎉 First scan complete!"
```

### 3. Explore Tools

Try each tool:
```bash
# Quick Classifier (fast, auto)
curl -X POST http://localhost:8000/api/v1/tools/quick_classifier/execute \
  -d '{"finding_text": "XSS in login form"}'

# Finding Validator (deep reasoning)
curl -X POST http://localhost:8000/api/v1/tools/finding_validator/execute \
  -d '{"finding_title": "XSS", "finding_description": "...", "asset_type": "web"}'
```

### 4. Set Up Bug Bounty Programs

```bash
# List available programs
curl http://localhost:8000/api/v1/programs

# Scrape new programs
curl -X POST http://localhost:8000/api/v1/programs/scrape/google_vrp

# Match programs to findings
curl 'http://localhost:8000/api/v1/programs/match?finding_title=XSS&finding_scope=example.com&severity=high'
```

### 5. Deploy to Cloud (Optional)

When ready to go production:
```bash
# Read deployment guide
cat KAI_SECURITY_SETUP_GUIDE.md

# Deploy to GCP Cloud Run
gcloud builds submit --config=cloudbuild-kai-secure.yaml
```

---

## Common First-Time Questions

**Q: Is K1 ready for production use?**
A: Yes! Phases 7a-7c are production-ready. Follow `KAI_SECURITY_SETUP_GUIDE.md` for enterprise deployment.

**Q: What if I don't have ANTHROPIC_API_KEY?**
A: System will fall back to local embeddings (slower but works offline).

**Q: Can I scan without authorization?**
A: No. K1 requires explicit authorization certificates for security compliance.

**Q: Is my data secure?**
A: Yes. All operations are logged immutably and can be audited. See `KAI_SECURITY_IMPLEMENTATION_SUMMARY.md`.

**Q: Where can I find more help?**
A: Check:
- This manual (first time setup)
- `K1_LONG_TERM_USER_MANUAL.md` (advanced features)
- `KAI_SECURITY_SETUP_GUIDE.md` (security/compliance)
- Code comments (implementation details)

---

## You're Ready!

You now have:
- ✅ K1 installed and running locally
- ✅ Backend API operational
- ✅ Frontend dashboard accessible
- ✅ Tools initialized and ready
- ✅ Your first authorization certificate
- ✅ Successfully run an OSINT scan
- ✅ Viewed results in the dashboard

**Next:** Follow `K1_LONG_TERM_USER_MANUAL.md` to unlock advanced features and optimize your workflow.

---

**Questions?** Check the documentation or review code comments for implementation details.

**Need help?** All API endpoints have complete error messages. Check the response for guidance.

**Ready for more?** You've completed first-time setup. Welcome to Kaison K1! 🚀

---

**Time Elapsed**: ~30 minutes | **Status**: ✅ COMPLETE
