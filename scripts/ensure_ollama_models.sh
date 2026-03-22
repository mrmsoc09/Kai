#!/usr/bin/env bash
# Ensure required Ollama models are installed locally and conform to max-size policy.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[ollama-models]${NC} $*"; }
warn() { echo -e "${YELLOW}[ollama-models]${NC} $*"; }
error() { echo -e "${RED}[ollama-models]${NC} $*" >&2; }

env_value() {
    local key="$1"
    local default="$2"
    local val=""
    if [[ -f "${ENV_FILE}" ]]; then
        val="$(grep -E "^${key}=" "${ENV_FILE}" | tail -n1 | cut -d= -f2- || true)"
        val="${val%\"}"
        val="${val#\"}"
    fi
    if [[ -n "${val}" ]]; then
        echo "${val}"
    else
        echo "${default}"
    fi
}

model_size_b() {
    local model="$1"
    if [[ "${model}" =~ ([0-9]+([.][0-9]+)?)b ]]; then
        echo "${BASH_REMATCH[1]}"
    else
        echo ""
    fi
}

size_is_allowed() {
    local size="$1"
    local max="$2"
    awk -v size="${size}" -v max="${max}" 'BEGIN { exit (size <= max) ? 0 : 1 }'
}

run_ollama() {
    if [[ "${OLLAMA_RUNNER}" == "host" ]]; then
        ollama "$@"
        return
    fi
    if [[ "${OLLAMA_RUNNER}" == "container" ]]; then
        docker exec k1_ollama ollama "$@"
        return
    fi
    return 1
}

MAX_MODEL_B="$(env_value K1_MAX_LOCAL_MODEL_B 9)"
MODELS_CSV="$(env_value K1_OLLAMA_ALLOWED_MODELS "qwen2.5-coder:7b,llama3.1:8b,gemma:7b")"
AUTO_PULL="$(env_value K1_OLLAMA_AUTO_PULL true | tr '[:upper:]' '[:lower:]')"

if [[ "${AUTO_PULL}" != "1" && "${AUTO_PULL}" != "true" && "${AUTO_PULL}" != "yes" && "${AUTO_PULL}" != "on" ]]; then
    info "K1_OLLAMA_AUTO_PULL is disabled; skipping model sync."
    exit 0
fi

OLLAMA_RUNNER=""
if command -v ollama >/dev/null 2>&1; then
    OLLAMA_RUNNER="host"
elif command -v docker >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -qx 'k1_ollama'; then
    OLLAMA_RUNNER="container"
fi

if [[ -z "${OLLAMA_RUNNER}" ]]; then
    warn "No Ollama runner available (host binary or k1_ollama container). Skipping model sync."
    exit 0
fi

IFS=',' read -r -a MODELS <<< "${MODELS_CSV}"
if [[ ${#MODELS[@]} -eq 0 ]]; then
    warn "No models configured in K1_OLLAMA_ALLOWED_MODELS; skipping."
    exit 0
fi

info "Ensuring Ollama models are available (max ${MAX_MODEL_B}B)."
for raw_model in "${MODELS[@]}"; do
    model="$(echo "${raw_model}" | xargs)"
    if [[ -z "${model}" ]]; then
        continue
    fi

    size="$(model_size_b "${model}")"
    if [[ -n "${size}" ]] && ! size_is_allowed "${size}" "${MAX_MODEL_B}"; then
        error "Model '${model}' violates max-size policy (${size}B > ${MAX_MODEL_B}B)."
        exit 1
    fi

    info "Pulling ${model}..."
    if ! run_ollama pull "${model}"; then
        warn "Failed to pull ${model}. Continuing with remaining models."
    fi
done

info "Installed Ollama models:"
run_ollama list || true
