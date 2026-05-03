#!/bin/bash
###############################################################################
# KAISONONE BOOTSTRAP SCRIPT
# Auto-installs all 35 essential tools for the tiered bug bounty platform
# Usage: ./bootstrap.sh [--check-only|--force-reinstall|--tier N]
###############################################################################

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOOL_REGISTRY="${SCRIPT_DIR}/tools/registry/tool_registry.yaml"
INSTALL_LOG="${SCRIPT_DIR}/output/logs/bootstrap.log"
MISSING_TOOLS_FILE="${SCRIPT_DIR}/output/logs/missing_tools.json"

# Tool categories with installation methods
declare -A TOOL_INSTALLERS=(
    # Tier 1 - Core OSINT
    ["amass"]="go_install github.com/owasp-amass/amass/v4/...@latest"
    ["subfinder"]="go_install github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"
    ["spiderfoot"]="pip_install spiderfoot"
    ["theharvester"]="git_install https://github.com/laramies/theHarvester.git theHarvester"

    # Tier 1 - Network
    ["masscan"]="apt_install masscan"
    ["nmap"]="apt_install nmap"
    ["naabu"]="go_install github.com/projectdiscovery/naabu/v2/cmd/naabu@latest"
    ["httpx"]="go_install github.com/projectdiscovery/httpx/cmd/httpx@latest"

    # Tier 1 - Discovery  
    ["gau"]="go_install github.com/lc/gau/v2/cmd/gau@latest"
    ["katana"]="go_install github.com/projectdiscovery/katana/cmd/katana@latest"
    ["arjun"]="pip_install arjun"
    ["ffuf"]="go_install github.com/ffuf/ffuf/v2@latest"

    # Tier 1 - Vulnerability
    ["nuclei"]="go_install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"
    ["dalfox"]="go_install github.com/hahwul/dalfox/v2@latest"
    ["sqlmap"]="apt_install sqlmap"
    ["ghauri"]="pip_install ghauri"
    ["ssrfmap"]="git_install https://github.com/swisskyrepo/SSRFmap.git SSRFmap"
    ["xsstrike"]="git_install https://github.com/s0md3v/XSStrike.git XSStrike"

    # Tier 2 - API
    ["kiterunner"]="go_install github.com/assetnote/kiterunner@latest"
    ["graphqlmap"]="git_install https://github.com/swisskyrepo/GraphQLmap.git GraphQLmap"
    ["restler"]="special_install_restler"

    # Tier 2 - Cloud
    ["prowler"]="pip_install prowler"
    ["scoutsuite"]="pip_install ScoutSuite"
    ["trivy"]="apt_install trivy"

    # Tier 2 - Auth
    ["jwt_tool"]="git_install https://github.com/ticarpi/jwt_tool.git jwt_tool"
    ["authmatrix"]="special_install_authmatrix"
    ["hydra"]="apt_install hydra"

    # Tier 2 - Secrets
    ["trufflehog"]="go_install github.com/trufflesecurity/trufflehog@latest"
    ["gitleaks"]="go_install github.com/gitleaks/gitleaks/v8@latest"

    # Tier 2 - Business Logic
    ["racetheweb"]="git_install https://github.com/indefinitedevil/racetheweb.git racetheweb"
    ["fuxploider"]="git_install https://github.com/almandin/fuxploider.git fuxploider"

    # Tier 3 - Client Side
    ["domdig"]="git_install https://github.com/fcavallarin/domdig.git domdig"
    ["csp_evaluator"]="pip_install csp-evaluator"

    # Tier 3 - Network Internal
    ["bloodhound"]="apt_install bloodhound"
    ["crackmapexec"]="pip_install crackmapexec"

    # Tier 3 - Mobile
    ["mobsf"]="special_install_mobsf"
)

# Installation counters
INSTALLED=0
FAILED=0
SKIPPED=0

###############################################################################
# Helper Functions
###############################################################################

log() {
    echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} $1" | tee -a "$INSTALL_LOG"
}

success() {
    echo -e "${GREEN}[✓]${NC} $1" | tee -a "$INSTALL_LOG"
}

warn() {
    echo -e "${YELLOW}[!]${NC} $1" | tee -a "$INSTALL_LOG"
}

error() {
    echo -e "${RED}[✗]${NC} $1" | tee -a "$INSTALL_LOG"
}

detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if command -v apt-get &> /dev/null; then
            echo "debian"
        elif command -v yum &> /dev/null; then
            echo "rhel"
        elif command -v pacman &> /dev/null; then
            echo "arch"
        else
            echo "linux"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        echo "macos"
    else
        echo "unknown"
    fi
}

check_prerequisites() {
    log "Checking prerequisites..."

    # Check package managers
    OS=$(detect_os)
    success "Detected OS: $OS"

    # Check for Go
    if ! command -v go &> /dev/null; then
        warn "Go not found. Installing..."
        install_go
    fi

    # Check for Python
    if ! command -v python3 &> /dev/null; then
        error "Python3 is required but not installed"
        exit 1
    fi

    # Check for pip
    if ! command -v pip3 &> /dev/null; then
        warn "pip3 not found. Installing..."
        apt_get_update
        apt_install python3-pip
    fi

    success "Prerequisites check complete"
}

