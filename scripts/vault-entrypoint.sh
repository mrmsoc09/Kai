#!/usr/local/bin/dumb-init /bin/sh
set -e

# Start Vault in the background
vault server -config=/vault/config/vault.hcl &
VAULT_PID=$!

# Wait for Vault to be ready
until vault status -format=json 2>/dev/null | grep -q '"sealed"'; do
  sleep 1
done

# Check if already initialized
if ! vault status -format=json | grep -q '"initialized": true'; then
  echo "Initializing Vault..."
  vault operator init -key-shares=1 -key-threshold=1 -format=json > /vault/file/init.json
  
  # Extract token and keys
  cat /vault/file/init.json | jq -r '.root_token' > /vault/file/root_token
  cat /vault/file/init.json | jq -r '.unseal_keys_b64[0]' > /vault/file/unseal_key
  
  # Also write to a path accessible by host if needed, but here we stay in container
  # The task says "writes it to a gitignored file". 
  # We will mount /vault/file to the host.
fi

# Unseal Vault
if vault status -format=json | grep -q '"sealed": true'; then
  vault operator unseal $(cat /vault/file/unseal_key)
fi

echo "Vault is ready."
# Wait for Vault process
wait $VAULT_PID
