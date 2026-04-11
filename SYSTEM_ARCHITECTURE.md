# Kaison K1 - System Architecture & Integration Guide

**Comprehensive overview of how K1 components integrate into a unified platform**

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      KAISON K1 UNIFIED PLATFORM                 │
│                                                                   │
│ ┌────────────────────────────┐    ┌─────────────────────────┐   │
│ │   Frontend Dashboard       │    │   Backend API Server    │   │
│ │   (React + TypeScript)     │    │   (FastAPI + Python)    │   │
│ │                            │    │                         │   │
│ │ - Overview Tab             │    │ ┌───────────────────┐   │   │
│ │ - Tools Tab                │◄──►│ │ Security Layer    │   │   │
│ │ - Programs Tab             │    │ │ • Authorization   │   │   │
│ │ - Security Tab             │    │ │ • Audit Logging   │   │   │
│ │                            │    │ │ • Rate Limiting   │   │   │
│ │ Unified Branding:          │    │ └───────────────────┘   │   │
│ │ • Primary: Forest Green    │    │                         │   │
│ │ • Secondary: Deep Orange   │    │ ┌───────────────────┐   │   │
│ │ • Responsive CSS Variables │    │ │ Tool Framework    │   │   │
│ └────────────────────────────┘    │ │ • Registry        │   │   │
│                                     │ │ • Execution Ctx   │   │   │
│                                     │ │ • Result Metrics  │   │   │
│                                     │ └───────────────────┘   │   │
│                                     │                         │   │
│                                     │ ┌───────────────────┐   │   │
│                                     │ │ LLM Abstraction   │   │   │
│                                     │ │ • Claude (Primary)│   │   │
│                                     │ │ • OpenAI GPT      │   │   │
│                                     │ │ • Google Gemini   │   │   │
│                                     │ │ • Auto-failover   │   │   │
│                                     │ └───────────────────┘   │   │
│                                     │                         │   │
│                                     │ ┌───────────────────┐   │   │
│                                     │ │ 5 Core Tools      │   │   │
│                                     │ │ • Classifier      │   │   │
│                                     │ │ • Validator       │   │   │
│                                     │ │ • Analyzer        │   │   │
│                                     │ │ • Chain Builder   │   │   │
│                                     │ │ • Program Matcher │   │   │
│                                     │ └───────────────────┘   │   │
│                                     │                         │   │
│                                     │ ┌───────────────────┐   │   │
│                                     │ │ Data Layer        │   │   │
│                                     │ │ • PostgreSQL      │   │   │
│                                     │ │ • Redis Cache     │   │   │
│                                     │ │ • Vector DB       │   │   │
│                                     │ └───────────────────┘   │   │
│                                     └─────────────────────────┘   │
│                                                                   │
│ ┌────────────────────────────────────────────────────────────┐  │
│ │                  Integration Points                        │  │
│ │                                                            │  │
│ │ • REST API: /api/v1/kai/* (Authorization & Scanning)     │  │
│ │ • REST API: /api/v1/tools/* (Tool Execution)             │  │
│ │ • REST API: /api/v1/programs/* (Program Discovery)       │  │
│ │ • WebSocket: Real-time updates and streaming             │  │
│ │ • Server-Sent Events: Scan progress and results          │  │
│ │                                                            │  │
│ └────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Integration Details

### 1. Frontend Dashboard Integration

**Location:** `apps/frontend/src/components/Dashboard.tsx`

**Purpose:** Unified interface for all K1 operations

**Key Features:**

| Feature | Implementation | Branding |
|---------|---|---|
| **Overview Tab** | System stats cards | Green primary color |
| **Tools Tab** | Tool grid with execution | Orange accents |
| **Programs Tab** | Searchable programs | Secondary styling |
| **Security Tab** | Auth status, audit logs | Status indicators |

**Data Flow:**

```
User Action
    ↓
React Component
    ↓
API Fetch (axios)
    ↓
Backend /api/v1/* endpoints
    ↓
Business Logic Layer
    ↓
Database Query
    ↓
Response JSON
    ↓
Component State Update
    ↓
UI Re-render
```

**Styling System:**

```css
/* Unified through CSS variables */
--color-primary-main: #1a472a        /* Forest Green */
--color-secondary-main: #d4571e      /* Deep Orange */
--color-status-success: #22c55e       /* Bright Green */
--color-status-error: #ef4444         /* Red */
```

### 2. Backend API Architecture

**Location:** `apps/backend/src/main.py`

**Entry Point:** FastAPI application with middleware stack

**Middleware Stack (Order Matters):**

```
1. CORS Middleware (outermost) - Browser cross-origin requests
2. Rate Limiting - Abuse prevention
3. CSRF Protection - Form tampering prevention
4. Security Headers - Browser security policies
5. Business Logic (innermost) - Route handlers
```

**Router Organization:**

```
/api/v1/
├── kai/                          # Security & Authorization
│   ├── authorize                 # Create permission certificate
│   ├── scan/osint                # Start reconnaissance
│   ├── scan/vulnerability        # Start vulnerability scan
│   ├── audit-logs                # View audit trail
│   ├── security-alerts           # Suspicious activity
│   └── compliance-report         # Compliance documentation
│
├── tools/                        # Tool Execution
│   ├── quick_classifier          # Fast classification
│   ├── finding_validator         # Deep validation
│   ├── vulnerability_analyzer    # Technical analysis
│   ├── chain_analyzer            # Multi-step attacks
│   └── program_matcher           # Payout optimization
│
├── programs/                     # Program Management
│   ├── (list programs)
│   ├── scrape/google_vrp         # Google VRP scraper
│   ├── scrape/microsoft          # Microsoft MSRC
│   ├── scrape/meta               # Meta VDP
│   ├── scrape/apple              # Apple Security
│   └── scrape/amazon             # AWS VRP
│
└── [other routes]               # Supporting endpoints
```

### 3. Security Layer Integration

**Location:** `apps/backend/src/core/kai_security_guardrails.py`

**Core Components:**

#### Authorization System

```python
class AuthorizationCertificate:
    """
    Cryptographic proof of authorized scanning

    Components:
    - certificate_id (UUID)
    - authorization_type (e.g., bug_bounty_platform)
    - target (domain or scope)
    - authorized_by (person/email)
    - expires_at (expiration date)
    - allowed_methods (osint, vulnerability_scanning, etc.)
    - scope (domain_wildcard, specific_hosts, etc.)
    """