install_go() {
    local go_version="1.21.5"
    local os=$(detect_os)

    log "Installing Go ${go_version}..."

    if [[ "$os" == "debian" ]] || [[ "$os" == "rhel" ]]; then
        wget -q "https://go.dev/dl/go${go_version}.linux-amd64.tar.gz"
        sudo rm -rf /usr/local/go
        sudo tar -C /usr/local -xzf "go${go_version}.linux-amd64.tar.gz"
        rm "go${go_version}.linux-amd64.tar.gz"

        # Add to PATH
        if ! grep -q "/usr/local/go/bin" ~/.bashrc; then
            echo 'export PATH=$PATH:/usr/local/go/bin:$HOME/go/bin' >> ~/.bashrc
        fi
        export PATH=$PATH:/usr/local/go/bin:$HOME/go/bin
    elif [[ "$os" == "macos" ]]; then
        if command -v brew &> /dev/null; then
            brew install go
        else
            error "Homebrew required for macOS Go installation"
            exit 1
        fi
    fi

    success "Go installed: $(go version)"
}

apt_get_update() {
    if [[ $(detect_os) == "debian" ]]; then
        sudo apt-get update -qq
    fi
}

###############################################################################
# Installation Methods
###############################################################################

apt_install() {
    local package=$1
    if command -v apt-get &> /dev/null; then
        sudo apt-get install -y -qq "$package" 2>&1 | tee -a "$INSTALL_LOG"
    elif command -v yum &> /dev/null; then
        sudo yum install -y "$package" 2>&1 | tee -a "$INSTALL_LOG"
    elif command -v brew &> /dev/null; then
        brew install "$package" 2>&1 | tee -a "$INSTALL_LOG"
    else
        return 1
    fi
}

go_install() {
    local package=$1
    log "Installing via go: $package"
    go install "$package" 2>&1 | tee -a "$INSTALL_LOG"
}

pip_install() {
    local package=$1
    log "Installing via pip: $package"
    pip3 install "$package" 2>&1 | tee -a "$INSTALL_LOG"
}

git_install() {
    local repo=$1
    local name=$2
    local install_dir="/opt/tools/$name"

    log "Installing from git: $name"

    if [[ -d "$install_dir" ]]; then
        warn "$name already exists at $install_dir"
        return 0
    fi

    sudo mkdir -p /opt/tools
    sudo git clone --depth 1 "$repo" "$install_dir" 2>&1 | tee -a "$INSTALL_LOG"

    # Create symlink in /usr/local/bin if there's a main script
    if [[ -f "$install_dir/$name.py" ]]; then
        sudo ln -sf "$install_dir/$name.py" "/usr/local/bin/$name"
    elif [[ -f "$install_dir/$name" ]]; then
        sudo chmod +x "$install_dir/$name"
        sudo ln -sf "$install_dir/$name" "/usr/local/bin/$name"
    fi
}

special_install_restler() {
    log "Installing RESTler via dotnet..."
    if ! command -v dotnet &> /dev/null; then
        warn "Installing dotnet first..."
        wget -q https://packages.microsoft.com/config/ubuntu/22.04/packages-microsoft-prod.deb
        sudo dpkg -i packages-microsoft-prod.deb
        rm packages-microsoft-prod.deb
        apt_get_update
        apt_install dotnet-sdk-6.0
    fi

    # Build RESTler
    local restler_dir="/opt/tools/restler-fuzzer"
    sudo git clone --depth 1 https://github.com/microsoft/restler-fuzzer.git "$restler_dir"
    cd "$restler_dir"
    sudo dotnet build src/Restler/Restler.fsproj -c Release
    sudo ln -sf "$restler_dir/restler/Restler.exe" /usr/local/bin/restler
}

special_install_authmatrix() {
    log "Installing AuthMatrix (Burp extension alternative)..."
    pip_install auth-matrix 2>/dev/null || pip_install pyjwt requests
    # Note: Full AuthMatrix requires Burp, installing Python alternatives
    git_install https://github.com/portswigger/auth-matrix.git auth-matrix
}

special_install_mobsf() {
    log "Installing MobSF..."
    local mobsf_dir="/opt/tools/Mobile-Security-Framework-MobSF"

    if [[ -d "$mobsf_dir" ]]; then
        warn "MobSF already installed"
        return 0
    fi

    sudo apt_install python3-venv python3-dev python3-pip build-essential libffi-dev libssl-dev libxml2-dev libxslt1-dev libjpeg8-dev zlib1g-dev wkhtmltopdf
    sudo git clone --depth 1 https://github.com/MobSF/Mobile-Security-Framework-MobSF.git "$mobsf_dir"
    cd "$mobsf_dir"
    sudo ./setup.sh || sudo pip3 install -r requirements.txt
    sudo ln -sf "$mobsf_dir/run.sh" /usr/local/bin/mobsf
}

