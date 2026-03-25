#!/usr/bin/env bash
# Apply a local-first Kai profile: Ollama-only routing (<=9B) + local Vault defaults.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[local-profile]${NC} $*"; }
warn() { echo -e "${YELLOW}[local-profile]${NC} $*"; }
error() { echo -e "${RED}[local-profile]${NC} $*" >&2; }

upsert_env() {
    local key="$1"
    local value="$2"
    if grep -q "^${key}=" "${ENV_FILE}"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "${ENV_FILE}"
    else
        printf "\n%s=%s\n" "${key}" "${value}" >> "${ENV_FILE}"
    fi
}

read_env_value() {
    local key="$1"
    local default="$2"
    local value=""
    if [[ -f "${ENV_FILE}" ]]; then
        value="$(grep -E "^${key}=" "${ENV_FILE}" | tail -n 1 | cut -d= -f2- || true)"
        value="${value%\"}"
        value="${value#\"}"
    fi
    if [[ -n "${value}" ]]; then
        echo "${value}"
    else
        echo "${default}"
    fi
}

if [[ ! -f "${ENV_FILE}" ]]; then
    if [[ -f "${REPO_ROOT}/.env.example" ]]; then
        cp "${REPO_ROOT}/.env.example" "${ENV_FILE}"
        warn "Created .env from .env.example."
    else
        error ".env and .env.example are both missing."
        exit 1
    fi
fi

# Local-first LLM routing.
upsert_env "LLM_PROVIDER" "ollama"
upsert_env "K1_PRIMARY_LLM_PROVIDER" "ollama"
upsert_env "K1_FALLBACK_LLM_PROVIDERS" "ollama"
upsert_env "OLLAMA_HOST" "http://localhost:11434"
upsert_env "OLLAMA_BASE_URL" "http://localhost:11434"
upsert_env "OLLAMA_MODEL" "qwen2.5-coder:7b"
upsert_env "K1_OLLAMA_MODEL" "qwen2.5-coder:7b"
upsert_env "GEMMA_MODEL" "gemma:7b"
upsert_env "K1_GEMMA_MODEL" "gemma:7b"
upsert_env "K1_OLLAMA_ALLOWED_MODELS" "qwen2.5-coder:7b,llama3.1:8b,gemma:7b"
upsert_env "K1_MAX_LOCAL_MODEL_B" "9"
upsert_env "K1_OLLAMA_AUTO_PULL" "true"
upsert_env "K1_BOOTSTRAP_REQUIRE_EXTERNAL_TOOLS" "false"
upsert_env "K1_BOOTSTRAP_ADMIN_ENABLED" "true"
upsert_env "K1_BOOTSTRAP_ADMIN_USERNAME" "k1-admin"
upsert_env "K1_BOOTSTRAP_TENANT_NAME" "kai-local"
upsert_env "K1_STARTUP_ENABLE_INTELLIGENCE" "false"
upsert_env "K1_STARTUP_ENABLE_RAG" "false"

# Local host runtime endpoints for non-container backend startup.
# Match docker-compose.dev local defaults to avoid host/container credential drift.
POSTGRES_PASSWORD_VALUE="${POSTGRES_PASSWORD}"
upsert_env "POSTGRES_USER" "k1"
upsert_env "POSTGRES_PASSWORD" "${POSTGRES_PASSWORD_VALUE}"
upsert_env "POSTGRES_DB" "k1"
upsert_env "DATABASE_URL" "postgresql://k1:${POSTGRES_PASSWORD_VALUE}@127.0.0.1:5432/k1"
upsert_env "REDIS_URL" "redis://127.0.0.1:6379/0"
upsert_env "K1_ENFORCE_WHONIX_KVM" "true"
upsert_env "K1_WHONIX_LIBVIRT_URI" "qemu:///session"
upsert_env "K1_WHONIX_VM_NAMES" "whonix-gateway,Whonix-Gateway,whonix_gateway"
upsert_env "K1_WHONIX_PROXY_HOST" "10.152.152.10"
upsert_env "K1_WHONIX_PROXY_PORT" "9050"
upsert_env "HTTP_PROXY" "http://10.152.152.10:9050"
upsert_env "HTTPS_PROXY" "http://10.152.152.10:9050"
upsert_env "NO_PROXY" "127.0.0.1,localhost,postgres,redis,vault,ollama"
upsert_env "no_proxy" "127.0.0.1,localhost,postgres,redis,vault,ollama"

# Local Vault defaults.
upsert_env "K1_SECRET_BACKEND" "vault"
upsert_env "K1_VAULT_HOST_BIND" "127.0.0.1"
upsert_env "K1_VAULT_HOST_PORT" "8201"
upsert_env "VAULT_ADDR" "http://localhost:8201"
upsert_env "VAULT_TOKEN" "${VAULT_TOKEN}"
upsert_env "VAULT_DEV_ROOT_TOKEN" "${VAULT_DEV_ROOT_TOKEN}"
upsert_env "VAULT_MOUNT_POINT" "secret"
upsert_env "VAULT_SECRET_PREFIX" "kai"

info "Applied local Ollama+Vault profile to ${ENV_FILE}"
info "Primary model: qwen2.5-coder:7b"
info "Allowed models: qwen2.5-coder:7b, llama3.1:8b, gemma:7b (max 9B)"
info "Vault host port: 8201"
