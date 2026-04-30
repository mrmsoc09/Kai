#!/usr/bin/env bash
# vpn_import_proton.sh — Import ProtonVPN private keys into Vault.
# This script is gitignored. Run once after initial setup.
# Usage: VAULT_TOKEN=<token> bash vpn_import_proton.sh
set -euo pipefail

VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
VAULT_TOKEN="${VAULT_TOKEN:?Set VAULT_TOKEN before running this script}"

vault_write() {
  local path="$1"; local key="$2"; local value="$3"
  curl -s -X POST \
    -H "X-Vault-Token: ${VAULT_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"data\":{\"${key}\":\"${value}\"}}" \
    "${VAULT_ADDR}/v1/${path}" >/dev/null
  echo "[OK] Stored ${path}"
}

echo "Importing ProtonVPN WireGuard private keys into Vault..."
echo "NOTE: Private keys are entered interactively — never stored in this script."

read -r -s -p "ProtonVPN private key for us-free-122: " KEY1; echo
vault_write "secret/data/k1/network/protonvpn_privkey_1" "value" "${KEY1}"

read -r -s -p "ProtonVPN private key for us-free-86: " KEY2; echo
vault_write "secret/data/k1/network/protonvpn_privkey_2" "value" "${KEY2}"

echo "Done. Keys are now in Vault. Do not store them anywhere else."
