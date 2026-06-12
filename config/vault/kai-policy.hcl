# Vault policy for the KAI application service account.
# Apply with: vault policy write kai-app config/vault/kai-policy.hcl

# Database credentials
path "secret/k1/db/*" {
  capabilities = ["read"]
}

# AI provider API keys
path "secret/k1/ai/*" {
  capabilities = ["read"]
}

# OSINT / search API keys
path "secret/k1/osint/*" {
  capabilities = ["read"]
}
path "secret/k1/search/*" {
  capabilities = ["read"]
}

# Security tool API keys
path "secret/k1/security/*" {
  capabilities = ["read"]
}

# Bug bounty platform credentials
path "secret/k1/bugbounty/*" {
  capabilities = ["read"]
}

# Integration credentials (TheHive, Cortex, Wazuh, Shuffle)
path "secret/k1/integrations/*" {
  capabilities = ["read"]
}

# JWT signing key (read-only; rotation handled by ops)
path "secret/k1/auth/jwt" {
  capabilities = ["read"]
}

# PGP signing keys used for artifact and approval signing
path "secret/k1/auth/pgp/*" {
  capabilities = ["read"]
}

# Allow token renewal but not root-token operations
path "auth/token/renew-self" {
  capabilities = ["update"]
}
path "auth/token/lookup-self" {
  capabilities = ["read"]
}

# Deny everything else
path "*" {
  capabilities = ["deny"]
}
