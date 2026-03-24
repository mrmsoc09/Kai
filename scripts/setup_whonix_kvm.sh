#!/usr/bin/env bash
# Provision/verify Whonix KVM resources for Kai startup enforcement.
# - Downloads Whonix libvirt archive if missing
# - Defines Whonix networks/domains in libvirt
# - Places gateway/workstation qcow2 images in /var/lib/libvirt/images
# - Starts Whonix Gateway and updates Kai .env Whonix settings

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${REPO_ROOT}/.env"

URI="${K1_WHONIX_LIBVIRT_URI:-qemu:///system}"
DOWNLOAD_DIR="${K1_WHONIX_DOWNLOAD_DIR:-${HOME}/Downloads}"
VERSION="${K1_WHONIX_VERSION:-}"
ARCHIVE_PATH="${K1_WHONIX_ARCHIVE_PATH:-}"
FORCE_DOWNLOAD=false
FORCE_IMAGE_COPY=false
PROXY_WAIT_SECONDS="${K1_WHONIX_PROXY_WAIT_SECONDS:-180}"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[whonix-kvm]${NC} $*"; }
warn() { echo -e "${YELLOW}[whonix-kvm]${NC} $*"; }
error() { echo -e "${RED}[whonix-kvm]${NC} $*" >&2; }

usage() {
    cat <<'EOF'
Usage: ./scripts/setup_whonix_kvm.sh [options]

Options:
  --uri <libvirt-uri>          Libvirt URI (default: qemu:///system)
  --download-dir <dir>         Directory for Whonix archive download/search (default: ~/Downloads)
  --version <x.y.z.w>          Specific Whonix libvirt version to download
  --archive <path>             Use existing Whonix *.qcow2.libvirt.xz archive
  --force-download             Download archive even if local archive is found
  --force-image-copy           Overwrite /var/lib/libvirt/images/Whonix-*.qcow2
  -h, --help                   Show this help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --uri)
            URI="${2:?missing value for --uri}"
            shift 2
            ;;
        --download-dir)
            DOWNLOAD_DIR="${2:?missing value for --download-dir}"
            shift 2
            ;;
        --version)
            VERSION="${2:?missing value for --version}"
            shift 2
            ;;
        --archive)
            ARCHIVE_PATH="${2:?missing value for --archive}"
            shift 2
            ;;
        --force-download)
            FORCE_DOWNLOAD=true
            shift
            ;;
        --force-image-copy)
            FORCE_IMAGE_COPY=true
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            error "Unknown argument: $1"
            usage
            exit 1
            ;;
    esac
done

need_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        error "Required command not found: $1"
        exit 1
    fi
}

run_virsh() {
    virsh -c "${URI}" "$@"
}

validate_archive() {
    local archive="$1"
    local stamp="${archive}.k1-validated"
    local size mtime signature skip_xz skip_validate
    [[ -f "${archive}" ]] || return 1
    [[ -s "${archive}" ]] || return 1

    skip_validate="$(echo "${K1_WHONIX_SKIP_ARCHIVE_VALIDATION:-false}" | tr '[:upper:]' '[:lower:]')"
    if [[ "${skip_validate}" == "1" || "${skip_validate}" == "true" || "${skip_validate}" == "yes" || "${skip_validate}" == "on" ]]; then
        return 0
    fi

    size="$(stat -c%s "${archive}" 2>/dev/null || echo "")"
    mtime="$(stat -c%Y "${archive}" 2>/dev/null || echo "")"
    signature="${size}:${mtime}"

    if [[ -n "${size}" && -n "${mtime}" && -f "${stamp}" ]]; then
        if [[ "$(cat "${stamp}" 2>/dev/null || true)" == "${signature}" ]]; then
            tar -tf "${archive}" >/dev/null 2>&1 || return 1
            return 0
        fi
    fi

    skip_xz="$(echo "${K1_WHONIX_SKIP_XZ_TEST:-false}" | tr '[:upper:]' '[:lower:]')"
    if [[ "${skip_xz}" != "1" && "${skip_xz}" != "true" && "${skip_xz}" != "yes" && "${skip_xz}" != "on" ]]; then
        if command -v xz >/dev/null 2>&1; then
            xz -t "${archive}" >/dev/null 2>&1 || return 1
        fi
    fi

    tar -tf "${archive}" >/dev/null 2>&1 || return 1
    if [[ -n "${size}" && -n "${mtime}" ]]; then
        printf "%s\n" "${signature}" > "${stamp}"
    fi
    return 0
}

