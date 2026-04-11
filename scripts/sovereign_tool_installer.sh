#!/usr/bin/env bash
# Sovereign Tool Installer — Build-Based Installation with System Dependency Baseline
# Implements build-from-source methodology for offensive security tools
# Usage: source sovereign_tool_installer.sh

set -euo pipefail

# ============================================================================
# SYSTEM DEPENDENCY BASELINE
# ============================================================================

# All build dependencies required before tool installation
SYSTEM_BUILD_DEPS=(
    build-essential
    libpcap-dev
    python3-dev
    libssl-dev
    libffi-dev
    libxml2-dev
    libxslt1-dev
    ruby-dev
    pkg-config
)

ensure_system_deps() {
    local missing=()
    local prefix
    prefix="$(apt_prefix)"

    if ! can_use_apt; then
        error "apt-get not available. Install system dependencies manually:"
        printf "  %s\n" "${SYSTEM_BUILD_DEPS[@]}"
        return 1
    fi

    info "Checking system build dependency baseline..."

    for pkg in "${SYSTEM_BUILD_DEPS[@]}"; do
        if ! dpkg -l | grep -qE "^ii.*${pkg}"; then
            missing+=("${pkg}")
        fi
    done

    if [[ ${#missing[@]} -eq 0 ]]; then
        info "System dependency baseline satisfied"
        return 0
    fi

    warn "Missing system dependencies: ${missing[*]}"
    info "Installing system build dependencies..."

    if ! apt_install_packages "${missing[@]}"; then
        error "Failed to install system dependencies. Manual installation required:"
        printf "  sudo apt-get install %s\n" "${missing[@]}"
        return 1
    fi

    info "System dependency baseline established"
    return 0
}

# ============================================================================
# TOOL-SPECIFIC BUILD BLOCKS
# ============================================================================

verify_tool_installed() {
    local tool="$1"
    local verify_cmd="${2:-}"

    if [[ -z "${verify_cmd}" ]]; then
        verify_cmd="${tool}"
    fi

    if command -v "${verify_cmd}" >/dev/null 2>&1; then
        "${verify_cmd}" --version 2>/dev/null || "${verify_cmd}" -v 2>/dev/null || return 0
        return 0
    fi

    return 1
}

# Masscan: Clone, build with libpcap, and symlink
install_masscan() {
    local src_dir="${LOCAL_TOOLS_SRC_DIR}/masscan"

    if verify_tool_installed "masscan" "masscan"; then
        info "Masscan already installed and verified"
        return 0
    fi

    info "Building Masscan from source..."
    ensure_local_bin

    # Ensure system dependencies
    if ! apt_install_packages libpcap-dev 2>/dev/null; then
        error "Masscan: Failed to install libpcap-dev (required for source build)"
        return 1
    fi

    # Clone and build
    clone_or_update_repo "https://github.com/robertdavidgraham/masscan.git" "${src_dir}" || {
        error "Masscan: Failed to clone repository"
        return 1
    }

    if ! (cd "${src_dir}" && make -j"$(nproc)" clean && make -j"$(nproc)"); then
        error "Masscan: Build failed"
        return 1
    fi

    if [[ ! -f "${src_dir}/bin/masscan" ]]; then
        error "Masscan: Binary not found after build"
        return 1
    fi

    cp "${src_dir}/bin/masscan" "${LOCAL_BIN_DIR}/masscan"
    chmod +x "${LOCAL_BIN_DIR}/masscan"

    # Verify installation
    if verify_tool_installed "masscan" "masscan"; then
        info "Masscan: Installation verified"
        return 0
    fi

    error "Masscan: Post-install verification failed"
    return 1
}

# Metasploit Framework: Official omnibus installer
install_metasploit() {
    if verify_tool_installed "msfconsole" "msfconsole"; then
        info "Metasploit Framework already installed and verified"
        return 0
    fi

    # Try apt package first
    if apt_install_packages metasploit-framework 2>/dev/null; then
        if verify_tool_installed "msfconsole" "msfconsole"; then
            info "Metasploit Framework: Installed from apt"
            return 0
        fi
    fi

    info "Installing Metasploit Framework via official omnibus installer..."
    local tmp_installer="/tmp/msfinstall-$(date +%s)"
    local install_dir="${LOCAL_TOOLS_SRC_DIR}/metasploit-omnibus"

    mkdir -p "${install_dir}"

    if ! curl -fsSL "https://raw.githubusercontent.com/rapid7/metasploit-omnibus/master/config/templates/metasploit-framework-wrappers/msfupdate.erb" \
         -o "${tmp_installer}"; then
        error "Metasploit: Failed to download omnibus installer"
        return 1
    fi

    chmod +x "${tmp_installer}"

    if ! "${tmp_installer}" >/dev/null 2>&1; then
        error "Metasploit: Omnibus installation failed"
        rm -f "${tmp_installer}"
        return 1
    fi

    rm -f "${tmp_installer}"

    if verify_tool_installed "msfconsole" "msfconsole"; then
        info "Metasploit Framework: Installation verified"
        return 0
    fi

    error "Metasploit: Post-install verification failed"
    return 1
}

# EyeWitness: Clone and setup
install_eyewitness() {
    local src_dir="${LOCAL_TOOLS_SRC_DIR}/EyeWitness"

    if verify_tool_installed "eyewitness" "eyewitness"; then
        info "EyeWitness already installed and verified"
        return 0
    fi

    info "Building EyeWitness from source..."
    ensure_local_bin

    clone_or_update_repo "https://github.com/RedSiege/EyeWitness.git" "${src_dir}" || {
        error "EyeWitness: Failed to clone repository"
        return 1
    }

    # Install Python dependencies
    if [[ -f "${src_dir}/Python/requirements.txt" ]]; then
        if ! python3 -m pip install -r "${src_dir}/Python/requirements.txt" >/dev/null 2>&1; then
            warn "EyeWitness: Some Python dependencies failed (non-critical)"
        fi
    fi

    # Create wrapper script
    cat > "${LOCAL_BIN_DIR}/eyewitness" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)/.local/share/kaison-tools/EyeWitness"

if [[ -f "${SRC_DIR}/Python/EyeWitness.py" ]]; then
    exec python3 "${SRC_DIR}/Python/EyeWitness.py" "$@"
elif [[ -f "${SRC_DIR}/EyeWitness.py" ]]; then
    exec python3 "${SRC_DIR}/EyeWitness.py" "$@"
else
    echo "EyeWitness.py not found in ${SRC_DIR}" >&2
    exit 1
fi
EOF

    chmod +x "${LOCAL_BIN_DIR}/eyewitness"

    if verify_tool_installed "eyewitness" "eyewitness"; then
        info "EyeWitness: Installation verified"
        return 0
    fi

    error "EyeWitness: Post-install verification failed"
    return 1
}

# Arjun: Clone and pip install
install_arjun() {
    local src_dir="${LOCAL_TOOLS_SRC_DIR}/Arjun"

    if verify_tool_installed "arjun" "arjun"; then
        info "Arjun already installed and verified"
        return 0
    fi

    info "Installing Arjun from source..."

    clone_or_update_repo "https://github.com/s0md3v/Arjun.git" "${src_dir}" || {
        error "Arjun: Failed to clone repository"
        return 1
    }

    if ! (cd "${src_dir}" && python3 -m pip install --quiet . 2>&1 | grep -v "Requirement already satisfied" || true); then
        error "Arjun: pip install failed"
        return 1
    fi

    if verify_tool_installed "arjun" "arjun"; then
        info "Arjun: Installation verified"
        return 0
    fi

    error "Arjun: Post-install verification failed"
    return 1
}

# Spiderfoot: Clone and setup venv
install_spiderfoot() {
    local src_dir="${LOCAL_TOOLS_SRC_DIR}/spiderfoot"
    local venv_dir="${src_dir}/venv"

    if verify_tool_installed "spiderfoot" "spiderfoot"; then
        info "Spiderfoot already installed and verified"
        return 0
    fi

    info "Building Spiderfoot from source..."

    clone_or_update_repo "https://github.com/smicallef/spiderfoot.git" "${src_dir}" || {
        error "Spiderfoot: Failed to clone repository"
        return 1
    }

    # Create virtual environment and install
    if [[ ! -d "${venv_dir}" ]]; then
        python3 -m venv "${venv_dir}"
    fi

    # shellcheck disable=SC1090
    source "${venv_dir}/bin/activate"

    if ! python3 -m pip install --quiet -r "${src_dir}/requirements.txt" 2>&1 | grep -v "Requirement already satisfied" || true; then
        error "Spiderfoot: pip install failed"
        deactivate 2>/dev/null || true
        return 1
    fi

    ensure_local_bin

    # Create wrapper script
    cat > "${LOCAL_BIN_DIR}/spiderfoot" <<EOF
#!/usr/bin/env bash
exec "${venv_dir}/bin/python3" "${src_dir}/sf.py" "\$@"
EOF

    chmod +x "${LOCAL_BIN_DIR}/spiderfoot"
    deactivate 2>/dev/null || true

    if verify_tool_installed "spiderfoot" "spiderfoot"; then
        info "Spiderfoot: Installation verified"
        return 0
    fi

    error "Spiderfoot: Post-install verification failed"
    return 1
}

# ReconFTW: Clone and run install script
install_reconftw() {
    local src_dir="${LOCAL_TOOLS_SRC_DIR}/reconftw"

    if verify_tool_installed "reconftw" "reconftw"; then
        info "ReconFTW already installed and verified"
        return 0
    fi

    info "Installing ReconFTW from source..."
    ensure_local_bin

    clone_or_update_repo "https://github.com/six2dez/reconftw.git" "${src_dir}" || {
        error "ReconFTW: Failed to clone repository"
        return 1
    }

    if [[ -f "${src_dir}/install.sh" ]]; then
        if ! (cd "${src_dir}" && bash install.sh >/dev/null 2>&1); then
            error "ReconFTW: install.sh failed"
            return 1
        fi
    fi

    local script_path=""
    if [[ -f "${src_dir}/reconftw.sh" ]]; then
        script_path="${src_dir}/reconftw.sh"
    elif [[ -f "${src_dir}/reconftw" ]]; then
        script_path="${src_dir}/reconftw"
    else
        error "ReconFTW: Script not found after install"
        return 1
    fi

    cp "${script_path}" "${LOCAL_BIN_DIR}/reconftw.sh"
    chmod +x "${LOCAL_BIN_DIR}/reconftw.sh"
    ln -sf "${LOCAL_BIN_DIR}/reconftw.sh" "${LOCAL_BIN_DIR}/reconftw"

    if verify_tool_installed "reconftw" "reconftw"; then
        info "ReconFTW: Installation verified"
        return 0
    fi

    error "ReconFTW: Post-install verification failed"
    return 1
}

# TorBot: Clone and pip install with python3-dev check
install_torbot() {
    local src_dir="${LOCAL_TOOLS_SRC_DIR}/TorBot"

    if verify_tool_installed "torbot" "torbot"; then
        info "TorBot already installed and verified"
        return 0
    fi

    info "Installing TorBot from source..."

    # Ensure python3-dev to prevent numpy build failures
    if ! apt_install_packages python3-dev 2>/dev/null; then
        error "TorBot: Failed to install python3-dev (required for numpy)"
        return 1
    fi

    clone_or_update_repo "https://github.com/DedSecInside/TorBot.git" "${src_dir}" || {
        error "TorBot: Failed to clone repository"
        return 1
    }

    if ! (cd "${src_dir}" && python3 -m pip install --quiet -r requirements.txt 2>&1 | grep -v "Requirement already satisfied" || true); then
        error "TorBot: pip install failed"
        return 1
    fi

    if verify_tool_installed "torbot" "torbot"; then
        info "TorBot: Installation verified"
        return 0
    fi

    error "TorBot: Post-install verification failed"
    return 1
}

# Trufflehog: Install via Go
install_trufflehog() {
    if verify_tool_installed "trufflehog" "trufflehog"; then
        info "Trufflehog already installed and verified"
        return 0
    fi

    info "Installing Trufflehog via Go..."

    if ! ensure_go; then
        error "Trufflehog: Go installation failed"
        return 1
    fi

    ensure_local_bin
    export GOBIN="${LOCAL_BIN_DIR}"
    mkdir -p "${GOBIN}"

    if ! GO111MODULE=on go install github.com/trufflesecurity/trufflehog/v3@latest >/dev/null 2>&1; then
        error "Trufflehog: go install failed"
        return 1
    fi

    if verify_tool_installed "trufflehog" "trufflehog"; then
        info "Trufflehog: Installation verified"
        return 0
    fi

    error "Trufflehog: Post-install verification failed"
    return 1
}

# Searchsploit: Clone and symlink
install_searchsploit() {
    local src_dir="${LOCAL_TOOLS_SRC_DIR}/searchsploit"

    if verify_tool_installed "searchsploit" "searchsploit"; then
        info "Searchsploit already installed and verified"
        return 0
    fi

    # Try apt package first
    if apt_install_packages exploitdb 2>/dev/null; then
        if verify_tool_installed "searchsploit" "searchsploit"; then
            info "Searchsploit: Installed from apt"
            return 0
        fi
    fi

    info "Installing Searchsploit from source..."
    ensure_local_bin

    clone_or_update_repo "https://github.com/JitPatro/searchsploit.git" "${src_dir}" || {
        error "Searchsploit: Failed to clone repository"
        return 1
    }

    local script_path=""
    if [[ -x "${src_dir}/searchsploit" ]]; then
        script_path="${src_dir}/searchsploit"
        ln -sf "${script_path}" "${LOCAL_BIN_DIR}/searchsploit"
    elif [[ -f "${src_dir}/searchsploit.py" ]]; then
        cat > "${LOCAL_BIN_DIR}/searchsploit" <<EOF
#!/usr/bin/env bash
exec python3 "${src_dir}/searchsploit.py" "\$@"
EOF
        chmod +x "${LOCAL_BIN_DIR}/searchsploit"
    else
        error "Searchsploit: No executable found after clone"
        return 1
    fi

    if verify_tool_installed "searchsploit" "searchsploit"; then
        info "Searchsploit: Installation verified"
        return 0
    fi

    error "Searchsploit: Post-install verification failed"
    return 1
}

# Caido: Download latest CLI binary
install_caido() {
    if verify_tool_installed "caido" "caido"; then
        info "Caido already installed and verified"
        return 0
    fi

    info "Installing Caido CLI..."
    ensure_local_bin

    local releases_url="https://api.github.com/repos/caido/caido/releases/latest"
    local download_url=""

    # Detect platform
    local platform
    case "$(uname -s)" in
        Linux)
            platform="linux"
            ;;
        Darwin)
            platform="macos"
            ;;
        *)
            error "Caido: Unsupported platform"
            return 1
            ;;
    esac

    # Get latest release download URL
    download_url=$(curl -fsSL "${releases_url}" | grep -o "\"browser_download_url\": \"https://github.com/caido/caido/releases/download/[^\"]*${platform}[^\"]*\"" | head -1 | cut -d'"' -f4)

    if [[ -z "${download_url}" ]]; then
        error "Caido: Could not find download URL for platform ${platform}"
        return 1
    fi

    if ! curl -fsSL "${download_url}" -o "${LOCAL_BIN_DIR}/caido"; then
        error "Caido: Download failed"
        return 1
    fi

    chmod +x "${LOCAL_BIN_DIR}/caido"

    if verify_tool_installed "caido" "caido"; then
        info "Caido: Installation verified"
        return 0
    fi

    error "Caido: Post-install verification failed"
    return 1
}

