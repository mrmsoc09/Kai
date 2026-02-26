# Kaison K1: Unified AI-Active Platform

## Executive Summary

Kaison K1 is now a **unified, AI-active multi-agent system** with integrated tools, neural intelligence, and autonomous workflows. This document explains the current capabilities and how to use them.

**Current Status**: Phase 7a-7c COMPLETE (Phases 7d-7f in progress)

---

## What's Inside

### 1. Unified Tool Framework ✅

A complete system for creating, managing, and orchestrating AI-powered tools with autonomy tiers and human-in-the-loop approval workflows.

**5 Core Tools Deployed:**
- **Finding Validator**: 5-step deep reasoning validation (TIER 2 - HiL approval)
- **Quick Classifier**: Fast finding categorization (TIER 0 - automatic)
- **Vulnerability Analyzer**: Comprehensive context analysis (TIER 2)
- **Chain Analyzer**: Multi-step attack detection (TIER 2)
- **Program Matcher**: Intelligent program targeting (TIER 2)

**Key Features:**
- Tool schema generation for LLM function calling
- Autonomy tier gating (TIER 0-3)
- Built-in metrics and statistics
- Streaming execution support
- Background async execution
- Tool result serialization and storage-ready

### 2. Program Discovery System ✅

Automated discovery and scraping of 50+ bug bounty programs with payout estimation.

**5 Platforms Supported:**
- Google VRP (up to $100K payouts)
- Microsoft MSRC (up to $250K payouts)
- Meta/Facebook (up to $50K payouts)
- Apple Security Bounty (up to $200K payouts)
- AWS Security (up to $50K payouts)

**Capabilities:**
- Async scraping with progress streaming
- Scope management (allowed/excluded items)
- Payout estimation by severity
- Program filtering and matching
- Real-time program matching for findings
- Extensible scraper architecture

### 3. Neural RAG System ✅

Hybrid retrieval-augmented generation with OpenAI embeddings and local fallback.

**Features:**
- OpenAI text-embedding-3-large (3072 dims) as primary
- Local Sentence-Transformers (384 dims) as fallback
- Automatic provider switching on failure
- Cosine similarity search
- Metadata-based filtering
- Batch embedding operations
- Production-ready for pgvector

### 4. Unified Branding ✅

Consistent visual identity across entire platform.

