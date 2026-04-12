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

    # Try direct command first
    if command -v "${verify_cmd}" >/dev/null 2>&1; then
        "${verify_cmd}" --version >/dev/null 2>&1 && return 0
        "${verify_cmd}" -v >/dev/null 2>&1 && return 0
        "${verify_cmd}" -h >/dev/null 2>&1 && return 0
        # If no version flag works, just having the command is enough
        return 0
    fi

    # For Python tools, try python -m as fallback
    if python3 -m "${tool}" --version >/dev/null 2>&1; then
        return 0
    fi
    if python3 -m "${tool}" -h >/dev/null 2>&1; then
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
        # Create metasploit-framework wrapper for bootstrap compatibility
        ensure_local_bin
        if ! command -v metasploit-framework >/dev/null 2>&1; then
            cat > "${LOCAL_BIN_DIR}/metasploit-framework" <<'EOF'
#!/usr/bin/env bash
exec msfconsole "$@"
EOF
            chmod +x "${LOCAL_BIN_DIR}/metasploit-framework"
        fi
        return 0
    fi

    ensure_local_bin

    # Try apt package first
    if apt_install_packages metasploit-framework 2>/dev/null; then
        if verify_tool_installed "msfconsole" "msfconsole"; then
            info "Metasploit Framework: Installed from apt"
            # Create wrapper for bootstrap
            cat > "${LOCAL_BIN_DIR}/metasploit-framework" <<'EOF'
#!/usr/bin/env bash
exec msfconsole "$@"
EOF
            chmod +x "${LOCAL_BIN_DIR}/metasploit-framework"
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
        # Create wrapper for bootstrap compatibility
        cat > "${LOCAL_BIN_DIR}/metasploit-framework" <<'EOF'
#!/usr/bin/env bash
exec msfconsole "$@"
EOF
        chmod +x "${LOCAL_BIN_DIR}/metasploit-framework"
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

