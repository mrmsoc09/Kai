#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${ROOT_DIR}/.venv"
MEM_DIR="${K1_EXPERIENCE_MEMORY_PATH:-/mnt/nvme/k1-experience-memory/chromadb}"

echo "[k1] Preparing local ChromaDB memory backend"
echo "[k1] Memory path: ${MEM_DIR}"

mkdir -p "${MEM_DIR}"

if [[ -d "${VENV_DIR}" ]]; then
  # shellcheck disable=SC1091
  source "${VENV_DIR}/bin/activate"
  python -m pip install --upgrade pip >/dev/null
  python -m pip install "chromadb>=0.5.5" >/dev/null
else
  python3 -m pip install --user "chromadb>=0.5.5" >/dev/null
fi

cat <<EOF
[k1] ChromaDB setup complete.
Export if needed:
  export K1_EXPERIENCE_MEMORY_PATH="${MEM_DIR}"
  export K1_EXPERIENCE_MEMORY_DISABLE_CHROMA=false
EOF

