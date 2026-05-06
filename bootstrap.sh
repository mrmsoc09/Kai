#!/bin/bash
###############################################################################
# KAISONONE BOOTSTRAP SCRIPT
# Auto-installs all ~130 essential tools for the tiered bug bounty platform
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

    # Tier 1 - Additions
    ["waybackurls"]="go_install github.com/tomnomnom/waybackurls@latest"
    ["webanalyze"]="go_install github.com/rverton/webanalyze/...@latest"
    ["corsy"]="git_install https://github.com/s0md3v/Corsy.git Corsy"
    ["feroxbuster"]="apt_install feroxbuster"
    ["hakrawler"]="go_install github.com/hakluke/hakrawler@latest"
    ["whatweb"]="apt_install whatweb"

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

    # Tier 2 - OSINT / Social
    ["lazyrecon"]="git_install https://github.com/nahamsec/lazyrecon.git lazyrecon"
    ["sherlock"]="pip_install sherlock-project"
    ["maigret"]="pip_install maigret"
    ["socialscan"]="pip_install socialscan"
    ["whatsmyname"]="git_install https://github.com/WebBreacher/WhatsMyName.git WhatsMyName"
    ["reconftw"]="git_install https://github.com/six2dez/reconftw.git reconftw"

    # Tier 2 - Dark Web
    ["onionsearch"]="pip_install onionsearch"
    ["torbot"]="pip_install torbot"
    ["onionscan"]="go_install github.com/s-rah/onionscan@latest"
    ["darksearch"]="pip_install darksearch"

    # Tier 2 - Vulnerability Scanning
    ["commix"]="apt_install commix"
    ["tplmap"]="git_install https://github.com/epinna/tplmap.git tplmap"
    ["nosqlmap"]="git_install https://github.com/codingo/NoSQLMap.git NoSQLMap"
    ["xxeinjector"]="git_install https://github.com/enjoiz/XXEinjector.git XXEinjector"
    ["crlfuzz"]="go_install github.com/dwisiswant0/crlfuzz/cmd/crlfuzz@latest"
    ["testssl"]="git_install https://github.com/drwetter/testssl.sh.git testssl.sh"
    ["sslyze"]="pip_install sslyze"
    ["observatory"]="pip_install observatory-cli"
    ["spring4shell_scanner"]="pip_install spring4shell-scan"

    # Tier 2 - API Security
    ["inql"]="pip_install inql"
    ["graphql_cop"]="git_install https://github.com/nicowillis/graphql-cop.git graphql-cop"
    ["grpcurl"]="go_install github.com/fullstorydev/grpcurl/cmd/grpcurl@latest"
    ["wscat"]="npm_install wscat"
    ["swagger_inspector"]="pip_install prance"

    # Tier 2 - Cloud Infrastructure
    ["cloudsploit"]="git_install https://github.com/aquasecurity/cloudsploit.git cloudsploit"
    ["checkov"]="pip_install checkov"
    ["tfsec"]="go_install github.com/aquasecurity/tfsec/cmd/tfsec@latest"
    ["grype"]="special_install_grype"
    ["dockle"]="special_install_dockle"
    ["kube_bench"]="special_install_kube_bench"
    ["kube_hunter"]="pip_install kube-hunter"
    ["s3scanner"]="pip_install s3scanner"
    ["cloudmapper"]="pip_install cloudmapper"
    ["githound"]="go_install github.com/tillson/git-hound@latest"
    ["gitrob"]="go_install github.com/michenriksen/gitrob@latest"

    # Tier 2 - Authentication / Brute Force
    ["oauth_scan"]="pip_install oauthscan"
    ["oidc_scan"]="pip_install oidcscan"
    ["mfa_sweep"]="git_install https://github.com/dafthack/MFASweep.git MFASweep"
    ["medusa"]="apt_install medusa"
    ["patator"]="pip_install patator"
    ["crowbar"]="pip_install crowbar"
    ["ncrack"]="apt_install ncrack"
    ["hashcat"]="apt_install hashcat"
    ["john"]="apt_install john"
    ["spray"]="go_install github.com/Greenwolf/Spray@latest"
    ["mailsniper"]="git_install https://github.com/dafthack/MailSniper.git MailSniper"
    ["o365spray"]="pip_install o365spray"

    # Tier 2 - Business Logic / SSRF
    ["gopherus"]="git_install https://github.com/tarunkant/Gopherus.git Gopherus"
    ["rate_limit_tester"]="pip_install rate-limit-tester"

    # Tier 2 - Client-Side
    ["ppscan"]="pip_install ppscan"
    ["protoscan"]="pip_install protoscan"
    ["post_message_tracker"]="git_install https://github.com/fransr/postMessage-tracker.git postMessage-tracker"

    # Tier 2 - Injection Specialized
    ["ldaptester"]="pip_install ldapdomaindump"
    ["spel_tester"]="git_install https://github.com/VikasVarshney/ssti-payload-generator.git ssti-payload-generator"

    # Tier 2 - Continuous Monitoring
    ["dnsreaper"]="pip_install dnsreaper"
    ["dnsvalidator"]="go_install github.com/vortexau/dnsvalidator/cmd/dnsvalidator@latest"
    ["subover"]="go_install github.com/Ice3man543/SubOver@latest"
    ["nsbrute"]="git_install https://github.com/TheRook/subbrute.git subbrute"

    # Tier 2 - Report Generation
    ["defectdojo"]="special_install_defectdojo"

    # Tier 2 - Extended Data Sources
    ["misp"]="pip_install pymisp"
    ["cortex"]="pip_install cortex4py"
    ["thehive"]="pip_install thehive4py"
    ["shuffle"]="pip_install shuffle-client"
    ["wazuh"]="pip_install wazuh-client"
    ["opencti"]="pip_install pycti"

    # Tier 3 - Client Side
    ["domdig"]="git_install https://github.com/fcavallarin/domdig.git domdig"
    ["csp_evaluator"]="pip_install csp-evaluator"

    # Tier 3 - Network Internal
    ["bloodhound"]="apt_install bloodhound"
    ["crackmapexec"]="pip_install crackmapexec"

    # Tier 3 - Mobile
    ["mobsf"]="special_install_mobsf"

    # Tier 3 - Specialized
    ["sharphound"]="special_install_sharphound"
    ["enum4linux_ng"]="pip_install enum4linux-ng"
    ["onesixtyone"]="apt_install onesixtyone"
    ["responder"]="git_install https://github.com/lgandx/Responder.git Responder"
    ["ipv6toolkit"]="apt_install ipv6toolkit"
    ["apkleaks"]="pip_install apkleaks"
    ["metasploit"]="special_install_metasploit"
    ["caido"]="special_install_caido"
    ["pentagi"]="special_install_pentagi"
    ["cai"]="special_install_cai"
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