download_with_lock() {
    local url="$1"
    local part_file="$2"
    local lock_file="${part_file}.lock"
    mkdir -p "$(dirname "${part_file}")"

    if command -v flock >/dev/null 2>&1; then
        # Serialize writes to the same partial file across concurrent setup runs.
        exec 9>"${lock_file}"
        flock -w 900 9 || return 1
        no_proxy_curl -fL -C - "${url}" -o "${part_file}"
        flock -u 9 || true
        exec 9>&-
    else
        no_proxy_curl -fL -C - "${url}" -o "${part_file}"
    fi
}

no_proxy_curl() {
    env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY -u NO_PROXY -u no_proxy \
        curl -sS --connect-timeout 20 --retry 3 --retry-delay 2 "$@"
}

upsert_env() {
    local key="$1"
    local value="$2"
    if [[ ! -f "${ENV_FILE}" ]]; then
        touch "${ENV_FILE}"
    fi
    if grep -q "^${key}=" "${ENV_FILE}"; then
        sed -i "s|^${key}=.*|${key}=${value}|" "${ENV_FILE}"
    else
        printf "\n%s=%s\n" "${key}" "${value}" >> "${ENV_FILE}"
    fi
}

is_port_open() {
    local host="$1"
    local port="$2"
    python3 - "$host" "$port" <<'PY'
import socket
import sys
host = sys.argv[1]
port = int(sys.argv[2])
try:
    with socket.create_connection((host, port), timeout=3):
        raise SystemExit(0)
except OSError:
    raise SystemExit(1)
PY
}

detect_latest_version() {
    local html versions
    html="$(no_proxy_curl -fsSL "https://download.whonix.org/libvirt/")"
    versions="$(printf "%s\n" "${html}" | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+/' | tr -d '/' | sort -Vu || true)"
    if [[ -z "${versions}" ]]; then
        return 1
    fi
    printf "%s\n" "${versions}" | tail -n 1
}

download_archive() {
    local ver="$1"
    local dest_dir="$2"
    local base url file final_file part_file
    base="https://download.whonix.org/libvirt/${ver}"
    mkdir -p "${dest_dir}"

    local candidates=(
        "Whonix-CLI-${ver}.Intel_AMD64.qcow2.libvirt.xz"
        "Whonix-LXQt-${ver}.Intel_AMD64.qcow2.libvirt.xz"
        "Whonix-Xfce-${ver}.Intel_AMD64.qcow2.libvirt.xz"
    )

    for file in "${candidates[@]}"; do
        url="${base}/${file}"
        if no_proxy_curl -fsI "${url}" >/dev/null 2>&1; then
            final_file="${dest_dir}/${file}"
            part_file="${final_file}.part"

            if [[ -f "${final_file}" ]] && validate_archive "${final_file}"; then
                info "Using existing verified archive: ${final_file}"
                printf "%s\n" "${final_file}"
                return 0
            fi

            if [[ -f "${final_file}" ]] && ! validate_archive "${final_file}"; then
                warn "Existing archive appears incomplete/corrupt; attempting resume from existing bytes."
                if [[ ! -f "${part_file}" ]]; then
                    mv -f "${final_file}" "${part_file}"
                elif [[ "${final_file}" -nt "${part_file}" ]]; then
                    mv -f "${final_file}" "${part_file}"
                else
                    rm -f "${final_file}"
                fi
            fi

            info "Downloading (resumable) ${url}"
            if ! download_with_lock "${url}" "${part_file}"; then
                return 1
            fi

            if ! validate_archive "${part_file}"; then
                warn "Downloaded archive is not complete yet (or is corrupt): ${part_file}"
                return 1
            fi

            mv -f "${part_file}" "${final_file}"
            printf "%s\n" "${final_file}"
            return 0
        fi
    done

    return 1
}