```

**Flow:**

```
User Request
    ↓
Extract Certificate ID
    ↓
Validate Certificate
    ├─ Not expired?
    ├─ Method allowed?
    ├─ Target in scope?
    └─ Valid signature?
    ↓
[PASS] Execute scan
[FAIL] Deny request + Log anomaly
    ↓
Immutable Audit Log
```

#### Audit Logging

```python
class ScanAuditLog:
    """
    Immutable record of all operations

    Fields:
    - user_id (who)
    - timestamp (when)
    - ip_address (where from)
    - target (what)
    - method (osint/vulnerability_scanning)
    - certificate_id (proof)
    - status (completed/failed/denied)
    - result_summary (outcome)
    """
```

#### Anomaly Detection

```
Pattern Detection:
├─ 10+ auth failures in 5 min → Alert
├─ 20+ scans in 5 min → Alert
├─ Scan outside scope → Deny + Alert
├─ Expired certificate usage → Deny
└─ Same target multiple times → Log pattern
```

### 4. Tool Framework Integration

**Location:** `apps/backend/src/core/tools.py`

**Tool Execution Pipeline:**

```
Tool Invocation
    ↓
Check Authorization
    ↓
Get Tool from Registry
    ↓
Create ExecutionContext
    ├─ Check autonomy tier
    ├─ Load user preferences
    └─ Setup logging
    ↓
Execute Tool
    ├─ Initialize with inputs
    ├─ Call LLM (Claude/GPT/Gemini)
    ├─ Process results
    └─ Format output
    ↓
Generate Result
    ├─ Tool output
    ├─ Metrics (duration, tokens used)
    ├─ Reasoning trace
    └─ Evidence references
    ↓
Return ToolResult
    ├─ success: bool
    ├─ data: dict
    ├─ metrics: ToolMetrics
    └─ reasoning: str
