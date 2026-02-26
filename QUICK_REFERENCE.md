# K1 Platform - Quick Reference Card

## 🚀 Quick Start (2 minutes)

```bash
# 1. Install dependencies
pip install -r apps/backend/requirements.txt

# 2. Set environment
export ANTHROPIC_API_KEY=your-key

# 3. Start backend
cd apps/backend && python -m uvicorn src.main:app --reload

# 4. In another terminal, initialize system
python scripts/init_k1_system.py

# Done! Visit http://localhost:8000/api/v1/tools
```

---

## 📋 Available Tools

| Tool | Purpose | Speed | Approval |
|------|---------|-------|----------|
| Quick Classifier | Categorize findings | <1s | Auto |
| Finding Validator | Deep validation | 15-20s | Required |
| Vulnerability Analyzer | Context analysis | 15-20s | Required |
| Chain Analyzer | Attack chains | 15-30s | Required |
| Program Matcher | Smart targeting | 2-3s | Required |

---

## 🌐 Available Programs

| Platform | Max Payout | Payouts |
|----------|-----------|---------|
| Google VRP | $100K | $100-100K |
| Microsoft | $250K | $2K-250K |
| Meta | $50K | $1K-50K |
| Apple | $200K | $5K-200K |
| AWS | $50K | $1K-50K |

---

## 🔧 API Quick Examples

### List Tools
```bash
curl http://localhost:8000/api/v1/tools
```

### Execute Tool
```bash
curl -X POST http://localhost:8000/api/v1/tools/quick_classifier/execute \
  -H "Content-Type: application/json" \
  -d '{
    "finding_text": "SQL injection in search"
  }'
```

### List Programs
```bash
curl http://localhost:8000/api/v1/programs
```

### Match Programs
```bash
curl 'http://localhost:8000/api/v1/programs/match?finding_title=RCE&finding_scope=google.com&severity=critical'
```

### Scrape Programs
```bash
curl -X POST http://localhost:8000/api/v1/programs/scrape/google_vrp
```

---

## 🎨 Branding

**Primary Color**: Deep Forest Green `#1a472a`
**Secondary Color**: Deep Orange `#d4571e`

**Location**:
- Backend: `configs/branding.yaml`
- Frontend: `apps/frontend/src/theme/branding.ts` and `.css`

---

## 📁 Key Files

| File | Purpose |
|------|---------|
| `apps/backend/src/core/llm_client.py` | LLM abstraction |
| `apps/backend/src/core/tools.py` | Tool framework |
| `apps/backend/src/routers/tools.py` | Tools API |
| `apps/backend/src/routers/programs_discovery.py` | Programs API |
| `UNIFIED_K1_PLATFORM_GUIDE.md` | Full documentation |
| `PHASE_7_IMPLEMENTATION_STATUS.md` | Implementation details |

---

## ⚙️ Configuration

```bash
# LLM Provider (pick one)
export ANTHROPIC_API_KEY=your-key     # Claude (recommended)
export OPENAI_API_KEY=your-key        # GPT (for embeddings)

# Database
export DATABASE_URL=postgresql://...

# Optional
export DEBUG_MODE=true
export REDIS_URL=redis://localhost:6379
```

---

## 📊 Tool Autonomy Tiers

- **TIER 0 (Auto)**: Executes immediately, no approval needed
- **TIER 1 (Notify)**: Sends notification only
- **TIER 2 (Approve)**: Requires human approval before execution
- **TIER 3 (Hard Stop)**: Explicit user confirmation required

---

## 🔗 Tool Chaining Example

```bash
curl -X POST http://localhost:8000/api/v1/tools/orchestrate \
  -H "Content-Type: application/json" \
  -d '{
    "steps": [
      {"tool_id": "quick_classifier", "params": {"finding_text": "RCE"}},
      {"tool_id": "vulnerability_analyzer", "params": {"vulnerability_type": "rce", ...}},
      {"tool_id": "program_matcher", "params": {"finding_title": "RCE", ...}}
    ]
  }'
```

---

## 🧠 Embeddings System

**Primary**: OpenAI (3072 dims, high accuracy)
**Fallback**: Local Sentence-Transformers (384 dims)

Automatically switches to fallback if OpenAI unavailable.

---

## 📈 Performance Targets

| Operation | Target | Status |
|-----------|--------|--------|
| Quick Classification | <1s | ✅ |
| Program Listing | <500ms | ✅ |
| Program Matching | 2-3s | ✅ |
| Deep Analysis | 15-20s | ✅ |
| Embeddings | 50-500ms | ✅ |

---

## 🐛 Health Checks

```bash
# Tools system
curl http://localhost:8000/api/v1/tools/health

# Programs system
curl http://localhost:8000/api/v1/programs/health

# Main app
curl http://localhost:8000/health
```

---

## 📚 Documentation

- **Full Guide**: `UNIFIED_K1_PLATFORM_GUIDE.md`
- **Implementation**: `PHASE_7_IMPLEMENTATION_STATUS.md`
- **Delivery Summary**: `PHASE_7_DELIVERY_SUMMARY.md`
- **This Card**: `QUICK_REFERENCE.md`

---

## 🚀 Next Steps

1. **Initialize System**: `python scripts/init_k1_system.py`
2. **Test Tools**: `curl http://localhost:8000/api/v1/tools`
3. **Scrape Programs**: `curl -X POST http://localhost:8000/api/v1/programs/scrape-all`
4. **Read Full Guide**: `UNIFIED_K1_PLATFORM_GUIDE.md`

---

## 💡 Tips

**For Development**:
- Set `DEBUG_MODE=true` for verbose logging
- Use `--reload` flag on uvicorn for auto-reload
- Check `init_k1_system.py` for system verification

**For Production**:
- Use PostgreSQL instead of in-memory cache
- Set up pgvector for production embeddings
- Configure Redis for caching and job queue
- Use environment variables for all secrets

**For Customization**:
- Edit `configs/branding.yaml` to change colors
- Add new tools by extending `BaseTool` class
- Add scrapers by extending `BaseProgramScraper` class
- Customize LLM provider in `llm_client.py`

---

## 🆘 Common Issues

**Issue**: "OPENAI_API_KEY not provided"
**Fix**: Set `export OPENAI_API_KEY=your-key` or embeddings will use local fallback

**Issue**: "Tool not found"
**Fix**: Run `python scripts/init_k1_system.py` to initialize tool registry

**Issue**: "Program scraping fails"
**Fix**: Check internet connectivity; scrapers are async but need network

**Issue**: "Slow embeddings"
**Fix**: Likely using local fallback; set `OPENAI_API_KEY` for faster OpenAI embeddings

---

## 📞 Support

**Issues**: Check `UNIFIED_K1_PLATFORM_GUIDE.md` FAQ section
**Code**: Fully commented with type hints
**API Docs**: Available at `/api/v1/tools` endpoints
**Examples**: See `api usage examples` in this card

---

**Version**: 7.0 - AI-Active Multi-Agent System
**Status**: ✅ Production Ready (Phases 7a-7c)
**Last Updated**: 2026-02-02
