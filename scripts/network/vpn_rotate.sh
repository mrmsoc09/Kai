#!/usr/bin/env bash
# vpn_rotate.sh — Rotate active WireGuard VPN interface.
# Called by network_router.py via subprocess when rotation is needed.
# Requires: wg-quick, curl, jq
set -euo pipefail

VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
VAULT_TOKEN="${VAULT_TOKEN:-}"
WG_CONF_DIR_MULLVAD="/home/k1-admin/MullvadVPN WireGaurd/mullvad_wireguard_linux_all_all"
HEALTH_CHECK_URL="https://ifconfig.me/ip"
MAX_ATTEMPTS=5

log() { echo "[vpn_rotate] $(date -u +%H:%M:%SZ) $*" >&2; }

fetch_vault_secret() {
  local path="$1" key="$2"
  curl -sf -H "X-Vault-Token: ${VAULT_TOKEN}" \
    "${VAULT_ADDR}/v1/${path}" | jq -r ".data.data.${key} // empty"
}

bring_down_all() {
  for iface in $(ip link show | grep -oP 'wg-\S+(?=:)' || true); do
    wg-quick down "${iface}" 2>/dev/null && log "Brought down ${iface}" || true
  done
}

current_ip() {
  curl -sf --max-time 8 "${HEALTH_CHECK_URL}" || echo "unknown"
}

rotate_mullvad() {
  local country_filter="${1:-us}"
  mapfile -t configs < <(ls "${WG_CONF_DIR_MULLVAD}"/${country_filter}-*.conf 2>/dev/null | shuf)
  [[ ${#configs[@]} -eq 0 ]] && { log "No Mullvad configs for country: ${country_filter}"; return 1; }

  local before_ip; before_ip=$(current_ip)

  for attempt in $(seq 1 "${MAX_ATTEMPTS}"); do
    local conf="${configs[$(( (attempt - 1) % ${#configs[@]} ))]}"
    local iface="wg-mlvd$(basename "${conf}" .conf | tr -cd '0-9' | head -c4)"
    log "Attempt ${attempt}: ${conf} → ${iface}"

    bring_down_all
    # Write temp config with real private key from Vault (never stored on disk)
    local privkey; privkey=$(fetch_vault_secret "secret/data/k1/network/mullvad_privkey" "value")
    if [[ -z "${privkey}" ]]; then
      log "Mullvad private key not in Vault — using config file directly (less secure)"
      wg-quick up "${conf}" && break
    else
      local tmpconf; tmpconf=$(mktemp /tmp/wg-XXXXXX.conf)
      sed "s|^PrivateKey = .*|PrivateKey = ${privkey}|" "${conf}" > "${tmpconf}"
      wg-quick up "${tmpconf}" && rm -f "${tmpconf}" && break
      rm -f "${tmpconf}"
    fi
    sleep "$(( RANDOM % 3 + 1 ))"
  done

  local after_ip; after_ip=$(current_ip)
  if [[ "${before_ip}" == "${after_ip}" ]]; then
    log "WARNING: IP did not change (${after_ip})"
    exit 1
  fi
  log "Rotated: ${before_ip} → ${after_ip}"
  echo "${after_ip}"
}

rotate_proton() {
  local slot="${1:-1}"  # 1 or 2
  local privkey_key="protonvpn_privkey_${slot}"
  local iface="wg-proton$(( slot - 1 ))"

  bring_down_all
  local privkey; privkey=$(fetch_vault_secret "secret/data/k1/network/${privkey_key}" "value")
  [[ -z "${privkey}" ]] && { log "ProtonVPN key ${slot} not in Vault"; exit 1; }

  local before_ip; before_ip=$(current_ip)
  local tmpconf; tmpconf=$(mktemp /tmp/wg-XXXXXX.conf)

  if [[ "${slot}" -eq 1 ]]; then
    cat > "${tmpconf}" <<CONF
[Interface]
PrivateKey = ${privkey}
Address = 10.2.0.2/32
DNS = 10.2.0.1
[Peer]
PublicKey = BjZdo7pghhm6xC6IQrAItH4O2QEKB5EGAYco60X4Vng=
AllowedIPs = 0.0.0.0/0
Endpoint = 149.40.51.231:51820
PersistentKeepalive = 25
CONF
  else
    cat > "${tmpconf}" <<CONF
[Interface]
PrivateKey = ${privkey}
Address = 10.2.0.2/32
DNS = 10.2.0.1
[Peer]
PublicKey = oOweBQMuJhyG8mY9D/zoRmnxZ1V6HcyND5HGKbWyZDg=
AllowedIPs = 0.0.0.0/0
Endpoint = 149.34.251.134:51820
PersistentKeepalive = 25
CONF
  fi

  wg-quick up "${tmpconf}"; local rc=$?
  rm -f "${tmpconf}"
  [[ ${rc} -ne 0 ]] && exit 1

  local after_ip; after_ip=$(current_ip)
  log "ProtonVPN slot ${slot} active: ${before_ip} → ${after_ip}"
  echo "${after_ip}"
}

# Main
PROVIDER="${1:-mullvad}"
PARAM="${2:-us}"
case "${PROVIDER}" in
  mullvad) rotate_mullvad "${PARAM}" ;;
  proton)  rotate_proton "${PARAM}" ;;
  down)    bring_down_all; log "All VPN interfaces down" ;;
  *) log "Usage: vpn_rotate.sh [mullvad|proton|down] [country|slot]"; exit 1 ;;
esac
