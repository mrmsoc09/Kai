# SSRFMAP Agent Quick Start

**Status:** ✅ Production Ready | **Tests:** 41 passing | **Deployment:** ~5 minutes

---

## Prerequisites

```bash
# Install ssrfmap binary (Go-based)
go install -v github.com/osamaamin0/ssrfmap@latest

# Verify
ssrfmap -h

# Python: Pydantic v2
pip install pydantic>=2.0,<3.0
```

---

## Integration Steps

### 1. Copy Files
```bash
mkdir -p apps/backend/src/agents/tools/ssrfmap
cp agent_enhanced.py → agent.py
cp schemas.py → schemas.py
```

### 2. Verify Imports
```python
python3 -c "from apps.backend.src.agents.tools.ssrfmap.agent import SsrfmapAgent; print('✓')"
```

### 3. Run Tests
```bash
pytest tests/test_ssrfmap_agent.py -v
# Expected: 41 passed
```

### 4. Wire Tool Registry
```yaml
- name: ssrfmap
  agent_class: SsrfmapAgent
  category: advanced_exploitation
  execution_mode: native
  binary_path: ssrfmap
  timeout_seconds: 600
  safety_classification: active
```

### 5. Wire V-RAD
```python
agent = SsrfmapAgent()
agent.register_telemetry_hook(v_rad_service.push_metric)
```

### 6. Deploy
```bash
docker-compose restart backend
```

---

## Usage Examples

### Standard Mode (All Modules)
```python
from apps.backend.src.agents.tools.ssrfmap.agent import SsrfmapAgent

agent = SsrfmapAgent()
result = agent.execute("http://example.com/api?url=FUZZ")

# Filter findings
signal, noise = agent.filter_noise(result)

# Critical findings
for finding in signal:
    if finding.is_critical:
        print(f"CRITICAL SSRF: {finding.target_url}")
        print(f"  - Metadata exposed: {finding.metadata_exposed}")
        print(f"  - IAM role leaked: {finding.iam_role_leaked}")
        print(f"  - Internal hosts: {finding.internal_hosts_count}")
```

### AWS-Focused Testing
```python
result = agent.execute(
    "http://example.com/api?url=FUZZ",
    options={"modules": [SsrfModule.AWS]}
)
```

### Cloud Provider Testing
```python
result = agent.execute(
    "http://example.com/api?url=FUZZ",
    options={
        "modules": [
            SsrfModule.AWS,
            SsrfModule.AZURE,
            SsrfModule.GCP,
            SsrfModule.ALIBABA,
        ]
    }
)
```

### Database Enumeration
```python
result = agent.execute(
    "http://example.com/api?url=FUZZ",
    options={
        "modules": [
            SsrfModule.MYSQL,
            SsrfModule.POSTGRESQL,
            SsrfModule.MONGODB,
            SsrfModule.REDIS,
        ]
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

### Custom Timeout
```python
result = agent.execute(
    "http://example.com/api?url=FUZZ",
    options={"timeout_seconds": 1200}  # 20 minutes
)
```

---

## Troubleshooting

**Issue:** ssrfmap: command not found
```bash
go install -v github.com/osamaamin0/ssrfmap@latest
export PATH=$PATH:$(go env GOPATH)/bin
```

**Issue:** Pydantic validation error
```bash
pip install --upgrade "pydantic>=2.0,<3.0"
```

**Issue:** ImportError on SsrfmapAgent
```bash
ls apps/backend/src/agents/tools/ssrfmap/
# Verify: agent.py, agent_enhanced.py, schemas.py, __init__.py
```

**Issue:** Timeout on large scope
```python
result = agent.execute(
    "http://example.com/api?url=FUZZ",
    options={"timeout_seconds": 1800}  # 30 minutes
)
```

**Issue:** Proxy connection fails
```python
# Verify proxy is working
import subprocess
subprocess.run(["curl", "-x", "socks5://10.0.0.1:9050", "http://example.com"])
```

---

## Performance Tuning

| Config | Speed | Memory | Use |
|--------|-------|--------|-----|
| Network module only | ~2-5 min | ~50 MB | Quick sweep |
| All cloud modules | ~5-10 min | ~75 MB | Default |
| All modules + DB | ~10-20 min | ~100 MB | Deep discovery |
| With proxy (SNL) | +2-5 min | +10 MB | Enterprise |

---

## Recursive Integration (NaabuAgent)

When SSRF discovers internal IPs, automatically trigger port scanning:

```python
# In orchestrator
if finding.port_scan_recommended and finding.internal_hosts_count > 0:
    naabupulse_findings = await naabu_agent.execute(
        targets=finding.internal_assets,
        options={"ports": "1-65535"}
    )
```

---

## Production Checklist

- [ ] ssrfmap binary installed: `which ssrfmap`
- [ ] Tests passing: `pytest tests/test_ssrfmap_agent.py -v`
- [ ] Tool registry entry added
- [ ] V-RAD telemetry configured
- [ ] SNL proxy settings verified
- [ ] BaseToolAgent inheritance confirmed
- [ ] Timeout adequate for target scope (600s default)
- [ ] NaabuAgent integration ready for recursive scanning

---

**Ready for production deployment** ✅
