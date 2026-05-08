#!/usr/bin/env bash
# KAI Tool Installer Script
# Downloads and installs all tools from tools/registry/tool_registry.yaml to local hardware
# Run this script manually from the repo root directory

set -euo pipefail

# Configuration
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOLS_YAML="${REPO_ROOT}/tools/registry/tool_registry.yaml"
LOG_FILE="${REPO_ROOT}/output/logs/tool_install_$(date +%Y%m%d_%H%M%S).log"
LOCAL_BIN="${HOME}/.local/bin"
TOOLS_SRC_DIR="${REPO_ROOT}/runtime/tools-src"
DOWNLOADS_DIR="${HOME}/Downloads"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging
log() {
    echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} $1" | tee -a "$LOG_FILE"
}

success() {
    echo -e "${GREEN}[✓]${NC} $1" | tee -a "$LOG_FILE"
}

warn() {
    echo -e "${YELLOW}[!]${NC} $1" | tee -a "$LOG_FILE"
}

error() {
    echo -e "${RED}[✗]${NC} $1" | tee -a "$LOG_FILE"
}

# Prerequisites
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Python3
    if ! command -v python3 &> /dev/null; then
        error "python3 is required. Please install Python 3.11+"
        exit 1
    fi
    
    # pip
    if ! python3 -m pip --version &> /dev/null; then
        error "pip is required. Please install pip"
        exit 1
    fi
    
    # git
    if ! command -v git &> /dev/null; then
        error "git is required. Please install git"
        exit 1
    fi
    
    # curl
    if ! command -v curl &> /dev/null; then
        error "curl is required. Please install curl"
        exit 1
    fi
    
    success "Prerequisites OK"
}

# Setup directories
setup_directories() {
    mkdir -p "$LOCAL_BIN" "$TOOLS_SRC_DIR" "$(dirname "$LOG_FILE")"
    export PATH="$LOCAL_BIN:$PATH"
}

# Install Go if needed
ensure_go() {
    if command -v go &> /dev/null; then
        success "Go is already installed"
        return 0
    fi
    
    log "Installing Go..."
    
    # Try apt first
    if command -v apt-get &> /dev/null; then
        if command -v sudo &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y golang-go
        else
            apt-get update && apt-get install -y golang-go
        fi
        if command -v go &> /dev/null; then
            success "Go installed via apt"
            return 0
        fi
    fi
    
    # Fallback to manual install
    GO_VERSION="1.21.5"
    GO_ARCH="linux-amd64"
    GO_TAR="go${GO_VERSION}.${GO_ARCH}.tar.gz"
    GO_URL="https://golang.org/dl/${GO_TAR}"
    
    curl -L "$GO_URL" -o "/tmp/$GO_TAR"
    sudo rm -rf /usr/local/go
    sudo tar -C /usr/local -xzf "/tmp/$GO_TAR"
    rm "/tmp/$GO_TAR"
    
    export PATH="/usr/local/go/bin:$PATH"
    echo 'export PATH="/usr/local/go/bin:$PATH"' >> ~/.bashrc
    
    if command -v go &> /dev/null; then
        success "Go installed manually"
    else
        error "Failed to install Go"
        return 1
    fi
}

# Install Rust if needed
ensure_rust() {
    if command -v cargo &> /dev/null; then
        success "Rust is already installed"
        return 0
    fi
    
    log "Installing Rust..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source ~/.cargo/env
    export PATH="$HOME/.cargo/bin:$PATH"
    
    if command -v cargo &> /dev/null; then
        success "Rust installed"
    else
        error "Failed to install Rust"
        return 1
    fi
}

# Install tool via Go
install_go_tool() {
    local name="$1"
    local module="$2"
    
    log "Installing $name via Go..."
    
    if ! ensure_go; then
        error "Go required for $name"
        return 1
    fi
    
    export GOBIN="$LOCAL_BIN"
    mkdir -p "$GOBIN"
    
    if go install "$module" 2>>"$LOG_FILE"; then
        if [ -x "$LOCAL_BIN/$name" ] || [ -x "$GOBIN/$name" ]; then
            success "$name installed"
            return 0
        else
            warn "$name: installed but binary not found in expected location"
            return 0
        fi
    else
        error "$name: Go install failed"
        return 1
    fi
}

# Install tool via pip
install_python_tool() {
    local name="$1"
    local package="$2"
    
    log "Installing $name via pip..."
    
    if python3 -m pip install "$package" --user 2>>"$LOG_FILE"; then
        success "$name installed"
        return 0
    else
        error "$name: pip install failed"
        return 1
    fi
}

# Install tool via apt
install_apt_tool() {
    local name="$1"
    local package="$2"
    
    log "Installing $name via apt..."
    
    if ! command -v apt-get &> /dev/null; then
        error "$name: apt not available"
        return 1
    fi
    
    local sudo_cmd=""
    if command -v sudo &> /dev/null; then
        sudo_cmd="sudo"
    fi
    
    if $sudo_cmd apt-get update && $sudo_cmd apt-get install -y "$package" 2>>"$LOG_FILE"; then
        success "$name installed"
        return 0
    else
        error "$name: apt install failed"
        return 1
    fi
}

