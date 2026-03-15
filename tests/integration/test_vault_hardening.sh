#!/usr/bin/env bash
# Integration test for Vault token hardening

echo "Checking for hardcoded Vault tokens in compose files..."
TOKENS=$(grep -r "VAULT_TOKEN: root" . --include="docker-compose*.yml")
DEV_ROOT=$(grep -r "VAULT_DEV_ROOT_TOKEN_ID" . --include="docker-compose*.yml")

if [ -n "$TOKENS" ]; then
    echo "FAIL: Found hardcoded VAULT_TOKEN: root in: $TOKENS"
    exit 1
fi

if [ -n "$DEV_ROOT" ]; then
    echo "FAIL: Found VAULT_DEV_ROOT_TOKEN_ID in: $DEV_ROOT"
    exit 1
fi

echo "PASS: No hardcoded Vault tokens found in compose files."

echo "Checking for Vault config and entrypoint script..."
if [ -f Kai/config/vault.hcl ] && [ -f Kai/scripts/vault-entrypoint.sh ]; then
    echo "PASS: Vault config and entrypoint script exist."
else
    echo "FAIL: Vault config or entrypoint script missing."
    exit 1
fi

echo "Checking for Vault persistent storage volume in compose..."
if grep -q "vault_data:/vault/file:rw" Kai/docker-compose.dev.yml; then
    echo "PASS: Persistent storage configured for Vault."
else
    echo "FAIL: Persistent storage not found in Kai/docker-compose.dev.yml"
    exit 1
fi

exit 0
