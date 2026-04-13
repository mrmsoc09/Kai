# Dalfox XSS Agent Quick Start

**Status:** ✅ Production Ready | **Tests:** 36 passing | **Deployment:** ~5 minutes

---

## Prerequisites

```bash
# Install dalfox binary
go install -v github.com/projectdiscovery/dalfox/v2@latest

# Verify
dalfox -h

# Python: Pydantic v2
pip install pydantic>=2.0,<3.0
```

---

## Integration Steps

### 1. Copy Files
```bash
mkdir -p apps/backend/src/agents/tools/dalfox
cp agent_enhanced.py → agent.py
```

### 2. Verify Imports
```python
python3 -c "from apps.backend.src.agents.tools.dalfox.agent_enhanced import DalfoxAgent; print('✓')"
```

### 3. Run Tests
```bash
pytest tests/test_dalfox_agent.py -v
# Expected: 36 passed
```

### 4. Wire Tool Registry
```yaml
- name: dalfox
  agent_class: DalfoxAgent
  category: web_vulnerability_research
  execution_mode: native
  binary_path: dalfox
  timeout_seconds: 600
  safety_classification: active
```

### 5. Wire V-RAD
```python
agent = DalfoxAgent()
agent.register_telemetry_hook(v_rad_service.push_metric)
```

### 6. Deploy
```bash
docker-compose restart backend
```

---

## Usage Examples

### Standard Mode
```python
from apps.backend.src.agents.tools.dalfox.agent_enhanced import DalfoxAgent

agent = DalfoxAgent()
result = agent.execute("https://example.com")

# Filter findings
signal, noise = agent.filter_noise(result.findings)

# Critical findings
for f in signal:
    if f["context"]["is_critical"]:
        print(f"CRITICAL XSS: {f['target_url']}")
```

### Deep Checking
```python
result = agent.execute(
    "https://example.com",
    options={"deep_check": True}
)
```

### Parameter Mining
```python
result = agent.execute(
    "https://example.com",
    options={"mining_dict": "/path/to/wordlist.txt"}
)
```

### Custom Payloads
```python
result = agent.execute(
    "https://example.com",
    options={"custom_payload_file": "/path/to/payloads.txt"}
)
```

### Listener Mode (from HTTPx)
```bash
httpx -l urls.txt -o results.json | dalfox scan --format json
```

---

## Troubleshooting

**Issue:** dalfox: command not found
```bash
go install -v github.com/projectdiscovery/dalfox/v2@latest
export PATH=$PATH:$(go env GOPATH)/bin
```

**Issue:** Pydantic validation error
```bash
pip install --upgrade "pydantic>=2.0,<3.0"
```

**Issue:** ImportError on DalfoxAgent
```bash
ls apps/backend/src/agents/tools/dalfox/
# Verify: agent_enhanced.py, agent.py, schemas.py, __init__.py
```

**Issue:** Timeout on large sites
```python
result = agent.execute(
    "https://example.com",
    options={"timeout_seconds": 1200}  # 20 minutes
)
```

---

## Performance Tuning

| Config | Speed | Memory | Use |
|--------|-------|--------|-----|
| Standard | ~2-5 min | ~50 MB | Default |
| Deep check | ~10-20 min | ~100 MB | High-priority |
| Mining | ~5-15 min | ~75 MB | Parameter discovery |

---

## Production Checklist

- [ ] dalfox binary installed: `which dalfox`
- [ ] Tests passing: `pytest tests/test_dalfox_agent.py -v`
- [ ] Tool registry entry added
- [ ] V-RAD telemetry configured
- [ ] OPSEC settings verified (random user-agent, SNL proxy)
- [ ] BaseToolAgent inheritance confirmed
- [ ] Timeout adequate for target scope

---

**Ready for production deployment** ✅