```

**5 Core Tools Integrated:**

| Tool | Purpose | Autonomy | Speed |
|------|---------|----------|-------|
| Quick Classifier | Fast categorization | TIER 0 (Auto) | <1s |
| Finding Validator | Deep analysis | TIER 1 (Notify) | 10-30s |
| Vulnerability Analyzer | Technical assessment | TIER 1 (Notify) | 15-45s |
| Chain Analyzer | Attack chains | TIER 2 (Approval) | 20-60s |
| Program Matcher | Payout optimization | TIER 0 (Auto) | 5-15s |

### 5. LLM Abstraction Layer

**Location:** `apps/backend/src/core/llm_client.py`

**Provider Support:**

```
┌─ Claude (Anthropic) ─────────────┐
│                                   │
├─ GPT-4 (OpenAI)──────────┐       │
│                           │       │
│                     LLMClientFactory
│                           │       │
│         ┌─────────────────┘       │
│         ↓                         │
├─ Gemini (Google)                 │
│                                   │
└─ Fallback chain if primary fails ─┘

Auto-failover Logic:
1. Try primary provider (Claude)
2. If error/rate-limited → Try secondary (GPT-4)
3. If still failing → Try tertiary (Gemini)
4. If all fail → Return cached result or graceful degradation
```

**Integration with Tools:**

```python
# In any tool:
llm = LLMClientFactory.create_client()

# Auto-selects best provider:
response = await llm.complete(
    messages=[...],
    model="gpt-4-turbo",
    tools=[...]
)

# Handles failures transparently
```

### 6. Program Discovery Integration

**Location:** `apps/backend/src/core/program_scrapers.py` & `routers/programs_discovery.py`

**Multi-Platform Coverage:**

```
Program Discovery System
│
├─ Google VRP Scraper
│  └─ Scope: All Google products
│  └─ Payout: $100-$200,000+
│
├─ Microsoft MSRC Scraper
│  └─ Scope: Windows, Office, etc.
│  └─ Payout: $500-$250,000+
│
├─ Meta VDP Scraper
│  └─ Scope: Facebook, Instagram, WhatsApp
│  └─ Payout: $100-$10,000+
│
├─ Apple Security Scraper
│  └─ Scope: iOS, macOS, Safari
│  └─ Payout: $200-$200,000+
│
└─ Amazon VRP Scraper
   └─ Scope: AWS services
   └─ Payout: $100-$$15,000+
```

**Real-Time Scraping:**

```
User Request
    ↓
Start Scraper (async)
    ↓
Open Server-Sent Events (SSE)
    ↓
Scraper yields updates
    ├─ "Scraping Google VRP..."
    ├─ "Found 150 programs"
    ├─ "Processing scope..."
    └─ "Complete: 145 active"
    ↓
Frontend streams to browser
    ↓
Live progress update
```

### 7. Embeddings & Vector Search

**Location:** `apps/backend/src/core/embeddings_client.py`

**Hybrid Approach:**

```
Input Text
    ↓
├─ Try OpenAI Embeddings (3072 dims)
│  └─ $0.02 per 1M tokens
│
└─ Fallback: Local Sentence-Transformers (384 dims)
   └─ Offline capable, lower quality
    ↓
Vector Store
    ├─ In-memory storage with cosine similarity
    ├─ Metadata filtering
    └─ Fast retrieval
    ↓
Similarity Search
    └─ Find related findings/programs
```

**Use Cases:**

- **Program Matching:** Find relevant programs for findings
- **Finding Deduplication:** Detect duplicate submissions
- **Pattern Recognition:** Identify attack chains
- **Knowledge Retrieval:** Find similar past findings

### 8. Data Persistence

**Location:** Database layer + cache layer

**Storage Strategy:**

```
Primary Data (PostgreSQL)
├─ Authorization Certificates
├─ Scan Results
├─ Tool Outputs
├─ Programs Database
├─ User Profiles
└─ Audit Logs

Cache Layer (Redis)
├─ Active Authorizations
├─ Tool Results (TTL: 1 hour)
├─ Program Lists (TTL: 24 hours)
├─ Rate Limiting Counters
└─ Session Data