# Faraday: Clone and prepare source
install_faraday() {
    local src_dir="${LOCAL_TOOLS_SRC_DIR}/faraday"

    info "Preparing Faraday source..."

    clone_or_update_repo "https://github.com/infobyte/faraday.git" "${src_dir}" || {
        error "Faraday: Failed to clone repository"
        return 1
    }

    if [[ -f "${src_dir}/requirements.txt" ]]; then
        if ! python3 -m pip install --quiet -r "${src_dir}/requirements.txt" 2>&1 | grep -v "Requirement already satisfied" || true; then
            warn "Faraday: Some Python dependencies failed (non-critical)"
        fi
    fi

    info "Faraday: Source prepared at ${src_dir}"
    return 0
}

# ============================================================================
# TOOL ORCHESTRATION
# ============================================================================

install_sovereignty_tools() {
    local -n tool_list=$1
    local strict_mode=${2:-true}
    local failed_tools=()
    local success_tools=()

    info "Installing sovereign tools with dependency baseline..."

    # Ensure system dependencies before all tool installations
    if ! ensure_system_deps; then
        if [[ "${strict_mode}" == "true" ]]; then
            error "System dependency baseline failed in strict mode"
            return 1
        else
            warn "System dependency baseline incomplete (non-critical in relaxed mode)"
        fi
    fi

    # Install each tool
    for tool in "${tool_list[@]}"; do
        case "${tool}" in
            masscan)
                install_masscan || failed_tools+=("${tool}")
                ;;
            metasploit)
                install_metasploit || failed_tools+=("${tool}")
                ;;
            eyewitness)
                install_eyewitness || failed_tools+=("${tool}")
                ;;
            arjun)
                install_arjun || failed_tools+=("${tool}")
                ;;
            spiderfoot)
                install_spiderfoot || failed_tools+=("${tool}")
                ;;
            reconftw)
                install_reconftw || failed_tools+=("${tool}")
                ;;
            torbot)
                install_torbot || failed_tools+=("${tool}")
                ;;
            trufflehog)
                install_trufflehog || failed_tools+=("${tool}")
                ;;
            searchsploit)
                install_searchsploit || failed_tools+=("${tool}")
                ;;
            caido)
                install_caido || failed_tools+=("${tool}")
                ;;
            faraday)
                install_faraday || failed_tools+=("${tool}")
                ;;
            *)
                warn "Unknown tool: ${tool}"
                ;;
        esac

        if [[ $? -eq 0 ]]; then
            success_tools+=("${tool}")
        fi
    done

    # Report results
    if [[ ${#success_tools[@]} -gt 0 ]]; then
        info "Successfully installed: ${success_tools[*]}"
    fi

    if [[ ${#failed_tools[@]} -gt 0 ]]; then
        if [[ "${strict_mode}" == "true" ]]; then
            error "Installation failed for: ${failed_tools[*]}"
            return 1
        else
            warn "Installation failed for (non-critical): ${failed_tools[*]}"
            return 0
        fi
    fi

    return 0
}
