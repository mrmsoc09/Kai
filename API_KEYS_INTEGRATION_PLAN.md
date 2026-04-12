# K1 API Keys Integration Plan

**Date:** April 11, 2026  
**Total Keys:** 55  
**Status:** Ready for Integration  

---

## 📊 API Keys Inventory

### By Service Category

#### 🔍 OSINT & Intelligence (10 keys)
- fullhunt — Subdomain discovery
- abuse_ch — Malware intelligence
- abuseipdb — IP reputation
- leakix — Leak intelligence  
- grayhatwarfare — S3 bucket discovery
- dehashed — Credential search
- intelx — Dark web/breach searches
- zoomeye — IP/device search (Chinese Shodan)
- hunter_io — Email discovery (2 keys)

#### 🔎 Search & Lookup (9 keys)
- **Shodan** — IP/device search + port scanning
- **Censys** — Certificate/host discovery (2 keys + creds)
- urlscan — URL/domain scanning
- ipinfo — IP geolocation
- projectdiscovery — Nuclei templates (2 keys)
- securitytrails — DNS/SSL records

#### 🤖 AI/LLM Services (11 keys)
- **OpenAI** — GPT models
- **Anthropic** — Claude models
- **Google** — Gemini + Workspace
- **Groq** — Fast inference
- **Mistral AI** — Mistral models
- **Perplexity AI** — Search + AI
- **OpenRouter** — Multi-model router
- DeepSeek — Chinese LLM
- LiteLLM — Multi-provider gateway
- HuggingFace — Model hub

#### 🐛 Bug Bounty Platforms (2 keys)
- HackerOne — BBP platform (encrypted)
- Intigriti — BBP platform

#### 🛡️ Security & Scanning (3 keys)
- VirusTotal — Malware/URL scanning
- OTX AlienVault — Threat intelligence
- NVD NIST — Vulnerability database

#### 🧑‍💻 Developer Tools (7 keys)
- **GitHub** — Code hosting (username + 2 keys)
- **Google** — Developer API + Workspace
- HuggingFace — ML models
- GitKraken — Git client
- AgentOps — Agent monitoring
- Coinbase — Crypto/payments (2 keys)

#### 📱 Social Media & Communication (8 keys)
- **X (Twitter)** — Social intel (5 keys: bearer, access, secret, app ID)
- Twilio — SMS/communications
- Proton.me — Email (credentials)

#### 📊 Other Services (6 keys)
- DeepL — Translation
- SERP/SerpDev — SERP scraping (2 keys)
- URLScan — Domain scanning

---

## 🔐 Integration Architecture

```
K1 Platform
    │
    ├─→ Vault (Secrets Management)
    │   └─→ Encrypted storage of all 55 keys
    │
    ├─→ Environment Variables
    │   └─→ /etc/k1/api-keys.env (loaded at startup)
    │
    ├─→ Tool Adapters
    │   ├─→ OSINT Agents (fullhunt, shodan, censys, etc.)
    │   ├─→ Intelligence Agents (virustotal, dehashed, etc.)
    │   ├─→ Scanning Agents (nuclei, nessus, etc.)
    │   ├─→ LLM Providers (OpenAI, Anthropic, Gemini, etc.)
    │   └─→ BBP Integrations (HackerOne, Intigriti)
    │
    └─→ Backend Configuration
        ├─→ llm_providers.py (AI model routing)
        ├─→ tool_registry.yaml (Tool-to-key mapping)
        └─→ config/providers/*.yaml (Service configs)
```

---

## 📝 Integration Steps

### Phase 1: Vault Setup (5 min)
```bash
# 1. Start Vault (if not running)
vault server -dev

# 2. Authenticate
export VAULT_ADDR='http://127.0.0.1:8200'
export VAULT_TOKEN='<dev-token>'

# 3. Create secret paths for each service category
vault kv put secret/k1/osint/shodan key="VyEiHyR9okVlCKK4s7D49pZz4PFPwHMS"
vault kv put secret/k1/ai/openai key="sk-proj-..."
vault kv put secret/k1/bugbounty/hackerone key="..."
# ... (repeat for all 55 keys)
```