find_local_archive() {
    local dir="$1"
    local pattern
    if [[ ! -d "${dir}" ]]; then
        return 1
    fi
    for pattern in \
        'Whonix-CLI-*.qcow2.libvirt.xz' \
        'Whonix-LXQt-*.qcow2.libvirt.xz' \
        'Whonix-Xfce-*.qcow2.libvirt.xz' \
        'Whonix-*.qcow2.libvirt.xz'; do
        local candidate
        candidate="$(find "${dir}" -maxdepth 1 -type f -name "${pattern}" | sort -V | tail -n 1)"
        [[ -z "${candidate}" ]] && continue

        if validate_archive "${candidate}"; then
            printf "%s\n" "${candidate}"
            return 0
        fi

        warn "Skipping invalid local archive: ${candidate}" >&2
    done
    return 1
}

extract_file() {
    local pattern="$1"
    local dir="$2"
    find "${dir}" -maxdepth 2 -type f -name "${pattern}" | head -n 1
}

domain_name_from_xml() {
    local xml="$1"
    awk -F'[<>]' '/<name>/{print $3; exit}' "${xml}"
}

network_name_from_xml() {
    local xml="$1"
    awk -F'[<>]' '/<name>/{print $3; exit}' "${xml}"
}

is_network_active() {
    local net_name="$1"
    run_virsh net-list --name 2>/dev/null | grep -Fxq "${net_name}"
}

network_bridge_name() {
    local net_name="$1"
    run_virsh net-dumpxml "${net_name}" 2>/dev/null | awk -F"'" '/<bridge name=/{print $2; exit}'
}

bridge_has_ipv4() {
    local bridge="$1"
    ip -o -4 addr show dev "${bridge}" 2>/dev/null | grep -q 'inet '
}

ensure_internal_bridge_host_ip() {
    local net_name="$1"
    local bridge cidr
    bridge="$(network_bridge_name "${net_name}")"
    [[ -z "${bridge}" ]] && return 1
    cidr="${K1_WHONIX_INTERNAL_HOST_CIDR:-10.152.152.11/18}"
    if bridge_has_ipv4 "${bridge}"; then
        return 0
    fi
    info "Assigning host IP ${cidr} to ${bridge} for Whonix proxy reachability"
    ip addr add "${cidr}" dev "${bridge}" >/dev/null 2>&1 || true
    bridge_has_ipv4 "${bridge}"
}

need_cmd virsh
need_cmd curl
need_cmd tar
need_cmd python3
need_cmd ip

IMAGE_DIR="/var/lib/libvirt/images"
if [[ "${URI}" == "qemu:///session" ]]; then
    IMAGE_DIR="${HOME}/.local/share/libvirt/images"
fi

info "Using libvirt URI: ${URI}"
if ! run_virsh list --all >/dev/null 2>&1; then
    if [[ "${URI}" == "qemu:///system" ]] && virsh -c qemu:///session list --all >/dev/null 2>&1; then
        warn "Cannot access qemu:///system in this shell; falling back to qemu:///session."
        URI="qemu:///session"
        IMAGE_DIR="${HOME}/.local/share/libvirt/images"
    else
        error "Cannot access libvirt URI ${URI}."
        error "Ensure libvirtd is running and your user has libvirt access."
        exit 1
    fi
fi

if [[ -z "${ARCHIVE_PATH}" && "${FORCE_DOWNLOAD}" == "false" ]]; then
    ARCHIVE_PATH="$(find_local_archive "${DOWNLOAD_DIR}" || true)"
fi

