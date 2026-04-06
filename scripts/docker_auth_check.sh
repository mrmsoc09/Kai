#!/bin/bash
# KAISON AI — Docker Authentication Check
# Verifies Docker login status and authenticates if needed.
# Stores credentials in Vault only. Never stores credentials in plaintext.
# Never prompts if already authenticated.

set -euo pipefail

VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
VAULT_TOKEN="${VAULT_TOKEN:-}"
DOCKER_REGISTRY="${DOCKER_REGISTRY:-docker.io}"

log_info()  { echo "[K1 Docker] $1"; }
log_warn()  { echo "[K1 Docker WARN] $1"; }
log_error() { echo "[K1 Docker ERROR] $1" >&2; }

# Check if Docker daemon is running
check_docker_running() {
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker daemon is not running."
        log_error "Start Docker and retry: sudo systemctl start docker"
        return 1
    fi
}

# Check if already authenticated to registry
is_docker_authenticated() {
    local config_file="$HOME/.docker/config.json"
    if [ ! -f "$config_file" ]; then
        return 1
    fi
    # Check if registry has an auth entry
    if python3 -c "
import json, sys
try:
    config = json.load(open('$config_file'))
    auths = config.get('auths', {})
    # Check for registry or credential helpers
    if '$DOCKER_REGISTRY' in auths:
        sys.exit(0)
    # Check for credsStore which handles auth externally
    if config.get('credsStore'):
        sys.exit(0)
    sys.exit(1)
except Exception:
    sys.exit(1)
" 2>/dev/null; then
        return 0
    fi
    return 1
}

# Retrieve Docker credentials from Vault
get_creds_from_vault() {
    if [ -z "$VAULT_TOKEN" ]; then
        return 1
    fi
    local response
    response=$(curl -sf \
        -H "X-Vault-Token: $VAULT_TOKEN" \
        "$VAULT_ADDR/v1/secret/data/kaison/docker" \
        2>/dev/null) || return 1

    DOCKER_USERNAME=$(echo "$response" | \
        python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    print(d['data']['data']['username'])
except:
    sys.exit(1)
" 2>/dev/null) || return 1

    DOCKER_PASSWORD=$(echo "$response" | \
        python3 -c "
import json,sys
try:
    d=json.load(sys.stdin)
    print(d['data']['data']['password'])
except:
    sys.exit(1)
" 2>/dev/null) || return 1

    return 0
}

# Store Docker credentials in Vault
store_creds_in_vault() {
    local username="$1"
    local password="$2"
    if [ -z "$VAULT_TOKEN" ]; then
        log_warn "Vault token not set. Credentials not persisted to Vault."
        return 0
    fi
    if curl -sf \
        -H "X-Vault-Token: $VAULT_TOKEN" \
        -H "Content-Type: application/json" \
        -X POST \
        -d "{\"data\":{\"username\":\"$username\",\"password\":\"$password\"}}" \
        "$VAULT_ADDR/v1/secret/data/kaison/docker" \
        > /dev/null 2>&1; then
        log_info "Docker credentials encrypted and stored in Vault."
        return 0
    else
        log_warn "Could not store credentials in Vault. Continuing."
        return 0
    fi
}

# Prompt user for Docker credentials
prompt_for_credentials() {
    log_info "Docker authentication required for $DOCKER_REGISTRY"
    log_info "Credentials will be encrypted and stored in Vault."
    echo ""
    read -rp "Docker Username: " DOCKER_USERNAME
    read -rsp "Docker Password/Token: " DOCKER_PASSWORD
    echo ""
    export DOCKER_USERNAME
    export DOCKER_PASSWORD
}

# Authenticate to Docker registry
docker_login() {
    local username="$1"
    local password="$2"
    echo "$password" | docker login \
        --username "$username" \
        --password-stdin \
        "$DOCKER_REGISTRY" 2>&1
    return $?
}

# Main authentication flow
main() {
    check_docker_running || return 1

    if is_docker_authenticated; then
        log_info "Docker: already authenticated to $DOCKER_REGISTRY"
        return 0
    fi

    log_info "Docker: not authenticated. Checking Vault..."

    # Try Vault first
    if get_creds_from_vault; then
        log_info "Docker: credentials found in Vault. Authenticating..."
        if docker_login "$DOCKER_USERNAME" "$DOCKER_PASSWORD"; then
            log_info "Docker: authenticated successfully."
            return 0
        else
            log_warn "Docker: Vault credentials failed. Prompting user."
        fi
    fi

    # Prompt user as last resort
    prompt_for_credentials

    if docker_login "$DOCKER_USERNAME" "$DOCKER_PASSWORD"; then
        log_info "Docker: authenticated successfully."
        store_creds_in_vault \
            "$DOCKER_USERNAME" \
            "$DOCKER_PASSWORD"
        return 0
    else
        log_error "Docker: authentication failed."
        log_error "Check username and password and retry."
        return 1
    fi
}

main "$@"
