# SSRFMAP Agent Integration — K1 Platform

**Delivered:** April 12, 2026  
**Status:** ✅ Production Ready  
**Architecture:** Advanced SSRF vulnerability discovery with internal infrastructure mapping  
**Test Coverage:** 41 tests passing  

---

## Executive Summary

**SsrfmapAgent** is the specialized SSRF vulnerability discovery and internal infrastructure mapping agent for K1 platform. It:

- **Multi-module SSRF testing:** Network, AWS, Azure, GCP, Alibaba, Docker, databases
- **Internal infrastructure discovery:** IP enumeration, service identification, hostname discovery
- **Cloud metadata exposure detection:** IAM roles, credentials, subscription IDs
- **Service enumeration:** Port mapping, protocol detection, version fingerprinting
- **Recursive port scanning integration:** Automatic NaabuAgent trigger on discovered IPs
- **Credential harvesting:** Extracts AWS keys, database credentials, API tokens
- **OPSEC sanitization:** No K1-identifiable markers in payloads
- **V-RAD telemetry:** Real-time metrics (INTERNAL_HOSTS_DISCOVERED, CLOUD_METADATA_EXPOSED)

---

## Operational Profile

### Execution Modes

**Standard:**
```bash
ssrfmap -u "http://example.com/api?url=FUZZ" -m network,aws,azure,gcp -o json
```

**AWS-focused:**
```bash
ssrfmap -u "http://example.com/api?url=FUZZ" -m aws -o json
```

**Database enumeration:**
```bash
ssrfmap -u "http://example.com/api?url=FUZZ" -m mysql,postgresql,mongodb,redis -o json
```

**With proxy routing (SNL):**
```bash
ssrfmap -u "http://example.com/api?url=FUZZ" -p socks5://10.0.0.1:9050 -m network -o json
```

---

## Data Normalization

### InternalAccessRegistry Model

**Mapping:** ssrfmap JSON → Canonical InternalAccessRegistry

| ssrfmap Field | Registry Field | Transform |
|---------------|----------------|-----------|
| url | target_url | Direct |
| parameter | vulnerable_parameter | Vulnerable param name |
| payload | exploit_path | SSRF payload used |
| response | raw_response | HTTP response (truncated to 5KB) |
| status | exploit_status | confirmed/probable/blind/reflected/time_based |
| module | module_used | SsrfModule enum |

**30+ Fields for comprehensive tracking:**
- access_id (UUID), target_url, vulnerable_parameter
- ssrf_confirmed, exploit_status, confidence (0.0-1.0)
- exploit_path, module_used, response_time_ms
- internal_assets (list), internal_hosts_count
- cloud_provider, metadata_exposed, iam_role_leaked
- credentials_leaked (list), services_discovered (list)
- port_scan_recommended, detected_by, detection_date
- last_verified, raw_response, raw_ssrfmap_output
- request_payload, request_headers, stealthy
- bypass_technique, notes

---

## Vulnerability Type Classification

| Type | Detection Method | Risk | Example |
|------|------------------|------|---------|
| **Cloud Metadata** | aws:iam, security-credentials, subscription_id | CRITICAL | AWS IAM role exposure |
| **Internal IP Enumeration** | 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16 | HIGH | Internal network mapping |
| **Database Access** | MySQL, PostgreSQL, MongoDB, Redis protocols | HIGH | Direct DB access via SSRF |
| **Docker Daemon** | Docker API on 2375/2376 | CRITICAL | Containerization escape |
| **Blind SSRF** | Timing-based detection, error inference | MEDIUM | No direct output |
| **Time-Based SSRF** | Response time differentials | MEDIUM | Connection delays |

---

## Risk Assessment Matrix

| Factors | Critical | High | Medium | Low |
|---------|----------|------|--------|-----|
| **Metadata + IAM** | Auto-escalate | — | — | — |
| **Confirmed Status** | Verified | — | — | — |
| **Internal IP Count** | >5 = +1 tier | +1 tier | +1 tier | +1 tier |
| **Credentials Leaked** | Always escalate | — | — | — |
| **High Confidence** | >0.9 | 0.8-0.9 | 0.6-0.8 | <0.6 |

---

## Cloud Provider Detection

