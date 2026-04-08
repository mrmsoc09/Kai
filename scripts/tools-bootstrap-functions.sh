#!/usr/bin/env bash
# Wave 7 Tool Installation Functions
# Handles installation of testssl.sh, spiderfoot, and graphql-cop
# with proper error handling and verification logging

set -euo pipefail

# Color output (shared with setup.sh)
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info() { echo -e "${GREEN}[k1-tools]${NC} $*"; }
warn() { echo -e "${YELLOW}[k1-tools]${NC} $*"; }
error() { echo -e "${RED}[k1-tools]${NC} $*" >&2; }

# Install testssl.sh from official GitHub repo
install_testssl() {
    local tools_base="${HOME}/.local/share/kaison-tools"
    local bin_dir="${HOME}/.local/bin"
    local testssl_dir="${tools_base}/testssl"

    mkdir -p "${tools_base}" "${bin_dir}"

    if [[ -d "${testssl_dir}" ]]; then
        info "testssl.sh already installed at ${testssl_dir}"
        # Ensure symlink exists
        if [[ ! -L "${bin_dir}/testssl.sh" ]]; then
            ln -sf "${testssl_dir}/testssl.sh" "${bin_dir}/testssl.sh"
            info "Created symlink: ${bin_dir}/testssl.sh"
        fi
        return 0
    fi

    info "Installing testssl.sh from https://github.com/testssl/testssl.sh.git"

    if ! git clone --depth 1 https://github.com/testssl/testssl.sh.git "${testssl_dir}" 2>/dev/null; then
        error "Failed to clone testssl.sh repository"
        return 1
    fi

    if [[ ! -f "${testssl_dir}/testssl.sh" ]]; then
        error "testssl.sh script not found after clone"
        rm -rf "${testssl_dir}"
        return 1
    fi

    chmod +x "${testssl_dir}/testssl.sh"

    # Create symlink in ~/.local/bin/
    ln -sf "${testssl_dir}/testssl.sh" "${bin_dir}/testssl.sh"

    if ! "${bin_dir}/testssl.sh" --version >/dev/null 2>&1; then
        error "testssl.sh verification failed (--version test)"
        return 1
    fi

    info "testssl.sh installed successfully at ${testssl_dir}"
    return 0
}

# Install spiderfoot from official GitHub repo
install_spiderfoot() {
    local tools_base="${HOME}/.local/share/kaison-tools"
    local bin_dir="${HOME}/.local/bin"
    local spiderfoot_dir="${tools_base}/spiderfoot"

    mkdir -p "${tools_base}" "${bin_dir}"

    if [[ -d "${spiderfoot_dir}" ]]; then
        info "spiderfoot already installed at ${spiderfoot_dir}"
        # Ensure wrapper exists
        if [[ ! -f "${bin_dir}/spiderfoot" ]]; then
            create_spiderfoot_wrapper "${spiderfoot_dir}" "${bin_dir}"
        fi
        return 0
    fi

    info "Installing spiderfoot from https://github.com/smicallef/spiderfoot.git"

    if ! git clone --depth 1 https://github.com/smicallef/spiderfoot.git "${spiderfoot_dir}" 2>/dev/null; then
        error "Failed to clone spiderfoot repository"
        return 1
    fi

    if [[ ! -f "${spiderfoot_dir}/sf.py" ]]; then
        error "sf.py not found in spiderfoot repository"
        rm -rf "${spiderfoot_dir}"
        return 1
    fi

    # Install Python dependencies
    info "Installing spiderfoot Python dependencies..."
    if ! (cd "${spiderfoot_dir}" && pip install -q -r requirements.txt 2>/dev/null); then
        warn "spiderfoot dependency installation had issues, attempting to continue"
    fi

    create_spiderfoot_wrapper "${spiderfoot_dir}" "${bin_dir}"

    if ! "${bin_dir}/spiderfoot" --version >/dev/null 2>&1; then
        warn "spiderfoot --version test failed, but installation may still be functional"
    fi

    info "spiderfoot installed successfully at ${spiderfoot_dir}"
    return 0
}

# Create wrapper script for spiderfoot to call sf.py
create_spiderfoot_wrapper() {
    local spiderfoot_dir="$1"
    local bin_dir="$2"

    cat > "${bin_dir}/spiderfoot" <<'EOF'
#!/usr/bin/env bash
# spiderfoot wrapper — calls sf.py from spiderfoot installation
SPIDERFOOT_DIR="${SPIDERFOOT_DIR:-}"
if [[ -z "${SPIDERFOOT_DIR}" ]]; then
    # Try to locate spiderfoot installation
    SPIDERFOOT_DIR="$(python3 -c "import spiderfoot; import os; print(os.path.dirname(spiderfoot.__file__))" 2>/dev/null || echo "")"
    if [[ -z "${SPIDERFOOT_DIR}" ]]; then
        SPIDERFOOT_DIR="${HOME}/.local/share/kaison-tools/spiderfoot"
    fi
fi

if [[ ! -f "${SPIDERFOOT_DIR}/sf.py" ]]; then
    echo "Error: spiderfoot installation not found at ${SPIDERFOOT_DIR}" >&2
    exit 1
fi

cd "${SPIDERFOOT_DIR}" || exit 1
exec python3 sf.py "$@"
EOF

    chmod +x "${bin_dir}/spiderfoot"
}