Vector Storage (In-Memory/Qdrant)
├─ Finding Embeddings
├─ Program Descriptions
└─ OSINT Knowledge Base
```

### 9. API Response Format

**Unified Response Structure:**

```json
{
  "success": true/false,
  "data": {
    /* Tool or operation specific data */
  },
  "metadata": {
    "timestamp": "2025-02-02T12:34:56Z",
    "execution_time_ms": 1234,
    "request_id": "req-uuid",
    "version": "7.0"
  },
  "errors": [
    {
      "code": "ERROR_CODE",
      "message": "Human readable error",
      "details": {}
    }
  ]
}
```

**Example Tool Response:**

```json
{
  "success": true,
  "data": {
    "tool_name": "quick_classifier",
    "input": "XSS in login form",
    "classification": {
      "type": "Cross-Site Scripting",
      "severity": "high",
      "confidence": 0.98
    },
    "reasoning": "Detected user input flowing to page output",
    "recommendations": [
      "Use output encoding",
      "Implement CSP headers"
    ]
  },
  "metadata": {
    "timestamp": "2025-02-02T12:34:56Z",
    "execution_time_ms": 342,
    "tokens_used": 156
  }
}
```

---

## Data Flow Examples

### Example 1: Create Authorization Certificate

```
Frontend Button Click
    ↓
POST /api/v1/kai/authorize
    {
      "authorization_type": "bug_bounty_platform",
      "target": "example.com",
      "authorized_by": "user@example.com",
      "duration_days": 365,
      "scope": "domain_wildcard"
    }
    ↓
Backend Handler (kai_authorized_scanning.py)
    ↓
1. Validate input
2. Generate certificate_id (UUID)
3. Create signature (HMAC)
4. Store in PostgreSQL
5. Cache in Redis
    ↓
Return Certificate
    {
      "certificate_id": "550e8400-e29b-41d4-a716-446655440000",
      "expires_at": "2026-02-02",
      "allowed_methods": [...]
    }
    ↓
Frontend Displays
    ├─ Certificate ID
    ├─ Expiration date
    └─ "Save for later" option
```

### Example 2: Execute Tool with Authorization

```
Frontend: Run Tool Button
    ↓
POST /api/v1/tools/quick_classifier/execute
    {
      "certificate_id": "550e8400-...",
      "user_id": "user@example.com",
      "finding": "XSS in search box"
    }
    ↓
Backend Authorization Check
    ├─ Lookup certificate in Redis
    ├─ Verify not expired
    ├─ Verify method allowed
    └─ Check scope (if applicable)
    ↓
Create ExecutionContext
    ├─ Set autonomy tier (TIER 0)
    └─ Initialize logging
    ↓
Get Tool from Registry
    └─ Load quick_classifier instance
    ↓
Initialize LLM Client
    ├─ Try Claude (Anthropic)
    └─ Auto-fallback if needed
    ↓
Execute Tool
    ├─ Call LLM with prompt
    ├─ Process response
    └─ Extract classification
    ↓
Generate Metrics
    ├─ Duration: 342ms
    ├─ Tokens: 156
    └─ LLM provider: anthropic
    ↓
Store Audit Log
    ├─ user_id, timestamp, method
    ├─ Input/output
    └─ certificate_id (proof)
    ↓
Return Result
    {
      "classification": "high severity XSS",
      "confidence": 0.98,
      "metrics": {...}
    }
    ↓
Frontend Updates
    ├─ Display classification
    ├─ Show confidence
    └─ Suggest recommendations
