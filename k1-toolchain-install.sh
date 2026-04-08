#!/bin/bash
set -euo pipefail

# K1 Toolchain Installation Script
# Must run with sudo

if [ "$EUID" -ne 0 ]; then
  echo "This script must run as root. Run with: sudo ./k1-toolchain-install.sh"
  exit 1
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

K1_TOOLS="/opt/k1-tools"
K1_BIN="$K1_TOOLS/bin"
K1_SRC="$K1_TOOLS/src"
GOPATH="${GOPATH:-$HOME/go}"

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $1"; }

# Ensure directories exist
mkdir -p "$K1_BIN" "$K1_SRC"

# Phase 0: Prerequisites
log_info "Installing system prerequisites..."
apt update -qq
apt install -y build-essential git curl wget golang-1.21 libpcap-dev libssl-dev pkg-config jq chromium-browser default-jre 2>&1 | grep -i "^setting up\|^unpacking" || true
log_ok "Prerequisites installed"

# Phase 1: Go Install Tools (Parallel)
log_info "Installing Go tools..."
export PATH="/usr/lib/go-1.21/bin:${PATH}"
go install github.com/ffuf/ffuf/v2@latest 2>&1 | grep -v "no matching files" &
go install github.com/dwisiswant0/crlfuzz/cmd/crlfuzz@latest 2>&1 | grep -v "no matching files" &
go install github.com/sensepost/gowitness@latest 2>&1 | grep -v "no matching files" &
go install github.com/tomnomnom/gf@latest 2>&1 | grep -v "no matching files" &
go install github.com/trufflesecurity/trufflehog/v3@latest 2>&1 | grep -v "no matching files" &
go install github.com/sundowndev/phoneinfoga/v2@latest 2>&1 | grep -v "no matching files" &
go install github.com/gwen001/github-subdomains@latest 2>&1 | grep -v "no matching files" &
wait
log_ok "Go tools installed"

# Kiterunner (Source Build)
log_info "Building Kiterunner..."
if [ ! -d "$K1_SRC/kiterunner" ]; then
  git clone https://github.com/assetnote/kiterunner "$K1_SRC/kiterunner" 2>&1 | head -5
fi
cd "$K1_SRC/kiterunner" && make build 2>&1 | tail -3
log_ok "Kiterunner built"

# Copy Go tools (instead of symlinking to /root/go/bin for permission safety)
log_info "Installing Go tools to K1_BIN..."
for tool in ffuf crlfuzz gowitness gf trufflehog phoneinfoga github-subdomains; do
  if [ -f "$GOPATH/bin/$tool" ]; then
    rm -f "$K1_BIN/$tool"  # Remove old symlinks
    cp "$GOPATH/bin/$tool" "$K1_BIN/$tool" && chmod +x "$K1_BIN/$tool"
  fi
done
rm -f "$K1_BIN/kr"
cp "$K1_SRC/kiterunner/dist/kr" "$K1_BIN/kr" && chmod +x "$K1_BIN/kr"
log_ok "Go tools installed to K1_BIN"

# GF patterns
log_info "Setting up GF patterns..."
mkdir -p ~/.gf
if [ ! -d "/tmp/gf-patterns" ]; then
  git clone https://github.com/1ndianl33t/Gf-Patterns /tmp/gf-patterns 2>&1 | head -3
fi
cp /tmp/gf-patterns/*.json ~/.gf/ 2>/dev/null || true
log_ok "GF patterns installed"

# Phase 2a: System Packages
log_info "Installing system packages..."
apt install -y whatweb exploitdb zaproxy 2>&1 | grep -i "^setting up\|^unpacking" || true
log_ok "System packages installed"

# Phase 2b: Masscan (Skip - binary builds often fail, use pre-built)
log_warn "Masscan: pre-built binary approach recommended, source build skipped"

# Phase 2c: Caido CLI (Skip - endpoint unstable)
log_warn "Caido CLI: download endpoint unstable, install manually if needed"
log_warn "  Manual: curl -L https://caido.io/download -o caido && chmod +x caido"

# Phase 3: ReconFTW
log_info "Installing ReconFTW..."
if [ ! -d "$K1_SRC/reconftw" ]; then
  git clone https://github.com/six2dez/reconftw "$K1_SRC/reconftw" 2>&1 | head -5
fi
if [ -f "$K1_SRC/reconftw/reconftw" ]; then
  chmod +x "$K1_SRC/reconftw/reconftw"
  ln -sf "$K1_SRC/reconftw/reconftw" "$K1_BIN/reconftw"
  log_ok "ReconFTW installed"
else
  log_warn "ReconFTW: script found but main binary missing, skipping"
fi

# Final: System Symlinks
log_info "Creating system symlinks..."
ln -sf /usr/bin/whatweb /usr/local/bin/whatweb
ln -sf /usr/bin/searchsploit /usr/local/bin/searchsploit
ln -sf /usr/bin/zaproxy /usr/local/bin/zaproxy

# Symlink everything from K1_BIN to /usr/local/bin
for binary in "$K1_BIN"/*; do
  [ -f "$binary" ] && [ -x "$binary" ] && ln -sf "$binary" "/usr/local/bin/$(basename "$binary")"
done
log_ok "System symlinks created"

# Make all binaries executable
chmod -R +x "$K1_BIN" "$K1_SRC"

# Verification
log_info "Verifying installation..."
export PATH="/opt/k1-tools/bin:/opt/k1-tools/go/bin:${PATH}"
TOOLS=("ffuf" "kr" "crlfuzz" "gowitness" "gf" "trufflehog" "phoneinfoga" "github-subdomains" "whatweb" "searchsploit" "zaproxy" "reconftw")
PASS=0
FAIL=0

for tool in "${TOOLS[@]}"; do
  if command -v "$tool" >/dev/null 2>&1; then
    log_ok "$tool"
    ((PASS++)) || true
  else
    log_error "$tool not found"
    ((FAIL++)) || true
  fi
done

echo ""
log_info "Installation complete: $PASS/${#TOOLS[@]} tools operational"
if [ $FAIL -eq 0 ]; then
  log_ok "STATUS: [OPERATIONAL] All tools ready"
else
  log_warn "STATUS: $FAIL tools missing (see above)"
fi

echo ""
echo "Toolchain location: $K1_TOOLS"
echo "Tools available from anywhere (in PATH): /usr/local/bin/"
