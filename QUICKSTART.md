# Kaison K1 - Quick Start Guide

**Get Kaison K1 running in 5 minutes**

This guide gets you from zero to a fully operational Kaison K1 instance with all components integrated and working together.

---

## System Verification

Before starting, verify your system meets minimum requirements:

```bash
# Check Python version (3.9+)
python --version

# Check Node.js version (16+)
node --version
npm --version

# Check git
git --version
```

**Need help?** See [HARDWARE_REQUIREMENTS.md](./HARDWARE_REQUIREMENTS.md) for detailed specs.

---

## Installation (3 minutes)

### 1. Clone & Navigate

```bash
git clone https://github.com/kaison-ai/kaison-k1.git
cd Kaison_Latest_Build
```

### 2. Install Dependencies

**Backend:**
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python packages
pip install -r requirements.txt
```

**Frontend:**
```bash
cd apps/frontend
npm install
cd ../..
```

### 3. Configure Environment

```bash
# Backend configuration
cp apps/backend/.env.example apps/backend/.env

# Edit with your settings
nano apps/backend/.env  # or your preferred editor

# Minimal required variables:
# ANTHROPIC_API_KEY=sk-ant-your-key
# DATABASE_URL=sqlite:///./k1.db
# DEBUG_MODE=true
```

---

## Quick Start (2 minutes)

### Terminal 1: Backend API

```bash
cd apps/backend
python -m uvicorn src.main:app --reload --port 8000
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

### Terminal 2: Frontend UI

```bash
cd apps/frontend
npm run dev
```

Expected output:
```
VITE v... ready in ... ms
➜ Local:   http://localhost:5173/
```

### Open Browser

Navigate to: **http://localhost:5173**

You should see:
- **Kaison K1** header with green branding
- **Dashboard** tab showing system overview
- Status indicator showing "System Healthy"

**Congratulations! You're running K1!** ✅

---

## First Scan (Optional - 2 minutes)

### Create Authorization

```bash
# Create permission certificate for authorized scanning
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

Response:
```json
{
  "success": true,
  "data": {
    "certificate_id": "550e8400-e29b-41d4-a716-446655440000",
    "authorization_type": "bug_bounty_platform",
    "target": "example.com",
    "expires_at": "2027-02-02T00:00:00"
  }
}
```

### Run OSINT Scan

```bash
curl -X POST http://localhost:8000/api/v1/kai/scan/osint \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your-email@example.com",
    "target": "example.com"
  }'
```

### View Results

```bash
# Check audit logs
curl http://localhost:8000/api/v1/kai/audit-logs \
  ?user_id=your-email@example.com
```

---

## Troubleshooting

### Backend won't start

```bash
# Check Python version
python --version  # Must be 3.9+

# Check packages
pip list | grep -E "fastapi|anthropic|sqlalchemy"

# Reinstall dependencies
rm -rf venv
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Frontend shows "Connection refused"

```bash
# Verify backend is running
curl http://localhost:8000/health

# Should return: {"status":"ok"}

# If not running, restart from Terminal 1
```

### Missing API keys

```bash
# Check ANTHROPIC_API_KEY
echo $ANTHROPIC_API_KEY

# If empty, add to .env file
echo "ANTHROPIC_API_KEY=sk-ant-your-key" >> apps/backend/.env

# Restart backend
```

### Tools not appearing in dashboard

```bash
cd apps/backend
python scripts/init_k1_system.py

# Restart backend and refresh browser
```

---

## Next Steps

1. **Read Full Manuals:**
   - [K1 First Time User Manual](./K1_FIRST_TIME_USER_MANUAL.md) - Setup & basics
   - [K1 Long Term User Manual](./K1_LONG_TERM_USER_MANUAL.md) - Advanced features

2. **Deploy to Production:**
   - See [KAI_SECURITY_SETUP_GUIDE.md](./KAI_SECURITY_SETUP_GUIDE.md)

3. **Explore Tools:**
   - View available tools in Dashboard → Tools tab
   - Execute tools via API: `/api/v1/tools`

4. **Configure Programs:**
   - Dashboard → Programs tab
   - Add bug bounty programs for targeting

---

## Key Features

✅ **5 Integrated Tools**
- Quick Classifier (auto classification)
- Finding Validator (deep analysis)
- Vulnerability Analyzer (technical assessment)
- Chain Analyzer (multi-step attacks)
- Program Matcher (payout optimization)

✅ **Security Guardrails**
- Authorization certificates (proof of permission)
- Immutable audit logs (compliance)
- Rate limiting (abuse prevention)
- Anomaly detection (suspicious activity)

✅ **Multi-Platform**
- Supports Anthropic Claude, OpenAI GPT, Google Gemini
- Automatic failover between LLM providers
- Hybrid embeddings (online + offline)

✅ **Enterprise Ready**
- Production-grade deployment on GCP Cloud Run
- Encryption with Google Cloud KMS
- Compliance reporting (SOC2, GDPR, HIPAA)

---

## API Documentation

**Available at:** http://localhost:8000/docs

Auto-generated interactive documentation using FastAPI/Swagger UI.

### Key Endpoints

- `POST /api/v1/kai/authorize` - Create authorization certificate
- `POST /api/v1/kai/scan/osint` - Start OSINT reconnaissance
- `POST /api/v1/kai/scan/vulnerability` - Start vulnerability scan
- `GET /api/v1/tools` - List available tools
- `GET /api/v1/programs` - List bug bounty programs
- `GET /api/v1/kai/audit-logs` - View audit trail

---

## Community & Support

- **Issues:** [GitHub Issues](https://github.com/kaison-ai/kaison-k1/issues)
- **Discussions:** [GitHub Discussions](https://github.com/kaison-ai/kaison-k1/discussions)
- **Documentation:** This repository

---

## Ready to Go!

You now have a fully operational Kaison K1 instance running locally with:

✅ Backend API with all security features
✅ Frontend dashboard with unified branding
✅ 5 integrated tools
✅ Authorization and audit systems
✅ Multi-LLM provider support

**Start exploring:** http://localhost:5173

---

**Questions?** Check the full manuals or open an issue on GitHub.

**Environment Variables Cheat Sheet:**

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-your-key

# Database
DATABASE_URL=sqlite:///./k1.db

# Debugging
DEBUG_MODE=true

# Optional LLM providers
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...

# Advanced (see full manual)
REDIS_URL=redis://localhost:6379
LOG_LEVEL=info
```

---

**Time:** ~5 minutes | **Status:** ✅ READY TO USE

