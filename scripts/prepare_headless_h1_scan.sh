#!/usr/bin/env bash
# Prepare Kai for a headless HackerOne run without executing scans.
# Targets: x.com, snapchat.com, coinbase.com

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"
ARTIFACT_DIR="${REPO_ROOT}/artifacts/headless"
ARTIFACT_FILE="${ARTIFACT_DIR}/headless_h1_preflight.json"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[headless-prep]${NC} $*"; }
warn() { echo -e "${YELLOW}[headless-prep]${NC} $*"; }
error() { echo -e "${RED}[headless-prep]${NC} $*" >&2; }

upsert_env() {
    local key="$1"
    local value="$2"
    if grep -q "^${key}=" "${ENV_FILE}"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "${ENV_FILE}"
    else
        printf "\n%s=%s\n" "${key}" "${value}" >> "${ENV_FILE}"
    fi
}

read_env_key() {
    local key="$1"
    local value=""
    value="$(grep -E "^${key}=" "${ENV_FILE}" | tail -n1 | cut -d= -f2- || true)"
    value="${value%\"}"
    value="${value#\"}"
    echo "${value}"
}

read_csv_alias() {
    local alias="$1"
    local value=""
    value="$(grep -E "^${alias}," "${ENV_FILE}" | tail -n1 | cut -d, -f2- || true)"
    value="${value%\"}"
    value="${value#\"}"
    echo "${value}"
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

mkdir -p "${ARTIFACT_DIR}"

TARGETS_CSV="x.com,snapchat.com,coinbase.com"
PROGRAM_IDS_CSV="hackerone:twitter,hackerone:snapchat,hackerone:coinbase"
ALLOWED_LOCAL_MODELS="qwen2.5-coder:7b,llama3.1:8b,gemma:7b"

info "Applying headless prep profile (no scan execution)."

# Normalize common alias keys into canonical env names when missing.
if [[ -z "$(read_env_key ANTHROPIC_API_KEY)" ]]; then
    alias_val="$(read_csv_alias AnthropicAI)"
    if [[ -n "${alias_val}" ]]; then
        upsert_env "ANTHROPIC_API_KEY" "${alias_val}"
    fi
fi

if [[ -z "$(read_env_key GEMINI_API_KEY)" ]]; then
    alias_val="$(read_csv_alias GeminiAI)"
    if [[ -n "${alias_val}" ]]; then
        upsert_env "GEMINI_API_KEY" "${alias_val}"
    fi
fi

# Provider chain: paid first, local fallback if key/credits fail.
upsert_env "K1_PRIMARY_LLM_PROVIDER" "anthropic"
upsert_env "K1_FALLBACK_LLM_PROVIDERS" "openai,ollama,gemma"
upsert_env "K1_ROUTING_LLM_PROVIDER" "gemma"

# Local model policy (<=9B only).
upsert_env "K1_OLLAMA_ALLOWED_MODELS" "${ALLOWED_LOCAL_MODELS}"
upsert_env "K1_MAX_LOCAL_MODEL_B" "9"
upsert_env "K1_OLLAMA_MODEL" "llama3.1:8b"
upsert_env "K1_GEMMA_MODEL" "gemma:7b"
upsert_env "K1_OLLAMA_AUTO_PULL" "true"

# Headless run intent metadata (used by operator/start scripts).
upsert_env "K1_HEADLESS_PREP_MODE" "true"
upsert_env "K1_HEADLESS_TARGETS" "${TARGETS_CSV}"
upsert_env "K1_HEADLESS_PROGRAM_IDS" "${PROGRAM_IDS_CSV}"
upsert_env "K1_HEADLESS_MAX_PARALLEL_SCANS" "3"
upsert_env "K1_HEADLESS_MIN_PARALLEL_SCANS" "1"
upsert_env "K1_HEADLESS_REQUIRE_HIL" "true"
upsert_env "K1_HEADLESS_PAID_BUDGET_CENTS" "1700"
upsert_env "K1_HEADLESS_FALLBACK_LOCAL_ONLY_ON_BUDGET_EXHAUST" "true"

PYTHON_BIN="python3"
if [[ -x "${REPO_ROOT}/.venv/bin/python" ]]; then
    PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
fi

export REPO_ROOT ENV_FILE ARTIFACT_FILE TARGETS_CSV PROGRAM_IDS_CSV ALLOWED_LOCAL_MODELS
"${PYTHON_BIN}" - <<'PY'
import json
import os
from datetime import datetime, timezone
from pathlib import Path

repo_root = Path(os.environ["REPO_ROOT"])
env_file = Path(os.environ["ENV_FILE"])
artifact_file = Path(os.environ["ARTIFACT_FILE"])
targets = [x.strip() for x in os.environ["TARGETS_CSV"].split(",") if x.strip()]
program_ids = [x.strip() for x in os.environ["PROGRAM_IDS_CSV"].split(",") if x.strip()]
allowed_models = [x.strip() for x in os.environ["ALLOWED_LOCAL_MODELS"].split(",") if x.strip()]

# Verify requested opportunities exist in catalog.
import sys
sys.path.insert(0, str(repo_root))
from apps.backend.src.core.opportunity_catalog import get_opportunity  # noqa: E402
from apps.backend.src.core.provider_bootstrap import run_zero_touch_provider_bootstrap  # noqa: E402

# Load .env key/value pairs for preflight visibility.
env_map: dict[str, str] = {}
if env_file.exists():
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env_map[k.strip()] = v.strip().strip('"').strip("'")

# Inject provider vars from .env into process if unset so bootstrap check is accurate.
for key in (
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENROUTER_API_KEY",
    "K1_PRIMARY_LLM_PROVIDER",
    "K1_FALLBACK_LLM_PROVIDERS",
    "K1_ROUTING_LLM_PROVIDER",
):
    if not os.getenv(key) and env_map.get(key):
        os.environ[key] = env_map[key]

missing = [pid for pid in program_ids if get_opportunity(pid) is None]
if missing:
    raise SystemExit(f"Missing opportunity ids in catalog: {', '.join(missing)}")

def model_size(model: str) -> float:
    text = model.lower()
    if "b" not in text:
        return 0.0
    head = text.split("b", 1)[0]
    num = ""
    for ch in reversed(head):
        if ch.isdigit() or ch == ".":
            num = ch + num
        else:
            if num:
                break
    return float(num) if num else 0.0

too_large = [m for m in allowed_models if model_size(m) > 9.0]
if too_large:
    raise SystemExit(f"Local model policy violation (>9B): {', '.join(too_large)}")

provider_status = run_zero_touch_provider_bootstrap(
    interactive_prompt=False,
    validate_calls=False,
)

payload = {
    "prepared_at": datetime.now(timezone.utc).isoformat(),
    "mode": "headless_prep_only",
    "execution_started": False,
    "targets": targets,
    "program_ids": program_ids,
    "parallel_limits": {"min": 1, "max": 3},
    "paid_budget_cents": 1700,
    "provider_chain": {
        "primary": os.getenv("K1_PRIMARY_LLM_PROVIDER", env_map.get("K1_PRIMARY_LLM_PROVIDER", "")),
        "fallback": os.getenv("K1_FALLBACK_LLM_PROVIDERS", env_map.get("K1_FALLBACK_LLM_PROVIDERS", "")),
        "routing": os.getenv("K1_ROUTING_LLM_PROVIDER", env_map.get("K1_ROUTING_LLM_PROVIDER", "")),
    },
    "provider_bootstrap": {
        name: {
            "available": status.available,
            "validated": status.validated,
            "source": status.source,
            "key_env": status.key_env,
            "error": status.error,
        }
        for name, status in provider_status.items()
    },
    "local_model_policy": {
        "max_billion_params": 9,
        "allowed_models": allowed_models,
    },
    "notes": [
        "Preparation complete; no headless scan was started.",
        "If paid provider calls fail (missing key/quota/credits), runtime fallback chain continues to local models.",
        "HiL is required prior to final submission flow.",
    ],
}

artifact_file.parent.mkdir(parents=True, exist_ok=True)
artifact_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
PY

info "Prepared headless configuration for targets: ${TARGETS_CSV}"
info "Program ids verified: ${PROGRAM_IDS_CSV}"
info "Preflight artifact: ${ARTIFACT_FILE}"
info "No scan was started."