```

---

## File Structure & Organization

```
Kaison_Latest_Build/
├── apps/
│   ├── backend/
│   │   ├── src/
│   │   │   ├── main.py                          # Entry point
│   │   │   ├── core/
│   │   │   │   ├── llm_client.py               # LLM abstraction
│   │   │   │   ├── tools.py                    # Tool framework
│   │   │   │   ├── tools_validators.py         # Validation tools
│   │   │   │   ├── tools_analysis.py           # Analysis tools
│   │   │   │   ├── program_scrapers.py         # Program discovery
│   │   │   │   ├── embeddings_client.py        # Vector search
│   │   │   │   └── kai_security_guardrails.py  # Security engine
│   │   │   ├── routers/
│   │   │   │   ├── kai_authorized_scanning.py  # Authorization API
│   │   │   │   ├── tools.py                    # Tool execution API
│   │   │   │   ├── programs_discovery.py       # Program API
│   │   │   │   └── [other routers...]
│   │   │   ├── middleware/
│   │   │   │   ├── rate_limit.py              # Rate limiting
│   │   │   │   ├── csrf.py                    # CSRF protection
│   │   │   │   └── security_headers.py        # Security headers
│   │   │   └── config/
│   │   │       └── cors_config.py             # CORS setup
│   │   ├── requirements.txt                   # Python dependencies
│   │   └── Dockerfile
│   │
│   └── frontend/
│       ├── src/
│       │   ├── main.tsx                        # Entry point
│       │   ├── App.tsx                         # Router setup
│       │   ├── components/
│       │   │   ├── Dashboard.tsx               # Main dashboard
│       │   │   ├── Dashboard.css               # Dashboard styles
│       │   │   ├── Layout.tsx                  # Layout wrapper
│       │   │   └── [other components...]
│       │   ├── theme/
│       │   │   ├── branding.ts                 # Branding constants
│       │   │   ├── branding.css                # Branding styles
│       │   │   └── index.ts
│       │   ├── routes/
│       │   │   └── [route components...]
│       │   ├── pages/
│       │   │   └── [page components...]
│       │   ├── theme.css                       # Global theme
│       │   └── App.css
│       ├── package.json
│       ├── vite.config.ts
│       └── Dockerfile
│
├── config/
│   └── branding.yaml                          # Branding config
│
├── docs/
│   └── [documentation...]
│
├── README.md
├── QUICKSTART.md                               # 5-min setup
├── K1_FIRST_TIME_USER_MANUAL.md                # 30-min onboarding
├── K1_LONG_TERM_USER_MANUAL.md                 # Advanced guide
├── HARDWARE_REQUIREMENTS.md                    # System specs
├── DEPLOYMENT_GUIDE.md                         # Production deployment
├── SYSTEM_ARCHITECTURE.md                      # This file
├── requirements.txt                            # Python deps
└── docker-compose.yml
```

---

## Integration Checklist

When adding new components:

- [ ] **Backend:** Create router in `routers/`
- [ ] **Frontend:** Create component in `components/` or `routes/`
- [ ] **Branding:** Use CSS variables from `theme/branding`
- [ ] **Security:** Check `kai_security_guardrails.py` integration
- [ ] **API:** Follow `/api/v1/` response format
- [ ] **Documentation:** Update relevant manual
- [ ] **Tests:** Add unit tests for business logic
- [ ] **Deployment:** Update Docker files if needed

---

## Performance Optimization

### Caching Strategy

```
Frontend
├─ Tools list (cache 1 hour)
├─ Programs list (cache 24 hours)
└─ User preferences (cache session)

Backend Cache
├─ Authorizations (active set in Redis)
├─ Tool results (TTL 1 hour)
├─ LLM responses (semantically similar)
└─ Program metadata (updated daily)

Database
├─ Index on certificate_id
├─ Index on scan timestamp
├─ Index on user_id
└─ Index on target/scope
```

### Query Optimization

```sql
-- Fast authorization lookups
CREATE INDEX idx_cert_id ON authorizations(certificate_id);
CREATE INDEX idx_cert_expiry ON authorizations(expires_at);

-- Fast audit trail queries
CREATE INDEX idx_audit_user ON audit_logs(user_id, timestamp DESC);
CREATE INDEX idx_audit_target ON audit_logs(target);

-- Fast program searches
CREATE INDEX idx_program_status ON programs(status);
CREATE INDEX idx_program_platform ON programs(platform);
```

---

## Security Considerations

### Defense in Depth

1. **Authentication:** User login with JWT
2. **Authorization:** Certificate-based permission system
3. **Rate Limiting:** Prevent brute force attacks
4. **Audit Logging:** Track all operations immutably
5. **Anomaly Detection:** Flag suspicious patterns
6. **Encryption:** All data encrypted in transit & at rest
7. **Input Validation:** All inputs sanitized
8. **Output Encoding:** All outputs escaped

### Key Security Flows

**Authorization Flow:**
```
Request with cert → Validate signature → Check expiry →
Check scope → Check method → Allow/Deny → Log result
```

**Audit Flow:**
```
Operation → Generate immutable record → Store in DB →
Index for queries → Never modify/delete
```

---

## Next Steps

1. **Monitoring:** Setup alerting for anomalies
2. **Scaling:** Configure for horizontal scaling
3. **Integration:** Connect with external platforms
4. **Customization:** Extend tools for specific needs

See [DEPLOYMENT_GUIDE.md](./DEPLOYMENT_GUIDE.md) for production setup.