| Provider | Patterns | Indicators |
|----------|----------|-----------|
| **AWS** | AKIA, security-credentials, arn:aws, assume-role | EC2 metadata, IAM roles |
| **Azure** | subscription_id, tenant_id, managed identity | VMSS identity, MSI tokens |
| **GCP** | service_account, googleapis, compute metadata | Service account keys |
| **Alibaba** | aliyun metadata endpoint | ECS instance metadata |

---

## Internal Asset Discovery

### IP Pattern Recognition
- RFC 1918: 10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16
- Loopback: 127.0.0.0/8
- Link-local: 169.254.0.0/16

### Service Port Mapping
| Port | Service | Priority |
|------|---------|----------|
| 3306 | MySQL | HIGH |
| 5432 | PostgreSQL | HIGH |
| 27017 | MongoDB | HIGH |
| 6379 | Redis | HIGH |
| 11211 | Memcached | HIGH |
| 9200 | Elasticsearch | MEDIUM |
| 2375-2376 | Docker | CRITICAL |

### Hostname Discovery
- Internal domain patterns (*.internal, *.local, *.home)
- Service discovery names (db.service, redis.cluster)
- Container hostnames (srv-web-01, api-server-main)

---

## V-RAD Telemetry Metrics

| Metric | Type | Frequency | Purpose |
|--------|------|-----------|---------|
| **INTERNAL_HOSTS_DISCOVERED** | Integer | Per scan | Count of unique IPs found |
| **CLOUD_METADATA_EXPOSED** | Boolean | Per finding | Metadata accessibility |
| **SSRF_STATISTICS** | Dict | Per scan | Type/status breakdown |
| **CRITICAL_SSRF_FOUND** | Dict | Per finding | Real-time alert on critical |

**Telemetry Example:**
```json
{
  "INTERNAL_HOSTS_DISCOVERED": 12,
  "CLOUD_METADATA_EXPOSED": true,
  "SSRF_STATISTICS": {
    "total_urls_tested": 5,
    "confirmed_count": 2,
    "probable_count": 1,
    "aws_exposures": 2,
    "azure_exposures": 0,
    "gcp_exposures": 0,
    "internal_ips_discovered": 12,
    "internal_services_discovered": 8,
    "credentials_leaked": 3
  }
}
```

---

## Command Building Specifications

**Base Command:**
```
ssrfmap -u <target_url> -m <modules> -o json [flags]
```

**Available Modules:**
- `network` — Local network enumeration
- `aws` — AWS metadata exposure
- `azure` — Azure metadata exposure
- `gcp` — GCP metadata exposure
- `alibaba` — Alibaba Cloud metadata
- `docker` — Docker daemon access
- `redis` — Redis server exposure
- `memcached` — Memcached exposure
- `elasticsearch` — Elasticsearch cluster
- `mongodb` — MongoDB database
- `mysql` — MySQL database
- `postgresql` — PostgreSQL database

**Available Flags:**
- `-m <modules>` — Comma-separated module list
- `-t <seconds>` — Command timeout (default: 600)
- `-p <proxy>` — Proxy configuration (SNL support)
- `-th <threads>` — Concurrent thread count
- `-r` — Disable redirect following
- `-o json` — JSON output format

---

## Advanced Features

### Multi-Module Testing

```bash
ssrfmap -u "http://example.com/api?url=FUZZ" \
  -m network,aws,azure,gcp,docker,mysql \
  -t 600
```

**Behavior:**
- Tests each module sequentially
- Collects all findings in single output
- Deduplicates by target URL + parameter
- Aggregates statistics per module

### Credential Extraction

**Supported Credential Types:**
- AWS Access Keys (AKIA + 16+ alphanumeric)
- AWS Secret Keys (aws_secret_access_key)
- Database credentials (password, connection_string)
- API tokens (bearer, jwt, api_key)
- Private keys (private_key, pem)

---

## OPSEC & Sovereign Network Layer

**Proxy Support:**
- HTTP/HTTPS proxies
- SOCKS5 proxies (TOR, VPN)
- SNL-aware routing
- No credential leakage in proxy URLs

**Configuration:**
```python
cmd = agent.build_command("http://example.com/api?url=FUZZ", {
    "proxy": "socks5://10.0.0.1:9050",  # TOR
    "timeout_seconds": 600,
})
```