# Install tool from source
install_from_source() {
    local name="$1"
    local repo_url="$2"
    local build_cmd="$3"
    local binary_path="$4"
    
    log "Installing $name from source..."
    
    local src_dir="$TOOLS_SRC_DIR/$name"
    
    if [ ! -d "$src_dir" ]; then
        git clone --depth 1 "$repo_url" "$src_dir" 2>>"$LOG_FILE"
    else
        (cd "$src_dir" && git pull) 2>>"$LOG_FILE" || true
    fi
    
    (cd "$src_dir" && eval "$build_cmd") 2>>"$LOG_FILE"
    
    if [ -x "$src_dir/$binary_path" ]; then
        cp "$src_dir/$binary_path" "$LOCAL_BIN/$name"
        chmod +x "$LOCAL_BIN/$name"
        success "$name installed"
        return 0
    else
        error "$name: build failed or binary not found"
        return 1
    fi
}

# Install specific tool
install_tool() {
    local name="$1"
    local category="$2"
    
    case "$name" in
        # Go tools
        amass) install_go_tool "$name" "github.com/OWASP/Amass/v3/cmd/amass@latest" ;;
        subfinder) install_go_tool "$name" "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest" ;;
        assetfinder) install_go_tool "$name" "github.com/tomnomnom/assetfinder@latest" ;;
        dnsx) install_go_tool "$name" "github.com/projectdiscovery/dnsx/cmd/dnsx@latest" ;;
        gau) install_go_tool "$name" "github.com/lc/gau/v2/cmd/gau@latest" ;;
        waybackurls) install_go_tool "$name" "github.com/tomnomnom/waybackurls@latest" ;;
        httpx) install_go_tool "$name" "github.com/projectdiscovery/httpx/cmd/httpx@latest" ;;
        naabu) install_go_tool "$name" "github.com/projectdiscovery/naabu/v2/cmd/naabu@latest" ;;
        nuclei) install_go_tool "$name" "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest" ;;
        katana) install_go_tool "$name" "github.com/projectdiscovery/katana/cmd/katana@latest" ;;
        dalfox) install_go_tool "$name" "github.com/hahwul/dalfox/v2@latest" ;;
        ffuf) install_go_tool "$name" "github.com/ffuf/ffuf/v2@latest" ;;
        hakrawler) install_go_tool "$name" "github.com/hakluke/hakrawler@latest" ;;
        gitleaks) install_go_tool "$name" "github.com/gitleaks/gitleaks/v8@latest" ;;
        crlfuzz) install_go_tool "$name" "github.com/dwisiswant0/crlfuzz/cmd/crlfuzz@latest" ;;
        findomain) install_go_tool "$name" "github.com/Findomain/Findomain@latest" ;;
        
        # APT tools
        nmap) install_apt_tool "$name" "nmap" ;;
        nikto) install_apt_tool "$name" "nikto" ;;
        whatweb) install_apt_tool "$name" "whatweb" ;;
        masscan) install_apt_tool "$name" "masscan" ;;
        feroxbuster) install_apt_tool "$name" "feroxbuster" ;;
        
        # Python tools
        arjun) install_python_tool "$name" "arjun" ;;
        sqlmap) install_python_tool "$name" "sqlmap" ;;
        ghauri) install_python_tool "$name" "ghauri" ;;
        
        # Source builds
        kiterunner) install_from_source "$name" "https://github.com/assetnote/kiterunner" "make build" "dist/kr" ;;
        metasploit-framework) install_from_source "$name" "https://github.com/rapid7/metasploit-framework" "bundle install" "msfconsole" ;;
        
        # Special cases
        theharvester) install_python_tool "$name" "theharvester" ;;
        spiderfoot) install_python_tool "$name" "spiderfoot" ;;
        
        *) warn "$name: No installation method defined, skipping" ;;
    esac
}

# Main installation loop
main() {
    echo "=============================================="
    echo "  KAI Tool Installer"
    echo "=============================================="
    echo ""
    
    check_prerequisites
    setup_directories
    
    if [ ! -f "$TOOLS_YAML" ]; then
        error "Tool registry not found: $TOOLS_YAML"
        exit 1
    fi
    
    log "Reading tool registry..."
    
    # Parse YAML and install tools
    python3 -c "
import yaml
import sys

with open('$TOOLS_YAML', 'r') as f:
    data = yaml.safe_load(f)

tools = data.get('tools', [])
installed = 0
failed = 0

for tool in tools:
    if not isinstance(tool, dict):
        continue
    
    name = tool.get('name', '').strip()
    mode = tool.get('execution_mode', 'native').strip().lower()
    
    if mode != 'native':
        continue
    
    print(f'Installing {name}...')
    sys.stdout.flush()
    
    # Call the install function
    if __import__('subprocess').call(['bash', '-c', f'source \"$0\" && install_tool \"{name}\" \"{tool.get(\"category\", \"\")}\"'], 
                                     stdout=sys.stdout, stderr=sys.stderr) == 0:
        installed += 1
    else:
        failed += 1

print(f'\\nInstallation complete: {installed} installed, {failed} failed')
" "$0"
    
    echo ""
    success "Installation complete. Check $LOG_FILE for details."
    echo "Add $LOCAL_BIN to your PATH if not already done:"
    echo "  export PATH=\"$LOCAL_BIN:\$PATH\""
    echo "  echo 'export PATH=\"$LOCAL_BIN:\$PATH\"' >> ~/.bashrc"
}

# Run main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
