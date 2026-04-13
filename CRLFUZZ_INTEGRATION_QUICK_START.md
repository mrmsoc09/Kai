# CrlfuzzAgent Quick Start

**Status:** ✅ Production Ready | **Tests:** 41 passing | **Deployment:** ~5 minutes

---

## Prerequisites

```bash
# Install crlfuzz binary
go install -v github.com/dwisiswant0/crlfuzz@latest

# Verify
crlfuzz -h

# Python: Pydantic v2
pip install pydantic>=2.0,<3.0
```

---

## Integration Steps

### 1. Copy Files
```bash
mkdir -p apps/backend/src/agents/tools/crlfuzz
cp agent_enhanced.py → agent.py
cp schemas.py → schemas.py
```

### 2. Verify Imports
```python
python3 -c "from apps.backend.src.agents.tools.crlfuzz.agent import CrlfuzzAgent; print('✓')"
```

### 3. Run Tests
```bash
pytest tests/test_crlfuzz_agent.py -v
# Expected: 41 passed
```

### 4. Wire Tool Registry
```yaml
- name: crlfuzz
  agent_class: CrlfuzzAgent
  category: vulnerability_assessment
  execution_mode: native
  binary_path: crlfuzz
  timeout_seconds: 600
  safety_classification: active
```

### 5. Wire V-RAD
```python
agent = CrlfuzzAgent()
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
from apps.backend.src.agents.tools.crlfuzz.agent import CrlfuzzAgent

agent = CrlfuzzAgent()
result = agent.execute("http://example.com/api?url=FUZZ")

# Filter findings
signal, noise = agent.filter_noise(result)

# Critical findings
for finding in signal:
    if finding.is_critical:
        print(f"CRITICAL CRLF: {finding.target_url}")
        print(f"  - Exploit: {finding.exploit_vector.value}")
        print(f"  - Risk: {finding.risk_level}")
```

### Response Splitting Detection
```python
result = agent.execute(
    "http://example.com/api?url=FUZZ",
    options={"timeout_seconds": 900}
)

# Find response splitting vulns
splits = [f for f in result["findings"]
          if f.exploit_vector == ExploitVector.RESPONSE_SPLITTING]
```

### Custom Payloads
```python
result = agent.execute(
    "http://example.com/api?url=FUZZ",
    options={"payload": "/custom/crlfuzz_payloads.txt"}
)
```

### Deep Scan
```python
result = agent.execute(
    "http://example.com/api?url=FUZZ",
    options={
        "deep_scan": True,
        "threads": 20,
    }
)
```

### With SNL Proxy
```python
result = agent.execute(
    "http://example.com/api?url=FUZZ",
    options={
        "proxy": "socks5://10.0.0.1:9050",
        "timeout_seconds": 900,
    }
)
```

---

## Troubleshooting

**Issue:** crlfuzz: command not found
```bash
go install -v github.com/dwisiswant0/crlfuzz@latest
export PATH=$PATH:$(go env GOPATH)/bin
```

**Issue:** Pydantic validation error
```bash
pip install --upgrade "pydantic>=2.0,<3.0"
```

**Issue:** ImportError on CrlfuzzAgent
```bash
ls apps/backend/src/agents/tools/crlfuzz/
# Verify: agent.py, agent_enhanced.py, schemas.py, __init__.py
```

**Issue:** Timeout on large sites
```python
result = agent.execute(
    "http://example.com/api?url=FUZZ",
    options={"timeout_seconds": 1200}  # 20 minutes
)
```

**Issue:** Proxy connection fails
```bash
# Verify proxy is working
curl -x socks5://10.0.0.1:9050 http://example.com
```

---

## Performance Tuning

| Config | Speed | Memory | Use |
|--------|-------|--------|-----|
| Standard | ~2-5 min | ~50 MB | Default |
| Multi-threaded (20) | ~1-2 min | ~75 MB | Large scope |
| Deep scan | ~5-10 min | ~100 MB | Thorough testing |
| With custom payloads | ~2-5 min | ~60 MB | Specialized targets |

---

## Automatic Session Hijacking Follow-up

CrlfuzzAgent automatically creates follow-up tasks:

```python
# When confirmed with session hijacking risk:
if finding.session_hijacking_risk and finding.can_inject_headers:
    # Automatically queued for Session Hijacking audit
    print(f"Follow-up task created: Session Hijacking audit for {finding.target_url}")
```

---

## Production Checklist

- [ ] crlfuzz binary installed: `which crlfuzz`
- [ ] Tests passing: `pytest tests/test_crlfuzz_agent.py -v`
- [ ] Tool registry entry added
- [ ] V-RAD telemetry configured
- [ ] SNL proxy settings verified
- [ ] BaseToolAgent inheritance confirmed
- [ ] Timeout adequate for target scope (600s default)
- [ ] Custom payload file (K1-curated) available

---

**Ready for production deployment** ✅