**Design System:**
- Primary color: Deep forest green (#1a472a)
- Secondary color: Deep orange (#d4571e)
- Full color palette with semantic meanings
- Global CSS variables for consistency
- React TypeScript theme constants
- Responsive design system
- Professional typography scale
- Component library ready

---

## Quick Start Guide

### Installation

```bash
# 1. Install backend dependencies
cd apps/backend
pip install -r requirements.txt

# 2. Install optional ML packages (recommended)
pip install openai sentence-transformers

# 3. Install frontend dependencies
cd ../frontend
npm install

# 4. Copy .env and configure
cp .env.example .env
# Edit .env with your API keys
```

### Environment Setup

```bash
# Required for LLM clients
export ANTHROPIC_API_KEY=your-claude-key
export OPENAI_API_KEY=your-openai-key  # Optional (for OpenAI, embeddings)

# Required for database
export DATABASE_URL=postgresql://user:pass@localhost/k1

# Optional but recommended
export DEBUG_MODE=true
export K1_DEV_TOKEN=dev-token-123
```

### Running the System

**Terminal 1 - Backend:**
```bash
cd apps/backend
python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd apps/frontend
npm run dev
```

**Terminal 3 (optional) - Initialize System:**
```bash
cd apps/backend
python scripts/init_k1_system.py --init-embeddings --scrape-programs
```

---

## API Usage Examples

### Tool Operations

**List all tools:**
```bash
curl http://localhost:8000/api/v1/tools
```

**Get tool details:**
```bash
curl http://localhost:8000/api/v1/tools/finding_validator
```

**Execute a tool (with auto approval):**
```bash
curl -X POST http://localhost:8000/api/v1/tools/quick_classifier/execute \
  -H "Content-Type: application/json" \
  -d '{
    "finding_text": "SQL injection in user search"
  }'
```

**Execute tool requiring approval:**
```bash
curl -X POST http://localhost:8000/api/v1/tools/finding_validator/execute \
  -H "Content-Type: application/json" \
  -d '{
    "finding_title": "XSS in Comment Form",
    "finding_description": "User input not escaped",
    "asset_type": "web",
    "estimated_severity": "high"
  }'
# Returns: {"execution_id": "...", "status": "pending_approval"}

# Approve execution
curl -X POST http://localhost:8000/api/v1/tools/finding_validator/approve \
  ?execution_id=... \
  ?user_id=admin
```

**Execute tool workflow (chaining):**
```bash
curl -X POST http://localhost:8000/api/v1/tools/orchestrate \
  -H "Content-Type: application/json" \
  -d '{
    "steps": [
      {
        "tool_id": "quick_classifier",
        "params": {"finding_text": "RCE in API"}
      },
      {
        "tool_id": "vulnerability_analyzer",
        "params": {
          "vulnerability_type": "rce",
          "affected_technology": "Node.js API",
          "attack_description": "...",
          "exploitation_difficulty": "easy"
        }
      },
      {
        "tool_id": "program_matcher",
        "params": {
          "finding_title": "RCE in API",
          "finding_scope": "*.example.com",
          "severity": "critical"
        }
      }
    ]
  }'
```

### Program Operations

**List programs:**
```bash
curl 'http://localhost:8000/api/v1/programs?limit=20&min_payout=1000'
```

**Get program details:**
```bash
curl http://localhost:8000/api/v1/programs/google_vrp_main
```

**Start scraping:**
```bash
curl -X POST http://localhost:8000/api/v1/programs/scrape/google_vrp

# Check status
curl http://localhost:8000/api/v1/programs/scrape-status/google_vrp_1706808123
```

**Stream scrape (Server-Sent Events):**
```bash
curl http://localhost:8000/api/v1/programs/scrape/stream/microsoft \
  --header "Accept: text/event-stream"
```

**Match programs to finding:**
```bash
curl 'http://localhost:8000/api/v1/programs/match?finding_title=RCE&finding_scope=api.company.com&severity=critical'
```

**Get statistics:**
```bash
curl http://localhost:8000/api/v1/programs/statistics
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React/TS)                     │
│              Branding: theme/branding.ts/.css               │
│           Components: Tools UI, Programs UI, Workflows       │
└────────────────────┬────────────────────────────────────────┘
                     │ REST/WebSocket
┌────────────────────▼────────────────────────────────────────┐
│                  FastAPI Backend (Python)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Tool Routers │  │ Program API  │  │ Embeddings   │       │
│  ├──────────────┤  ├──────────────┤  │ API (future) │       │
│  │ Validators   │  │ Scrapers     │  └──────────────┘       │
│  │ Analyzers    │  │ Discovery    │                          │
│  │ Orchestration│  │ Matching     │                          │
│  └──────────────┘  └──────────────┘                          │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Core Systems                            │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐    │   │
│  │  │LLM Client│ │Tool Frame│ │Embeddings Client│    │   │
│  │  │(OpenAI, │ │(Registry,│ │(OpenAI + Local) │    │   │
│  │  │Anthropic)│ │Registry) │ │Vector Store     │    │   │
│  │  └──────────┘ └──────────┘ └──────────────────┘    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Middleware: Security Headers | CSRF | Rate Limit | CORS    │
└────────────────────┬─────────────────────────────────────────┘
                     │ SQL/Redis
┌────────────────────▼────────────────────────────────────────┐
│              Data Layer                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │PostgreSQL│  │ pgvector │  │  Redis   │                  │
│  │Findings  │  │Embeddings│  │Caching   │                  │
│  │Programs  │  │          │  │Job Queue │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

---

## Tool Development Guide

### Creating a New Tool

```python
from src.core.tools import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolResult,
    ToolStatus,
    ToolAutonomyTier,
    register_tool,
)

class MyCustomTool(BaseTool):
    def __init__(self):
        parameters = [
            ToolParameter(
                name="input_param",
                type="string",
                description="Input parameter",
                required=True,
            ),
        ]

        super().__init__(
            id="my_custom_tool",
            name="My Custom Tool",
            description="Does something useful",
            category=ToolCategory.ANALYSIS,  # Pick appropriate category
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,  # Or TIER_0_AUTO
            parameters=parameters,
            version="1.0.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        import time
        start_time = time.time()

        try:
            # Validate inputs
            is_valid, error = self.validate_parameters(**kwargs)
            if not is_valid:
                return ToolResult(
                    tool_id=self.id,
                    status=ToolStatus.FAILED,
                    output=None,
                    error=error,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            # Your business logic here
            result = my_logic(kwargs.get("input_param"))

            # Record execution
            self.record_execution(...)

            return ToolResult(
                tool_id=self.id,
                status=ToolStatus.COMPLETED,
                output=result,
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            return ToolResult(
                tool_id=self.id,
                status=ToolStatus.FAILED,
                output=None,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

# Register the tool
register_tool(MyCustomTool())
```

---

## Branding Customization

### Backend Branding (`configs/branding.yaml`)
- Color scheme definitions
- Typography scale
- Spacing constants
- Component styles
- API response styling

### Frontend Branding (`apps/frontend/src/theme/`)

**TypeScript Constants (`branding.ts`):**
```typescript
import { COLORS, UI, COMPONENT_STYLES } from '@/theme/branding'

// Use in components
const buttonStyle = COMPONENT_STYLES.button.primary
const primaryColor = COLORS.primary.main
```

**CSS Variables (`branding.css`):**
```css
/* Use in CSS */
button {
  background-color: var(--color-primary-main);
  color: var(--color-primary-contrast);
  padding: var(--spacing-md);
  border-radius: var(--border-radius-medium);
}
```

### Customizing Colors

Edit `configs/branding.yaml`:
```yaml
colors:
  primary:
    main: "#1a472a"      # Change to your color
    light: "#2d7a47"
    lighter: "#45a369"
    contrast: "#ffffff"
```

Then run:
```bash
# CSS variables auto-generate from YAML
npm run generate-theme-css
```

---

## Performance Optimization

### Tool Execution
- **TIER 0 (Auto)**: <1 second (no approval)
- **TIER 1 (Notify)**: 1-3 seconds (notification only)
- **TIER 2 (Approve)**: 15-20 seconds (deep reasoning DeepAgents)
- **TIER 3 (Hard Stop)**: Variable (requires explicit approval)

### Embeddings
- **OpenAI**: 200-500ms per request (high accuracy)
- **Local**: 50-100ms per request (lower accuracy)
- **Hybrid**: Automatic failover from OpenAI to local

### Program Matching
- First request: 2-3 seconds (scrapes if needed)
- Cached: <500ms (subsequent requests)

---

## Deployment Guide

### Docker

```dockerfile
# Docker build in progress for unified container

FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY apps/backend ./apps/backend
COPY apps/frontend/dist ./apps/frontend/dist
COPY configs ./configs

CMD ["python", "-m", "uvicorn", "apps.backend.src.main:app", \
     "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables for Production

```bash
# LLM
K1_PROVIDER_PREFERRED=anthropic
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Database
DATABASE_URL=postgresql://user:pass@host:5432/k1
DATABASE_POOL_SIZE=20

# Cache
REDIS_URL=redis://host:6379/0

# Security
K1_DEV_TOKEN=disabled
CORS_ALLOWED_ORIGINS=https://yourdomain.com

# Observability
LANGSMITH_API_KEY=...
LOG_LEVEL=INFO
```

---

## What's Next (Phases 7d-7f)

### Phase 7d: DAG Orchestration (In Progress)
- Parallel task execution with dependencies
- Conditional branching
- Workflow composition
- Error recovery and retry logic

### Phase 7e: Intelligent Agent Routing (Planned)
- Task classification engine
- Dynamic agent selection
- Confidence-based escalation
- Self-adaptive routing

### Phase 7f: Advanced Detection (Planned)
- Fuzzing module
- Pattern detection
- Code analysis
- Full LangSmith integration
- Comprehensive documentation

---

## Support and Documentation

**Key Files:**
- `PHASE_7_IMPLEMENTATION_STATUS.md` - Detailed implementation status
- `configs/branding.yaml` - Brand configuration
- `apps/backend/scripts/init_k1_system.py` - System initialization
- `apps/frontend/src/theme/branding.ts` - Frontend branding

**API Documentation:**
- Tools API: `GET /api/v1/tools`
- Programs API: `GET /api/v1/programs`
- Health checks: `GET /health` and `/api/v1/tools/health`

**Community & Support:**
- GitHub Issues: Report bugs and request features
- Documentation: See docs/ folder
- Contributing: Follow the development guide

---

## FAQ

**Q: Can I use my own LLM provider?**
A: Yes! Edit `src/core/llm_client.py` to add new providers. The factory pattern makes it easy.

**Q: How do I add programs from other platforms?**
A: Create a scraper in `src/core/program_scrapers.py` and register it with `ScraperFactory`.

**Q: What's the difference between TIER 0 and TIER 2?**
A: TIER 0 (auto) executes immediately. TIER 2 (approve) requires human-in-the-loop approval before execution.

**Q: Can I use local embeddings only?**
A: Yes, set `OPENAI_API_KEY` to empty and the system will automatically use local embeddings.

**Q: How do I scale this to multiple workers?**
A: Deploy multiple backend instances with shared PostgreSQL and Redis. The architecture is stateless.

---

## License

Kaison K1 - Unified Bug Bounty Intelligence Platform

---

**Status**: ✅ Production Ready (Phases 7a-7c) | 🔄 In Development (Phases 7d-7f)

**Last Updated**: 2026-02-02

**Version**: 7.0 - AI-Active Multi-Agent System
