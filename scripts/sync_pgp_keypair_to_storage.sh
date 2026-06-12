#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOURCE_DIR="${1:-/home/k1-admin/Documents/PGP-Keys}"
STORAGE_ROOT="${KAI_STORAGE_ROOT:-/srv/kai}"
PGP_DIR="${K1_PGP_KEY_SOURCE_DIR:-${STORAGE_ROOT}/keys/pgp}"

PUBLIC_KEY="${SOURCE_DIR}/kaisonai_0x0B83F0AE_public.asc"
PRIVATE_KEY="${SOURCE_DIR}/kaisonai_0x0B83F0AE_SECRET.asc"

if [[ ! -f "${PUBLIC_KEY}" ]]; then
  echo "Missing public key file: ${PUBLIC_KEY}" >&2
  exit 1
fi
if [[ ! -f "${PRIVATE_KEY}" ]]; then
  echo "Missing private key file: ${PRIVATE_KEY}" >&2
  exit 1
fi

if [[ -z "${VAULT_ADDR:-}" || -z "${VAULT_TOKEN:-}" ]]; then
  if [[ -f "${REPO_ROOT}/.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "${REPO_ROOT}/.env"
    set +a
  fi
fi

if [[ -z "${VAULT_ADDR:-}" || -z "${VAULT_TOKEN:-}" ]]; then
  echo "VAULT_ADDR and VAULT_TOKEN must be set or loadable from .env" >&2
  exit 1
fi

vault kv put secret/k1/auth/pgp/kaisonai \
  fingerprint="DECAA36A9155547D1E17966DFA6C06DA0B83F0AE" \
  uid="kaisonai <kaisonai@pm.me>" \
  public_key=@"${PUBLIC_KEY}" \
  private_key=@"${PRIVATE_KEY}"

mkdir -p "${PGP_DIR}"
install -m 0644 "${PUBLIC_KEY}" "${PGP_DIR}/kaisonai_public.asc"
install -m 0600 "${PRIVATE_KEY}" "${PGP_DIR}/kaisonai_private.asc"

echo "Stored PGP private key in Vault: secret/k1/auth/pgp/kaisonai"
echo "Synced runtime key material to: ${PGP_DIR}"