### Phase 2: Environment Configuration (10 min)
```bash
# Create /etc/k1/api-keys.env with all keys
# Format:
# K1_SHODAN_API_KEY="..."
# K1_OPENAI_API_KEY="..."
# K1_ANTHROPIC_API_KEY="..."
# etc.
```

### Phase 3: Tool Adapter Configuration (15 min)
Update tool registry to map keys to tools:
```yaml
tools:
  - name: nuclei
    api_keys_required:
      - projectdiscovery_token
      - projectdiscovery_teamid
    
  - name: shodan
    api_keys_required:
      - shodan_api_key
    
  - name: censys
    api_keys_required:
      - censys_uid
      - censys_secret
```

### Phase 4: LLM Provider Setup (10 min)
Configure multi-provider routing in `llm_providers.py`:
```python
PROVIDERS = {
    'openai': {
        'api_key': os.getenv('K1_OPENAI_API_KEY'),
        'models': ['gpt-4', 'gpt-4-turbo', 'gpt-3.5-turbo']
    },
    'anthropic': {
        'api_key': os.getenv('K1_ANTHROPIC_API_KEY'),
        'models': ['claude-3-opus', 'claude-3-sonnet']
    },
    'gemini': {
        'api_key': os.getenv('K1_GOOGLE_GEMINI_KEY'),
        'models': ['gemini-1.5-pro']
    },
    # ... (repeat for all 11 LLM providers)
}
```

### Phase 5: Testing & Validation (20 min)
```bash
# Test each service:
pytest tests/test_api_connectivity.py
pytest tests/test_osint_services.py
pytest tests/test_ai_providers.py
pytest tests/test_bugbounty_platforms.py
```

---

## 🔑 Key Mapping & Usage

### OSINT Tools
| Service | Key | Tool | Purpose |
|---------|-----|------|---------|
| Shodan | shodan | shodan agent | IP/port/device search |
| Censys | censys_* | censys agent | Certificate/host enumeration |
| FullHunt | fullhunt | fullhunt agent | Subdomain discovery |
| URLScan | urlscan | urlscan agent | URL/domain analysis |
| LeakIX | leakix | leakix agent | Leak intelligence |
| ZoomEye | zoomeye | zoomeye agent | Device discovery |
| Hunter.io | hunter_io | hunter agent | Email discovery |
| SecurityTrails | securitytrails | trails agent | DNS/SSL records |
| GreyHat Warfare | grayhatwarfare | ghw agent | S3 bucket discovery |
| Dehashed | dehashed | dehashed agent | Credential search |

### Scanning & Security
| Service | Key | Tool | Purpose |
|---------|-----|------|---------|
| VirusTotal | virustotal | vt agent | Malware/URL scanning |
| ProjectDiscovery | projectdiscovery_* | nuclei agent | Vulnerability scanning |
| OTX AlienVault | otx_alienvault | otx agent | Threat intelligence |
| NVD NIST | nvd_nist | nvd agent | Vulnerability data |

### AI/LLM Providers
| Service | Key | Models | Purpose |
|---------|-----|--------|---------|
| OpenAI | openai | GPT-4, GPT-3.5 | Primary LLM |
| Anthropic | anthropicai | Claude 3 Opus/Sonnet | Reasoning tasks |
| Google | geminiai | Gemini 1.5 Pro | Vision + multimodal |
| Groq | grokai | Mixtral, LLaMA | Fast inference |
| Mistral | mistralai | Mistral 7B/8x7B | Alternative models |
| Perplexity | perplexityai | Perplexity Pro | Search + AI |
| OpenRouter | openrouter | 100+ models | Multi-model routing |

### Bug Bounty Platforms
| Service | Key | Purpose |
|---------|-----|---------|
| HackerOne | hackerone | BBP integration + report tracking |
| Intigriti | intigriti | BBP integration + submissions |