# Install graphql-cop from GitHub (binary or source)
install_graphql_cop() {
    local tools_base="${HOME}/.local/share/kaison-tools"
    local bin_dir="${HOME}/.local/bin"
    local graphql_cop_dir="${tools_base}/graphql-cop"

    mkdir -p "${tools_base}" "${bin_dir}"

    if command -v graphql-cop >/dev/null 2>&1; then
        info "graphql-cop already available in PATH"
        return 0
    fi

    if [[ -d "${graphql_cop_dir}" ]]; then
        info "graphql-cop source already installed at ${graphql_cop_dir}"
        # Try to build if not already
        if [[ ! -f "${bin_dir}/graphql-cop" ]]; then
            build_graphql_cop_from_source "${graphql_cop_dir}" "${bin_dir}"
        fi
        return 0
    fi

    # Try to download pre-built binary first
    if try_graphql_cop_binary "${bin_dir}"; then
        info "graphql-cop binary installed successfully"
        return 0
    fi

    warn "Pre-built binary not available, building from source"

    # Fall back to source build
    info "Installing graphql-cop from https://github.com/dolevf/graphql-cop.git"

    if ! git clone --depth 1 https://github.com/dolevf/graphql-cop.git "${graphql_cop_dir}" 2>/dev/null; then
        error "Failed to clone graphql-cop repository"
        return 1
    fi

    if ! build_graphql_cop_from_source "${graphql_cop_dir}" "${bin_dir}"; then
        error "Failed to build graphql-cop from source"
        rm -rf "${graphql_cop_dir}"
        return 1
    fi

    info "graphql-cop installed successfully at ${graphql_cop_dir}"
    return 0
}

# Attempt to download pre-built binary for graphql-cop
try_graphql_cop_binary() {
    local bin_dir="$1"
    local arch

    # Detect platform
    if [[ "$(uname)" != "Linux" ]]; then
        return 1
    fi

    arch="$(uname -m)"
    case "${arch}" in
        x86_64) arch="amd64" ;;
        aarch64) arch="arm64" ;;
        *)
            warn "Unsupported architecture: ${arch}"
            return 1
            ;;
    esac

    local latest_release
    latest_release="$(
        curl -s https://api.github.com/repos/dolevf/graphql-cop/releases/latest \
            | grep -oP '"tag_name": "\K.*?(?=")' || true
    )"

    if [[ -z "${latest_release}" ]]; then
        return 1
    fi

    local binary_url="https://github.com/dolevf/graphql-cop/releases/download/${latest_release}/graphql-cop_${latest_release#v}_linux_${arch}"

    info "Downloading graphql-cop binary: ${binary_url}"

    if curl -sL "${binary_url}" -o "${bin_dir}/graphql-cop" 2>/dev/null; then
        chmod +x "${bin_dir}/graphql-cop"

        # Verify binary works
        if "${bin_dir}/graphql-cop" --help >/dev/null 2>&1; then
            return 0
        fi
    fi

    rm -f "${bin_dir}/graphql-cop"
    return 1
}

# Build graphql-cop from source
build_graphql_cop_from_source() {
    local graphql_cop_dir="$1"
    local bin_dir="$2"

    if ! command -v pip >/dev/null 2>&1 && ! command -v pip3 >/dev/null 2>&1; then
        error "pip/pip3 required to build graphql-cop from source"
        return 1
    fi

    info "Building graphql-cop from source..."

    if ! (cd "${graphql_cop_dir}" && pip install -q -e . 2>/dev/null); then
        error "Failed to install graphql-cop via pip"
        return 1
    fi

    # Create wrapper script if graphql-cop is not in PATH
    local graphql_cop_bin
    graphql_cop_bin="$(python3 -c "import shutil; print(shutil.which('graphql-cop'))" 2>/dev/null || true)"

    if [[ -z "${graphql_cop_bin}" ]]; then
        # Create wrapper for module call
        cat > "${bin_dir}/graphql-cop" <<'EOF'
#!/usr/bin/env bash
exec python3 -m graphql_cop "$@"
EOF
        chmod +x "${bin_dir}/graphql-cop"
    else
        # Create symlink to found binary
        ln -sf "${graphql_cop_bin}" "${bin_dir}/graphql-cop"
    fi

    return 0
}

# Main installation coordinator
install_wave7_tools() {
    local failed=0

    info "Starting Wave 7 tool installation"

    # testssl.sh
    if install_testssl; then
        info "✓ testssl.sh ready"
    else
        error "✗ testssl.sh installation failed"
        ((failed++))
    fi

    # spiderfoot
    if install_spiderfoot; then
        info "✓ spiderfoot ready"
    else
        error "✗ spiderfoot installation failed"
        ((failed++))
    fi

    # graphql-cop
    if install_graphql_cop; then
        info "✓ graphql-cop ready"
    else
        error "✗ graphql-cop installation failed"
        ((failed++))
    fi

    if [[ ${failed} -eq 0 ]]; then
        info "All Wave 7 tools installed successfully"
        return 0
    else
        warn "${failed} Wave 7 tool(s) failed to install"
        return 1
    fi
}

# Export functions for use in setup.sh
export -f install_testssl
export -f install_spiderfoot
export -f install_graphql_cop
export -f install_wave7_tools
export -f create_spiderfoot_wrapper
export -f try_graphql_cop_binary
export -f build_graphql_cop_from_source