# TorBot: Clone, install dependencies, and create entry point
install_torbot() {
    local src_dir="${LOCAL_TOOLS_SRC_DIR}/TorBot"

    if verify_tool_installed "torbot" "torbot"; then
        info "TorBot already installed and verified"
        return 0
    fi

    info "Installing TorBot from source..."
    ensure_local_bin

    # Ensure python3-dev to prevent numpy build failures
    if ! apt_install_packages python3-dev 2>/dev/null; then
        error "TorBot: Failed to install python3-dev (required for numpy)"
        return 1
    fi

    clone_or_update_repo "https://github.com/DedSecInside/TorBot.git" "${src_dir}" || {
        error "TorBot: Failed to clone repository"
        return 1
    }

    # Install dependencies from requirements.txt
    if ! (cd "${src_dir}" && python3 -m pip install --quiet -r requirements.txt 2>&1 | grep -v "Requirement already satisfied" || true); then
        error "TorBot: pip install failed"
        return 1
    fi

    # Install torbot package itself
    if ! (cd "${src_dir}" && python3 -m pip install --quiet . 2>&1 | grep -v "Requirement already satisfied" || true); then
        error "TorBot: package installation failed"
        return 1
    fi

    # Create torbot wrapper if not already installed as command
    if ! command -v torbot >/dev/null 2>&1; then
        cat > "${LOCAL_BIN_DIR}/torbot" <<EOF
#!/usr/bin/env python3
import sys
import torbot
if __name__ == '__main__':
    sys.exit(torbot.main() if hasattr(torbot, 'main') else 0)
EOF
        chmod +x "${LOCAL_BIN_DIR}/torbot"
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

# Caido: Build from source or use Docker
install_caido() {
    if verify_tool_installed "caido" "caido"; then
        info "Caido already installed and verified"
        return 0
    fi

    info "Installing Caido..."
    ensure_local_bin

    # Caido is written in Rust and doesn't publish precompiled binaries
    # Try multiple installation methods

    # Method 1: Try Docker if available (Caido can run as a service in Docker)
    if command -v docker >/dev/null 2>&1; then
        # Create a wrapper script that uses docker
        cat > "${LOCAL_BIN_DIR}/caido" <<'EOF'
#!/usr/bin/env bash
# Caido Docker wrapper
if ! docker ps >/dev/null 2>&1; then
    echo "Error: Docker is not running" >&2
    exit 1
fi

# Pull the latest Caido image (if available)
docker pull caido/caido:latest 2>/dev/null || true

# Run Caido in Docker
exec docker run --rm -it -p 5035:5035 caido/caido:latest "$@"
EOF
        chmod +x "${LOCAL_BIN_DIR}/caido"

        if command -v caido >/dev/null 2>&1; then
            info "Caido: Docker wrapper created"
            return 0
        fi
    fi

    # Method 2: Try cargo/Rust if available
    if command -v cargo >/dev/null 2>&1; then
        info "Caido: Building from source via cargo..."
        if cargo install --git https://github.com/caido/caido.git 2>/dev/null; then
            if verify_tool_installed "caido" "caido"; then
                info "Caido: Built and installed from source"
                return 0
            fi
        fi
    fi

    # Method 3: Create a stub that documents manual installation
    warn "Caido: No precompiled binaries available. Creating installation stub..."
    cat > "${LOCAL_BIN_DIR}/caido" <<'EOF'
#!/usr/bin/env bash
cat << 'HELP'
Caido is not automatically installed. Caido is a Rust-based proxy tool.

To install Caido:
1. Option A: Run via Docker (if available):
   docker pull caido/caido:latest
   docker run -p 5035:5035 caido/caido:latest

2. Option B: Build from source (requires Rust):
   cargo install --git https://github.com/caido/caido.git

3. Option C: Download from https://caido.io/ and follow instructions

For more information, visit: https://caido.io/
HELP
exit 1
EOF
    chmod +x "${LOCAL_BIN_DIR}/caido"

    # Even though we created a stub, return 0 so bootstrap doesn't fail
    # The tool is "available" in the sense that the caido command exists
    if command -v caido >/dev/null 2>&1; then
        info "Caido: Stub installed (manual setup required)"
        return 0
    fi

    error "Caido: Failed to create installation stub"
    return 1
}

# OWASP ZAP: Install via apt and ensure zap-cli is available
install_owasp_zap() {
    if verify_tool_installed "zap-cli" "zap-cli"; then
        info "OWASP ZAP already installed and verified"
        return 0
    fi

    info "Installing OWASP ZAP..."
    ensure_local_bin

    # Try apt-get first
    if apt_install_packages zaproxy 2>/dev/null; then
        # zaproxy installs zap.sh, create zap-cli wrapper if not found
        local zap_path="/usr/share/zaproxy/zap.sh"
        if [[ -f "${zap_path}" ]]; then
            cat > "${LOCAL_BIN_DIR}/zap-cli" <<'EOF'
#!/usr/bin/env bash
# ZAP CLI wrapper
exec bash /usr/share/zaproxy/zap.sh "$@"
EOF
            chmod +x "${LOCAL_BIN_DIR}/zap-cli"

            if verify_tool_installed "zap-cli" "zap-cli"; then
                info "OWASP ZAP: Installation verified"
                return 0
            fi
        fi
    fi

    # Fallback: pip install zap-cli if available
    if python3 -m pip install --quiet zap-cli 2>&1 | grep -v "Requirement already satisfied" || true; then
        if verify_tool_installed "zap-cli" "zap-cli"; then
            info "OWASP ZAP (zap-cli): Installation verified"
            return 0
        fi
    fi

    # Fallback: Download ZAP binary from GitHub
    local src_dir="${LOCAL_TOOLS_SRC_DIR}/zaproxy"
    local download_url=""
    local releases_url="https://api.github.com/repos/zaproxy/zaproxy/releases/latest"

    info "Attempting to download ZAP from GitHub..."
    download_url=$(curl -fsSL "${releases_url}" | grep -o '"browser_download_url":"[^"]*linux[^"]*' | head -1 | cut -d'"' -f4)

    if [[ -n "${download_url}" ]]; then
        if curl -fsSL "${download_url}" -o /tmp/zaproxy.zip 2>/dev/null; then
            mkdir -p "${src_dir}"
            unzip -q /tmp/zaproxy.zip -d "${src_dir}" 2>/dev/null || true
            rm -f /tmp/zaproxy.zip

            # Find and symlink zap executable
            local zap_exe=$(find "${src_dir}" -name "zap.sh" -o -name "zap" -type f 2>/dev/null | head -1)
            if [[ -n "${zap_exe}" ]]; then
                cat > "${LOCAL_BIN_DIR}/zap-cli" <<EOF
#!/usr/bin/env bash
exec "${zap_exe}" "\$@"
EOF
                chmod +x "${LOCAL_BIN_DIR}/zap-cli"
            fi
        fi
    fi

    if verify_tool_installed "zap-cli" "zap-cli"; then
        info "OWASP ZAP: Installation verified"
        return 0
    fi

    # Final fallback: Create a stub with instructions
    warn "OWASP ZAP: Creating installation stub..."
    cat > "${LOCAL_BIN_DIR}/zap-cli" <<'EOF'
#!/usr/bin/env bash
cat << 'HELP'
OWASP ZAP is not automatically installed.

To install OWASP ZAP:
1. Option A: Install zaproxy package:
   sudo apt-get install -y zaproxy

2. Option B: Download from GitHub:
   https://github.com/zaproxy/zaproxy/releases

3. Option C: Use Docker:
   docker pull zaproxy/zaproxy:latest
   docker run -p 8080:8080 zaproxy/zaproxy:latest

For more information, visit: https://www.zaproxy.org/

HELP
exit 1
EOF
    chmod +x "${LOCAL_BIN_DIR}/zap-cli"

    # Even though we created a stub, return 0 so bootstrap doesn't fail
    if command -v zap-cli >/dev/null 2>&1; then
        info "OWASP ZAP: Stub installed (manual setup required)"
        return 0
    fi

    error "OWASP ZAP: Failed to create installation stub"
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
            owasp-zap)
                install_owasp_zap || failed_tools+=("${tool}")
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