###############################################################################
# Main Functions
###############################################################################

check_tool_installed() {
    local tool=$1
    local binary_path=$2

    if [[ -f "$binary_path" ]]; then
        return 0  # Installed
    fi

    if command -v "$tool" &> /dev/null; then
        return 0  # In PATH
    fi

    return 1  # Not installed
}

install_tool() {
    local tool=$1
    local installer=${TOOL_INSTALLERS[$tool]:-}

    if [[ -z "$installer" ]]; then
        warn "No installer defined for $tool"
        ((FAILED++))
        return 1
    fi

    log "Installing $tool..."

    # Parse installer method
    local method=$(echo "$installer" | cut -d' ' -f1)
    local args=$(echo "$installer" | cut -d' ' -f2-)

    case $method in
        apt_install|go_install|pip_install|git_install)
            if $method $args; then
                success "$tool installed"
                ((INSTALLED++))
                return 0
            else
                error "$tool installation failed"
                ((FAILED++))
                return 1
            fi
            ;;
        special_install_*)
            if $method; then
                success "$tool installed"
                ((INSTALLED++))
                return 0
            else
                error "$tool installation failed"
                ((FAILED++))
                return 1
            fi
            ;;
        *)
            warn "Unknown install method: $method"
            ((FAILED++))
            return 1
            ;;
    esac
}

scan_and_install() {
    local check_only=${1:-false}
    local specific_tier=${2:-}

    log "Starting tool scan..."
    log "Registry: $TOOL_REGISTRY"

    # Parse registry and check each tool
    local missing_tools=()

    while IFS= read -r line; do
        if [[ "$line" =~ ^[[:space:]]*-[[:space:]]*name:[[:space:]]*(.*) ]]; then
            tool_name="${BASH_REMATCH[1]}"
            tool_name=$(echo "$tool_name" | xargs)  # Trim whitespace

            # Get tier info
            read -r next_line
            if [[ "$next_line" =~ tier:[[:space:]]*([0-9]) ]]; then
                tier="${BASH_REMATCH[1]}"
            fi

            # Skip if specific tier requested and doesn't match
            if [[ -n "$specific_tier" && "$tier" != "$specific_tier" ]]; then
                continue
            fi

            # Check if installed
            if ! check_tool_installed "$tool_name" "/usr/local/bin/$tool_name"; then
                missing_tools+=("$tool_name")

                if [[ "$check_only" == "false" ]]; then
                    install_tool "$tool_name"
                else
                    warn "$tool_name (Tier $tier) - MISSING"
                fi
            else
                ((SKIPPED++))
                log "$tool_name (Tier $tier) - OK"
            fi
        fi
    done < "$TOOL_REGISTRY"

    # Save missing tools report
    if [[ ${#missing_tools[@]} -gt 0 ]]; then
        echo "{\"missing_tools\": [$(printf '\"%s\",' "${missing_tools[@]}" | sed 's/,$//')], \"timestamp\": "$(date -Iseconds)\"}" > "$MISSING_TOOLS_FILE"
    fi

    return ${#missing_tools[@]}
}

###############################################################################
# Main Entry Point
###############################################################################

main() {
    echo "═══════════════════════════════════════════════════════════════"
    echo "  KAISONONE BOOTSTRAP - 35-Tool Auto-Installer"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""

    # Create log directory
    mkdir -p "$(dirname "$INSTALL_LOG")"

    # Check for args
    local check_only=false
    local specific_tier=""
    local force_reinstall=false

    while [[ $# -gt 0 ]]; do
        case $1 in
            --check-only)
                check_only=true
                shift
                ;;
            --tier)
                specific_tier="$2"
                shift 2
                ;;  
            --force-reinstall)
                force_reinstall=true
                shift
                ;;
            --help|-h)
                echo "Usage: ./bootstrap.sh [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --check-only       Check which tools are missing (don't install)"
                echo "  --tier N           Only check/install tools for specific tier (1-3)"
                echo "  --force-reinstall  Force reinstallation of all tools"
                echo "  --help, -h         Show this help message"
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    # Check prerequisites
    check_prerequisites

    # Set PATH for Go
    export PATH=$PATH:/usr/local/go/bin:$HOME/go/bin

    # Run scan/install
    scan_and_install "$check_only" "$specific_tier"

    # Summary
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "  INSTALLATION SUMMARY"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    echo "  Installed:  $INSTALLED"
    echo "  Skipped:    $SKIPPED (already present)"
    echo "  Failed:     $FAILED"
    echo ""

    if [[ $FAILED -gt 0 ]]; then
        error "Some tools failed to install. Check $INSTALL_LOG"
        exit 1
    elif [[ $INSTALLED -gt 0 ]]; then
        success "Bootstrap complete! All tools ready."
        echo ""
        echo "Run './k1 start' to launch KaisonOne"
    else
        success "All tools already installed. Platform ready!"
    fi

    echo ""
    echo "Log saved to: $INSTALL_LOG"
}

# Run main
main "$@"
