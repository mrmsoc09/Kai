#!/usr/bin/env bash
# Vault API Keys Loader
# Unseals Vault and loads all 55 API keys into secure secret paths

set -euo pipefail

VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
KEYS_FILE="${1:-/home/k1-admin/Documents/API-KEYS Hashi-Corp_Vault.csv}"

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         K1 API KEYS VAULT LOADER                              ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Vault Address: $VAULT_ADDR"
echo "Keys File: $KEYS_FILE"
echo ""

# Check Vault CLI
if ! command -v vault &> /dev/null; then
    echo "❌ Error: vault CLI not found. Install Vault CLI first."
    exit 1
fi

# Check if Vault is running
echo "Checking Vault status..."
VAULT_STATUS=$(vault status 2>&1) || {
    echo "❌ Error: Cannot connect to Vault at $VAULT_ADDR"
    echo "   Start Vault with: vault server -dev"
    exit 1
}

echo "✓ Vault is running"
echo ""

# Check if sealed
IS_SEALED=$(echo "$VAULT_STATUS" | grep -i "sealed" | grep "true" || echo "")

if [[ -n "$IS_SEALED" ]]; then
    echo "⚠️  Vault is sealed. Unsealing..."
    echo ""
    echo "Note: For development, you can run:"
    echo "  vault operator unseal <key1>"
    echo "  vault operator unseal <key2>"
    echo ""
    echo "For dev server, get the unseal keys from the startup output:"
    echo "  vault server -dev"
    echo ""
    read -p "Press Enter after unsealing Vault, or Ctrl+C to exit: "
else
    echo "✓ Vault is unlocked"
fi

# Verify we can access Vault
echo ""
echo "Verifying Vault access..."
if ! vault secrets list &> /dev/null; then
    echo "❌ Error: Cannot authenticate to Vault"
    echo "   Set VAULT_TOKEN environment variable:"
    echo "   export VAULT_TOKEN=<your-root-token>"
    exit 1
fi

echo "✓ Vault authentication successful"
echo ""

# Create KV v2 secret engine if needed
echo "Setting up secret engine..."
vault secrets list | grep -q "secret/" || {
    echo "Creating KV v2 secret engine at secret/..."
    vault secrets enable -version=2 -path=secret kv || echo "Secret engine may already exist"
}

echo "✓ Secret engine ready"
echo ""

# Load keys from CSV
echo "Loading API keys into Vault..."
echo "─────────────────────────────────────────────────────────────────"

LOADED=0
FAILED=0

while IFS=',' read -r SERVICE KEY; do
    # Skip empty lines and header
    [[ -z "$SERVICE" ]] && continue
    SERVICE=$(echo "$SERVICE" | xargs)
    KEY=$(echo "$KEY" | xargs)
    [[ -z "$KEY" ]] && continue

    # Determine category
    CATEGORY=""
    case "$SERVICE" in
        fullhunt|abuse_ch|abuseipdb|leakix|grayhatwarfare|dehashed|intelx|zoomeye|hunter*) CATEGORY="osint" ;;
        ipinfo|projectdiscovery*|urlscan|securitytrails|shodan|censys*) CATEGORY="search" ;;
        openai|anthropic*|gemini*|grok*|mistral*|perplexity*|openrouter|deepseek|litellm|aimlapi|vertexai) CATEGORY="ai" ;;
        virustotal|otx_alienvault|nvd_nist) CATEGORY="security" ;;
        hackerone|intigriti) CATEGORY="bugbounty" ;;
        github*|google*|huggingface|gitkraken|agentops|coinbase*) CATEGORY="developer" ;;
        x_com*|twilio|proton*) CATEGORY="communication" ;;
        *) CATEGORY="other" ;;
    esac

    # Create secret path
    SECRET_PATH="secret/k1/$CATEGORY/$SERVICE"

    # Load to Vault
    if vault kv put "$SECRET_PATH" key="$KEY" &> /dev/null; then
        printf "  ✓ %-35s → %s\n" "$SERVICE" "$SECRET_PATH"
        ((LOADED++))
    else
        printf "  ✗ %-35s → FAILED\n" "$SERVICE"
        ((FAILED++))
    fi
done < "$KEYS_FILE"

echo "─────────────────────────────────────────────────────────────────"
echo ""

# Results
echo "📊 LOADING RESULTS:"
echo "   ✓ Loaded: $LOADED keys"
if [[ $FAILED -gt 0 ]]; then
    echo "   ✗ Failed: $FAILED keys"
fi

echo ""
echo "═════════════════════════════════════════════════════════════════"
echo "NEXT STEPS:"
echo "═════════════════════════════════════════════════════════════════"
echo ""
echo "1. Verify keys are in Vault:"
echo "   vault kv list secret/k1/"
echo ""
echo "2. Test reading a key:"
echo "   vault kv get secret/k1/osint/shodan"
echo ""
echo "3. Load environment variables in K1:"
echo "   export \$(cat .env.api-keys | xargs)"
echo ""
echo "4. Configure K1 to use Vault:"
echo "   K1_VAULT_ADDR=$VAULT_ADDR"
echo "   K1_VAULT_TOKEN=<your-token>"
echo ""
echo "5. Start K1 with API keys:"
echo "   ./k1 start"
echo ""
echo "✅ Vault integration complete!"
echo "═════════════════════════════════════════════════════════════════"