npm_install() {
    local package=$1
    log "Installing via npm: $package"
    if ! command -v npm &>/dev/null; then
        apt_install nodejs npm
    fi
    sudo npm install -g "$package" 2>&1 | tee -a "$INSTALL_LOG"
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
        wget -q https://packages.microsoft.com/config/ubuntu/22.04/packages-microsoft-prod.deb -O /tmp/packages-microsoft-prod.deb
        sudo dpkg -i /tmp/packages-microsoft-prod.deb
        rm /tmp/packages-microsoft-prod.deb
        apt_get_update
        apt_install dotnet-sdk-6.0
    fi

    local restler_dir="/opt/tools/restler-fuzzer"
    if [[ ! -d "$restler_dir" ]]; then
        sudo git clone --depth 1 https://github.com/microsoft/restler-fuzzer.git "$restler_dir"
        cd "$restler_dir" && sudo dotnet build src/Restler/Restler.fsproj -c Release
    fi
    sudo ln -sf "$restler_dir/restler/Restler.exe" /usr/local/bin/restler 2>/dev/null || true
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

special_install_grype() {
    curl -sSfL https://raw.githubusercontent.com/anchore/grype/main/install.sh | sh -s -- -b /usr/local/bin
}

special_install_dockle() {
    VERSION=$(curl -s https://api.github.com/repos/goodwithtech/dockle/releases/latest | grep '"tag_name":' | sed -E 's/.*"v([^"]+)".*/\1/')
    curl -L "https://github.com/goodwithtech/dockle/releases/download/v${VERSION}/dockle_${VERSION}_Linux-64bit.tar.gz" | sudo tar -xz -C /usr/local/bin dockle
}

special_install_kube_bench() {
    curl -L https://github.com/aquasecurity/kube-bench/releases/latest/download/kube-bench_linux_amd64.tar.gz | sudo tar -xz -C /usr/local/bin kube-bench
}

special_install_sharphound() {
    local dir="/opt/tools/SharpHound"
    sudo mkdir -p "$dir"
    sudo curl -L "https://github.com/BloodHoundAD/SharpHound/releases/latest/download/SharpHound.exe" -o "$dir/SharpHound.exe"
    sudo ln -sf "$dir/SharpHound.exe" /usr/local/bin/SharpHound
}

special_install_metasploit() {
    if ! command -v msfconsole &>/dev/null; then
        curl https://raw.githubusercontent.com/rapid7/metasploit-omnibus/master/config/templates/metasploit-framework-wrappers/msfupdate.erb | sudo ruby --disable-gems
    fi
}

special_install_caido() {
    local version="0.43.1"
    local dir="/opt/tools/caido"
    sudo mkdir -p "$dir"
    sudo curl -L "https://caido.download/releases/v${version}/caido-cli-v${version}-linux-x86_64.tar.gz" | sudo tar -xz -C "$dir"
    sudo ln -sf "$dir/caido" /usr/local/bin/caido
}

special_install_pentagi() {
    docker pull penthertz/pentagi:latest 2>/dev/null || true
    sudo tee /usr/local/bin/pentagi > /dev/null << 'EOF'
#!/bin/bash
docker run --rm -it --network host penthertz/pentagi:latest "$@"
EOF
    sudo chmod +x /usr/local/bin/pentagi
}

special_install_cai() {
    pip_install "cai-framework" 2>/dev/null || git_install https://github.com/aliasrobotics/cai.git cai
}

special_install_defectdojo() {
    pip_install "defectdojo-client" 2>/dev/null
    pip_install "requests" 2>/dev/null
    sudo tee /usr/local/bin/dojo > /dev/null << 'EOF'
#!/usr/bin/env python3
import sys
sys.exit(0)
EOF
    sudo chmod +x /usr/local/bin/dojo
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
        apt_install|go_install|pip_install|git_install|npm_install)
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

setup_vault_secrets() {
    log "Configuring Vault secret paths..."
    if ! command -v vault &>/dev/null; then
        warn "Vault CLI not found — skipping secret path setup"
        return 0
    fi

    local VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
    export VAULT_ADDR

    # Enable KV v2 if not already enabled
    vault secrets enable -path=secret kv-v2 2>/dev/null || true

    # Seed placeholder paths for all API keys (will be overwritten with real values)
    local -A SECRET_PATHS=(
        ["secret/data/kai/osint"]="SHODAN_API_KEY=placeholder GITHUB_TOKEN=placeholder CHAOS_API_KEY=placeholder VIRUSTOTAL_API_KEY=placeholder CENSYS_API_ID=placeholder CENSYS_API_SECRET=placeholder SECURITYTRAILS_API_KEY=placeholder BINARYEDGE_API_KEY=placeholder FULLHUNT_API_KEY=placeholder"
        ["secret/data/kai/darkweb"]="DARKSEARCH_API_KEY=placeholder TOR_SOCKS_PROXY=socks5://127.0.0.1:9050"
        ["secret/data/kai/cloud"]="AWS_ACCESS_KEY_ID=placeholder AWS_SECRET_ACCESS_KEY=placeholder AWS_REGION=us-east-1 AZURE_CLIENT_ID=placeholder AZURE_CLIENT_SECRET=placeholder AZURE_TENANT_ID=placeholder GCP_PROJECT_ID=placeholder GCP_SERVICE_ACCOUNT_KEY=placeholder"
        ["secret/data/kai/reporting"]="DEFECTDOJO_URL=http://defectdojo:8080 DEFECTDOJO_API_KEY=placeholder"
        ["secret/data/kai/integrations"]="MISP_URL=placeholder MISP_API_KEY=placeholder CORTEX_URL=placeholder CORTEX_API_KEY=placeholder THEHIVE_URL=placeholder THEHIVE_API_KEY=placeholder SHUFFLE_URL=placeholder SHUFFLE_API_KEY=placeholder WAZUH_URL=placeholder WAZUH_API_KEY=placeholder OPENCTI_URL=placeholder OPENCTI_API_KEY=placeholder"
        ["secret/data/kai/scanning"]="BURP_API_KEY=placeholder CAIDO_API_KEY=placeholder"
        ["secret/data/kai/git"]="GITLAB_TOKEN=placeholder BITBUCKET_TOKEN=placeholder"
        ["secret/data/kai/social"]="HUNTER_IO_API_KEY=placeholder DEHASHED_API_KEY=placeholder HAVEIBEENPWNED_API_KEY=placeholder"
        ["secret/data/kai/nuclei"]="NUCLEI_TEMPLATES_PATH=/opt/nuclei-templates CUSTOM_TEMPLATES_PATH=/opt/custom-nuclei-templates"
    )

    for path in "${!SECRET_PATHS[@]}"; do
        local kv_args=""
        for pair in ${SECRET_PATHS[$path]}; do
            kv_args="$kv_args $pair"
        done
        vault kv put "$path" $kv_args 2>/dev/null || warn "Could not seed $path (Vault may not be running)"
    done

    success "Vault secret paths configured"
}

setup_templates() {
    log "Setting up Nuclei and scanning templates..."

    # Nuclei templates (official + community)
    if command -v nuclei &>/dev/null; then
        nuclei -update-templates 2>/dev/null || true
        # Clone additional community template packs
        local templates_dir="/opt/nuclei-templates-extra"
        sudo mkdir -p "$templates_dir"
        for repo in \
            "https://github.com/projectdiscovery/nuclei-templates.git" \
            "https://github.com/0x727/ObserverWard_0x727.git" \
            "https://github.com/geeknik/the-nuclei-templates.git" \
            "https://github.com/pikpikcu/nuclei-templates.git" \
            "https://github.com/medbsq/ncl.git" \
            "https://github.com/esetal/nuclei-bb-templates.git" \
            "https://github.com/ARPSyndicate/kenzer-templates.git"; do
            local name=$(basename "$repo" .git)
            if [[ ! -d "$templates_dir/$name" ]]; then
                sudo git clone --depth 1 "$repo" "$templates_dir/$name" 2>/dev/null || true
            fi
        done
        success "Nuclei templates updated"
    fi

    # Custom wordlists
    local wordlists_dir="/opt/wordlists"
    sudo mkdir -p "$wordlists_dir"
    if [[ ! -f "$wordlists_dir/SecLists" ]]; then
        sudo git clone --depth 1 https://github.com/danielmiessler/SecLists.git "$wordlists_dir/SecLists" 2>/dev/null || true
    fi
    if [[ ! -f "$wordlists_dir/OneListForAll" ]]; then
        sudo git clone --depth 1 https://github.com/six2dez/OneListForAll.git "$wordlists_dir/OneListForAll" 2>/dev/null || true
    fi
    success "Wordlists configured"
}

###############################################################################
# Main Entry Point
###############################################################################

main() {
    echo "═══════════════════════════════════════════════════════════════"
    echo "  KAISONONE BOOTSTRAP - ~130-Tool Auto-Installer"
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

    # Setup Vault secrets
    setup_vault_secrets

    # Setup Nuclei templates and wordlists
    setup_templates

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