### Developer & Communication
| Service | Key | Purpose |
|---------|-----|---------|
| GitHub | github_* | Code repo + API access |
| Google Workspace | google_workspace | Email + cloud integration |
| Twilio | twilio | SMS notifications |
| Proton.me | proton_me | Secure email backup |

---

## 🔒 Security Best Practices

### ✅ DO
- [ ] Store all keys in Vault (encrypted at rest)
- [ ] Use environment variables for local development
- [ ] Rotate keys quarterly
- [ ] Audit key usage via Vault logs
- [ ] Separate read-only keys from admin keys
- [ ] Use team-scoped keys where available
- [ ] Document which tools require which keys

### ❌ DON'T
- [ ] Commit API keys to git (already in .gitignore)
- [ ] Log full API key values
- [ ] Share keys via unencrypted channels
- [ ] Use same key for multiple environments
- [ ] Hardcode keys in config files

---

## 📋 Required Vault Secrets Paths

```
secret/k1/osint/
  ├─ shodan
  ├─ censys
  ├─ fullhunt
  ├─ urlscan
  ├─ leakix
  ├─ zoomeye
  ├─ hunter_io
  ├─ securitytrails
  ├─ grayhatwarfare
  ├─ dehashed
  └─ intelx

secret/k1/scanning/
  ├─ virustotal
  ├─ projectdiscovery
  ├─ otx_alienvault
  └─ nvd_nist

secret/k1/ai/
  ├─ openai
  ├─ anthropic
  ├─ google_gemini
  ├─ groq
  ├─ mistral
  ├─ perplexity
  ├─ openrouter
  ├─ deepseek
  ├─ litellm
  └─ huggingface

secret/k1/bugbounty/
  ├─ hackerone
  └─ intigriti

secret/k1/developer/
  ├─ github
  ├─ google_developer
  ├─ gitkraken
  ├─ agentops
  └─ coinbase

secret/k1/communication/
  ├─ x_com
  ├─ twilio
  └─ proton_me

secret/k1/other/
  ├─ deepl
  ├─ serp
  └─ serper_dev
```

---

## 🧪 Testing Checklist

After integration, verify each service:

- [ ] Shodan — `shodan host <IP>`
- [ ] Censys — Certificate lookup
- [ ] FullHunt — Subdomain enum
- [ ] Nuclei — Template scan
- [ ] VirusTotal — URL scan
- [ ] OpenAI — API call with GPT-4
- [ ] Anthropic — API call with Claude
- [ ] Gemini — Vision analysis
- [ ] GitHub — Repo access
- [ ] HackerOne — Report retrieval
- [ ] Intigriti — Submission test
- [ ] X (Twitter) — Tweet search
- [ ] Twilio — SMS test message

---

## 📅 Implementation Timeline

| Phase | Task | Time | Status |
|-------|------|------|--------|
| 1 | Vault setup | 5 min | 🔲 Ready |
| 2 | Env configuration | 10 min | 🔲 Ready |
| 3 | Tool adapter config | 15 min | 🔲 Ready |
| 4 | LLM provider setup | 10 min | 🔲 Ready |
| 5 | Testing & validation | 20 min | 🔲 Ready |
| **Total** | **Complete Integration** | **60 min** | 🔲 Ready |

---

## 🚀 Quick Start

```bash
# 1. Create integration script
python3 scripts/integrate_api_keys.py \
  --vault-address http://127.0.0.1:8200 \
  --keys-file /home/k1-admin/Documents/API-KEYS\ Hashi-Corp_Vault.csv

# 2. Validate all keys
pytest tests/test_api_validation.py -v

# 3. Start K1 with keys loaded
./k1 start --load-api-keys

# 4. Verify integrations
./k1 test-apis --verbose
```

---

## 📞 Support

Once integrated, all K1 tools will have access to:
- ✅ Instant OSINT data from 10+ intelligence sources
- ✅ Multi-provider AI routing (11 LLM services)
- ✅ Automated vulnerability scanning
- ✅ Bug bounty platform integration
- ✅ Credential hunting across dark web
- ✅ Threat intelligence feeds

**Ready to proceed with integration? 🚀**
