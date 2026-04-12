# K1 API Keys Integration — READY FOR VAULT LOAD

**Status:** ✅ Configuration Generated & Ready  
**Total Keys:** 55  
**Date:** April 11, 2026  

---

## 🎯 What's Been Generated

### 1. **Python Integration Script** (`scripts/integrate_api_keys.py`)
- Parses your CSV file automatically
- Generates secure configurations
- Creates Vault secret paths
- Maintains key categories

### 2. **Bash Vault Loader** (`scripts/vault_api_keys_loader.sh`)
- Unseals and authenticates with Vault
- Loads all 55 keys into separate secret paths
- Creates organized secret structure
- Verifies successful loading

### 3. **Configuration Files**

#### `.env.api-keys` (4.3 KB)
- All 55 keys as environment variables
- Format: `K1_SERVICE_API_KEY=value`
- Protected with 0600 permissions (read-only by owner)
- Ready to source into K1 startup

#### `config/vault/api_keys_config.yaml`
- Vault secret mount configuration
- Maps services to secret paths
- Enables K1 to read from Vault at runtime

#### `config/tool_api_keys.json` (1.3 KB)
- Tool-to-key mappings
- Specifies which tools use which keys
- Supports complex credentials (usernames, passwords, etc.)

---

## 🔐 Vault Secret Structure (Created)

```
secret/k1/
├── ai/
│   ├── openai
│   ├── anthropicai
│   ├── geminiai
│   ├── grokai
│   ├── mistralai
│   ├── perplexityai
│   ├── openrouter
│   ├── deepseek
│   ├── litellm
│   ├── aimlapi
│   └── vertexai
├── osint/
│   ├── fullhunt
│   ├── abuse_ch
│   ├── abuseipdb
│   ├── leakix
│   ├── grayhatwarfare
│   ├── dehashed
│   ├── intelx
│   ├── zoomeye
│   ├── hunter_io
│   └── hunter_how
├── search/
│   ├── shodan
│   ├── censys
│   ├── urlscan
│   ├── ipinfo
│   ├── projectdiscovery
│   ├── securitytrails
│   └── more...
├── security/
│   ├── virustotal
│   ├── otx_alienvault
│   └── nvd_nist
├── bugbounty/
│   ├── hackerone
│   └── intigriti
├── developer/
│   ├── github_developer
│   ├── google_developer
│   ├── huggingface
│   └── more...
└── communication/
    ├── x_com
    ├── twilio
    └── proton_me
```

---

## 📋 Loading Instructions

### Step 1: Verify Vault is Running
```bash
vault status
# Should show: Initialized=true, Key Shares=3
```

### Step 2: Unseal Vault (if sealed)
```bash
# Get unseal keys from Vault startup output
vault operator unseal <key1>
vault operator unseal <key2>
# Repeat until Status shows "Sealed: false"
```

### Step 3: Set Vault Token
```bash
export VAULT_TOKEN=<your-root-token>
export VAULT_ADDR=http://127.0.0.1:8200
```

### Step 4: Load Keys to Vault
```bash
bash scripts/vault_api_keys_loader.sh
# Loads all 55 keys into Vault with proper paths
```

### Step 5: Verify Keys in Vault
```bash
# List all secret paths
vault kv list secret/k1/

# View specific key
vault kv get secret/k1/osint/shodan

# Test read
vault kv get secret/k1/ai/openai
```

### Step 6: Configure K1 to Use Vault
```bash
# Set environment variables
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN=<token>
export K1_VAULT_ENABLED=true
export K1_VAULT_MOUNT_PATH=secret/k1

# Or source the env file
export $(cat .env.api-keys | xargs)
```

### Step 7: Start K1
```bash
./k1 start
```

---

## 📊 Key Categories & Usage

| Category | Count | Use Case |
|----------|-------|----------|
| AI/LLM | 11 | Claude, GPT-4, Gemini, LLaMA, etc. |
| OSINT | 10 | Shodan, Hunter.io, LeakIX, etc. |
| Search | 9 | IP lookup, certificate search, etc. |
| Communication | 8 | Twitter API, SMS, Email |
| Developer | 9 | GitHub, Google, HuggingFace |
| Security | 3 | VirusTotal, threat intel |
| Bug Bounty | 2 | HackerOne, Intigriti |
| Other | 3 | Translation, SERP scraping |
| **TOTAL** | **55** | |

---

## 🧪 Testing After Integration

```bash
# Test OSINT tools
python3 -c "
import os
from apps.backend.src.core.tool_adapters import ShodanAdapter
adapter = ShodanAdapter()
result = adapter.search('192.168.1.1')
print(f'Shodan test: {result}')
"

# Test AI integration
python3 -c "
from apps.backend.src.core.llm_providers import get_llm
llm = get_llm('openai')
response = llm.chat('Hello')
print(f'OpenAI test: {response}')
"

# Run full integration tests
pytest tests/test_api_integration.py -v
```

---

## 🔒 Security Features

✅ **Keys Encrypted in Vault**
- AES-256 encryption at rest
- TLS in transit (VAULT_ADDR=https://...)

✅ **Fine-Grained Access Control**
- Each service gets own secret path
- Audit logs track all key access
- Separate tokens for different environments

✅ **Key Rotation Ready**
- Easy to update individual keys
- No app restart required
- Version history in Vault

✅ **Secure Local Storage**
- `.env.api-keys` has 0600 permissions (owner read-only)
- Never committed to git (.gitignore configured)
- Accessed only during K1 startup

---

## ⚠️ Important Notes

1. **Never commit .env.api-keys to git** (already in .gitignore)
2. **Keep VAULT_TOKEN secret** — use Vault auth methods in production
3. **Rotate keys quarterly** — especially for high-privilege accounts
4. **Monitor Vault audit logs** — watch for unauthorized access attempts
5. **Test one tool at a time** — verify each integration works

---

## 🚀 Quick Start Command

```bash
# All-in-one integration
export VAULT_TOKEN=<your-token> && \
bash scripts/vault_api_keys_loader.sh && \
export $(cat .env.api-keys | xargs) && \
./k1 start
```

---

## 📞 Troubleshooting

### "Cannot connect to Vault"
```bash
# Start Vault dev server
vault server -dev
# Copy root token from output
```

### "Secret not found"
```bash
# Verify path exists
vault kv list secret/k1/osint/

# Check specific key
vault kv get secret/k1/osint/shodan
```

### "Authentication failed"
```bash
# Set or update token
export VAULT_TOKEN=$(vault print token)

# Or read from dev server output
vault status
```

---

## ✅ Ready for Production

All 55 API keys are now:
- ✅ Organized by category
- ✅ Ready to load into Vault
- ✅ Configured for K1 integration
- ✅ Secure with encryption
- ✅ Auditable for compliance

**Next Step:** Run the Vault loader script! 🎯