if [[ -z "${ARCHIVE_PATH}" || "${FORCE_DOWNLOAD}" == "true" ]]; then
    if [[ -z "${VERSION}" ]]; then
        info "Detecting latest Whonix libvirt version..."
        VERSION="$(detect_latest_version || true)"
        if [[ -z "${VERSION}" ]]; then
            error "Unable to detect latest Whonix version from download.whonix.org."
            error "Pass --version <x.y.z.w> or --archive <path>."
            exit 1
        fi
    fi
    ARCHIVE_PATH="$(download_archive "${VERSION}" "${DOWNLOAD_DIR}" || true)"
    if [[ -z "${ARCHIVE_PATH}" ]]; then
        error "Whonix download failed."
        error "Pass --archive /absolute/path/to/Whonix-*.qcow2.libvirt.xz"
        exit 1
    fi
fi

if [[ ! -f "${ARCHIVE_PATH}" ]]; then
    error "Archive not found: ${ARCHIVE_PATH}"
    exit 1
fi

if ! validate_archive "${ARCHIVE_PATH}"; then
    error "Archive validation failed (incomplete/corrupt): ${ARCHIVE_PATH}"
    error "Re-run with --force-download (or provide a complete --archive path)."
    exit 1
fi

info "Using archive: ${ARCHIVE_PATH}"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "${TMP_DIR}"' EXIT

info "Extracting Whonix archive..."
tar -xvf "${ARCHIVE_PATH}" -C "${TMP_DIR}" >/dev/null

ext_net_xml="$(extract_file 'Whonix_external*.xml' "${TMP_DIR}")"
int_net_xml="$(extract_file 'Whonix_internal*.xml' "${TMP_DIR}")"
gw_xml="$(extract_file 'Whonix-Gateway*.xml' "${TMP_DIR}")"
ws_xml="$(extract_file 'Whonix-Workstation*.xml' "${TMP_DIR}")"
gw_qcow="$(extract_file 'Whonix-Gateway*.qcow2' "${TMP_DIR}")"
ws_qcow="$(extract_file 'Whonix-Workstation*.qcow2' "${TMP_DIR}")"

for req in "${ext_net_xml}" "${int_net_xml}" "${gw_xml}" "${ws_xml}" "${gw_qcow}" "${ws_qcow}"; do
    if [[ -z "${req}" ]]; then
        error "Archive format mismatch: expected Whonix libvirt bundle files not found."
        exit 1
    fi
done

for net_xml in "${ext_net_xml}" "${int_net_xml}"; do
    net_name="$(network_name_from_xml "${net_xml}")"
    if ! run_virsh net-info "${net_name}" >/dev/null 2>&1; then
        info "Defining network ${net_name}"
        run_virsh net-define "${net_xml}" >/dev/null
    else
        info "Network ${net_name} already defined"
    fi
    run_virsh net-autostart "${net_name}" >/dev/null || true
    if ! is_network_active "${net_name}"; then
        start_err=""
        info "Starting network ${net_name}"
        if ! start_err="$(run_virsh net-start "${net_name}" 2>&1 >/dev/null)"; then
            # Race-safe: treat a failed start as non-fatal when the network is
            # already active by the time we re-check state.
            if is_network_active "${net_name}"; then
                info "Network ${net_name} became active."
            else
                if [[ "${URI}" == "qemu:///session" ]]; then
                    error "Unable to start ${net_name} on qemu:///session (bridge creation is not permitted)."
                    error "Whonix KVM requires qemu:///system with libvirt network privileges."
                    error "Run this once in a terminal with sudo access:"
                    error "  K1_WHONIX_LIBVIRT_URI=qemu:///system ./scripts/setup_whonix_kvm.sh --archive ${ARCHIVE_PATH}"
                else
                    error "Failed to start libvirt network ${net_name}."
                fi
                [[ -n "${start_err}" ]] && error "${start_err}"
                exit 1
            fi
        fi
    fi
    if ! is_network_active "${net_name}"; then
        error "Network ${net_name} is not active after setup."
        exit 1
    fi
done

gw_domain="$(domain_name_from_xml "${gw_xml}")"
ws_domain="$(domain_name_from_xml "${ws_xml}")"

if ! run_virsh dominfo "${gw_domain}" >/dev/null 2>&1; then
    info "Defining domain ${gw_domain}"
    run_virsh define "${gw_xml}" >/dev/null
else
    info "Domain ${gw_domain} already defined"
fi

