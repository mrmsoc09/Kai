#!/usr/bin/env bash
# Sync keys from secret/k1/* format to secret/kai/SERVICE_API_KEY format
# This bridges the namespace between our integration format and K1's expected format

set -uo pipefail

VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
VAULT_TOKEN="${VAULT_TOKEN:-}"

if [[ -z "$VAULT_TOKEN" ]]; then
    echo "❌ Error: VAULT_TOKEN not set"
    exit 1
fi

# Mapping table from k1 paths to kai secret names
declare -A KEY_MAPPING=(
    # AI Providers
    ["secret/k1/ai/openai"]="OPENAI_API_KEY"
    ["secret/k1/ai/anthropicai"]="ANTHROPIC_API_KEY"
    ["secret/k1/ai/geminiai"]="GEMINI_API_KEY"
    ["secret/k1/ai/grokai"]="GROQ_API_KEY"
    ["secret/k1/ai/mistralai"]="MISTRAL_API_KEY"
    ["secret/k1/ai/perplexityai"]="PERPLEXITY_API_KEY"
    ["secret/k1/ai/openrouter"]="OPENROUTER_API_KEY"
    ["secret/k1/ai/deepseek"]="DEEPSEEK_API_KEY"
    ["secret/k1/ai/vertexai"]="VERTEX_API_KEY"

    # OSINT Tools
    ["secret/k1/osint/shodan"]="SHODAN_API_KEY"
    ["secret/k1/osint/fullhunt"]="FULLHUNT_API_KEY"
    ["secret/k1/osint/censys"]="CENSYS_API_KEY"
    ["secret/k1/osint/urlscan"]="URLSCAN_API_KEY"
    ["secret/k1/osint/leakix"]="LEAKIX_API_KEY"
    ["secret/k1/osint/zoomeye"]="ZOOMEYE_API_KEY"
    ["secret/k1/osint/hunter_io"]="HUNTER_API_KEY"
    ["secret/k1/osint/dehashed"]="DEHASHED_API_KEY"
    ["secret/k1/osint/intelx"]="INTELX_API_KEY"
    ["secret/k1/osint/grayhatwarfare"]="GRAYHATWARFARE_API_KEY"

    # Security Tools
    ["secret/k1/security/virustotal"]="VIRUSTOTAL_API_KEY"
    ["secret/k1/security/otx_alienvault"]="OTX_API_KEY"
    ["secret/k1/security/nvd_nist"]="NVD_API_KEY"

    # BugBounty Platforms
    ["secret/k1/bugbounty/hackerone"]="HACKERONE_API_KEY"
    ["secret/k1/bugbounty/intigriti"]="INTIGRITI_API_KEY"

    # Search & Lookup
    ["secret/k1/search/securitytrails"]="SECURITYTRAILS_API_KEY"
    ["secret/k1/search/projectdiscovery"]="PROJECTDISCOVERY_API_KEY"
    ["secret/k1/search/ipinfo"]="IPINFO_API_KEY"

    # Communication
    ["secret/k1/communication/x_com"]="X_API_KEY"
    ["secret/k1/communication/twilio"]="TWILIO_API_KEY"
    ["secret/k1/communication/proton_me"]="PROTON_API_KEY"

    # Developer Tools
    ["secret/k1/developer/github_developer"]="GITHUB_API_KEY"
    ["secret/k1/developer/google_developer"]="GOOGLE_API_KEY"
    ["secret/k1/developer/huggingface"]="HUGGINGFACE_API_KEY"

    # Other
    ["secret/k1/other/deepl"]="DEEPL_API_KEY"
    ["secret/k1/other/serp"]="SERP_API_KEY"
)

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║      K1 API Keys Vault Format Synchronizer                    ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Syncing keys from secret/k1/* to secret/kai/* format..."
echo ""

SYNCED=0
FAILED=0
SKIPPED=0

for source_path in "${!KEY_MAPPING[@]}"; do
    target_name="${KEY_MAPPING[$source_path]}"
    target_path="secret/$target_name"

    # Try to read the source key
    value=$(vault kv get -field=key "$source_path" 2>/dev/null) || {
        echo "  ⊘ $source_path → (not found, skipping)"
        ((SKIPPED++))
        continue
    }

    # Write to target path
    if vault kv put "$target_path" value="$value" &> /dev/null; then
        printf "  ✓ %-45s → %s\n" "$source_path" "$target_name"
        ((SYNCED++))
    else
        printf "  ✗ %-45s → FAILED\n" "$source_path"
        ((FAILED++))
    fi
done

echo ""
echo "📊 SYNC RESULTS:"
echo "   ✓ Synced:  $SYNCED keys"
echo "   ⊘ Skipped: $SKIPPED keys"
if [[ $FAILED -gt 0 ]]; then
    echo "   ✗ Failed:  $FAILED keys"
fi

echo ""
echo "✅ Vault key format synchronization complete!"
echo ""
echo "You can now:"
echo "1. Source the .env.vault file: source .env.vault"
echo "2. Start K1 services: ./k1 start"
echo "3. K1 will automatically load API keys from Vault"