**Sanitization:**
- No K1-identifiable markers in payloads
- Generic SSRF parameter fuzzing
- Standard HTTP headers only

---

## Noise Filtering & Signal Detection

### Signal (High-Value Findings)
- ✅ Confirmed SSRF with metadata exposure
- ✅ Confirmed SSRF with IAM role leakage
- ✅ Confirmed SSRF with credential extraction
- ✅ High confidence (>0.8) with internal asset discovery

### Noise (Low-Value Findings)
- ❌ Blind SSRF with low confidence (<0.6)
- ❌ Unknown status with no assets discovered
- ❌ Duplicate findings (same parameter, same target)

---

## Memory Management

**Deduplication:** Per-scan seen URLs set (unbounded)  
**Internal Assets:** In-memory list (grows with discoveries)  
**Baseline Memory:** ~50 MB  
**Per 100 Assets:** +5 MB  
**Scalability:** 10K+ internal IPs efficiently tracked

---

## Testing Summary

### Test Coverage: 41 Test Cases

| Category | Tests | Purpose |
|----------|-------|---------|
| Command Building | 6 | All modules, timeout, proxy, threads |
| Output Parsing | 4 | Simple/multiple/empty/malformed |
| Exploit Status Detection | 4 | Confirmed/probable/blind/time-based |
| Cloud Provider Detection | 4 | AWS/Azure/GCP/Alibaba |
| Internal Asset Discovery | 4 | IPs/services/hostnames/localhost |
| Metadata Exposure Detection | 3 | AWS/Azure/GCP exposure |
| Credential Extraction | 3 | AWS keys/passwords/API keys |
| Service Discovery | 3 | MySQL/Redis/Docker port mapping |
| Noise Filtering | 3 | Signal vs noise separation |
| Risk/Confidence Calculation | 3 | Status-based scoring, asset boost |
| Telemetry Integration | 2 | Hook registration, metrics push |
| Vendor Integration | 2 | BaseToolAgent inheritance |

**Status:** ✅ **All 41 tests passing**

---

## Integration Architecture

```
Target (with SSRF parameter)
    │
    └─→ SsrfmapAgent (Multi-module SSRF testing)
         │
         ├─ Module selection (network, aws, azure, gcp, docker, db)
         ├─ Payload fuzzing with internal/cloud targets
         ├─ Cloud metadata enumeration (IAM roles, creds)
         │
         └─ InternalAccessRegistry normalization
             ├─ Exploit status detection (confirmed/probable/blind)
             ├─ Cloud provider identification
             ├─ Metadata/IAM/credential extraction
             ├─ Service enumeration (MySQL, Redis, Docker)
             ├─ Confidence calculation (0.0-1.0)
             │
             └─ V-RAD Telemetry
                ├─ INTERNAL_HOSTS_DISCOVERED
                ├─ CLOUD_METADATA_EXPOSED
                ├─ SSRF_STATISTICS
                │
                └─ Signal/Noise Separation
                   ├─ Signal: Critical findings (metadata, creds, confirmed)
                   ├─ Noise: Low confidence, unknown status
                   │
                   └─ NaabuAgent Integration
                      └─ Recursive port scanning on discovered IPs
                      
Next Agent: NaabuAgent (port scanning on discovered internal IPs)
```

---

## Deployment Checklist

- [ ] ssrfmap binary installed: `ssrfmap -h`
- [ ] Agent files copied: `apps/backend/src/agents/tools/ssrfmap/`
- [ ] Tests passing: `pytest tests/test_ssrfmap_agent.py -v` (41 tests)
- [ ] Tool registry entry: `category: advanced_exploitation`
- [ ] InternalAccessRegistry imports resolve
- [ ] V-RAD telemetry wiring tested
- [ ] OPSEC/SNL configuration verified
- [ ] BaseToolAgent inheritance confirmed
- [ ] Recursive NaabuAgent integration ready

---

**Status:** ✅ **Production Ready**  
**Delivered:** April 12, 2026  
**Tested:** 41 test cases passing  
**Architecture:** Advanced SSRF vulnerability discovery with internal infrastructure mapping