if ! run_virsh dominfo "${ws_domain}" >/dev/null 2>&1; then
    info "Defining domain ${ws_domain}"
    run_virsh define "${ws_xml}" >/dev/null
else
    info "Domain ${ws_domain} already defined"
fi

target_gw="${IMAGE_DIR}/Whonix-Gateway.qcow2"
target_ws="${IMAGE_DIR}/Whonix-Workstation.qcow2"

if [[ "${URI}" == "qemu:///session" ]]; then
    mkdir -p "${IMAGE_DIR}"
else
    sudo mkdir -p "${IMAGE_DIR}"
fi

if [[ "${FORCE_IMAGE_COPY}" == "true" || ! -f "${target_gw}" ]]; then
    info "Installing ${target_gw}"
    if [[ "${URI}" == "qemu:///session" ]]; then
        cp -f "${gw_qcow}" "${target_gw}"
    else
        sudo cp -f "${gw_qcow}" "${target_gw}"
    fi
else
    info "Keeping existing ${target_gw}"
fi

if [[ "${FORCE_IMAGE_COPY}" == "true" || ! -f "${target_ws}" ]]; then
    info "Installing ${target_ws}"
    if [[ "${URI}" == "qemu:///session" ]]; then
        cp -f "${ws_qcow}" "${target_ws}"
    else
        sudo cp -f "${ws_qcow}" "${target_ws}"
    fi
else
    info "Keeping existing ${target_ws}"
fi

gw_state="$(run_virsh domstate "${gw_domain}" 2>/dev/null | tr '[:upper:]' '[:lower:]' || true)"
if [[ "${gw_state}" != *"running"* ]]; then
    info "Starting ${gw_domain}"
    run_virsh start "${gw_domain}" >/dev/null
fi

proxy_host="${K1_WHONIX_PROXY_HOST:-10.152.152.10}"
proxy_port="${K1_WHONIX_PROXY_PORT:-9050}"

if [[ "${URI}" == "qemu:///system" && "${proxy_host}" == "10.152.152.10" ]]; then
    if ! ensure_internal_bridge_host_ip "Whonix-Internal"; then
        warn "Unable to confirm host IPv4 on Whonix-Internal bridge; proxy check may fail."
    fi
fi

info "Waiting for Whonix proxy at ${proxy_host}:${proxy_port} (timeout: ${PROXY_WAIT_SECONDS}s)..."
elapsed=0
while ! is_port_open "${proxy_host}" "${proxy_port}"; do
    sleep 3
    elapsed=$((elapsed + 3))
    if (( elapsed >= PROXY_WAIT_SECONDS )); then
        error "Proxy ${proxy_host}:${proxy_port} is still unreachable after ${PROXY_WAIT_SECONDS}s."
        error "Finish Whonix first boot wizard and wait for Tor bootstrap, then re-run setup."
        exit 1
    fi
done
info "Proxy reachable at ${proxy_host}:${proxy_port}"

upsert_env "K1_ENFORCE_WHONIX_KVM" "true"
upsert_env "K1_WHONIX_LIBVIRT_URI" "${URI}"
upsert_env "K1_WHONIX_VM_NAMES" "${gw_domain}"
upsert_env "K1_WHONIX_PROXY_HOST" "${proxy_host}"
upsert_env "K1_WHONIX_PROXY_PORT" "${proxy_port}"
upsert_env "HTTP_PROXY" "http://${proxy_host}:${proxy_port}"
upsert_env "HTTPS_PROXY" "http://${proxy_host}:${proxy_port}"
upsert_env "NO_PROXY" "127.0.0.1,localhost,postgres,redis,vault,ollama"
upsert_env "no_proxy" "127.0.0.1,localhost,postgres,redis,vault,ollama"

info "Whonix KVM setup complete."
info "Updated ${ENV_FILE} with libvirt URI, VM name, and proxy settings."
echo "Next steps:"
echo "  1) virsh -c ${URI} list --all"
echo "  2) virsh -c ${URI} domstate ${gw_domain}"
echo "  3) cd ${REPO_ROOT} && ./k1-start"
