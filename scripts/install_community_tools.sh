#!/bin/bash
# KAISON AI Community Edition — Tool Installer
# Installs all 28 new tools for Waves 1-3
# Run from repo root after ./bootstrap.sh

set -uo pipefail

LOCAL_BIN="${HOME}/.local/bin"
mkdir -p "$LOCAL_BIN"

log_ok()   { echo "  ✓ $1"; }
log_fail() { echo "  ✗ $1 — $2"; }
log_skip() { echo "  → $1 already installed"; }

install_go() {
  local name="$1" pkg="$2"
  if command -v "$name" &>/dev/null; then
    log_skip "$name"; return 0
  fi
  if go install "$pkg" 2>/dev/null; then
    log_ok "$name"
  else
    log_fail "$name" "go install failed"
  fi
}

install_pip() {
  local name="$1" pkg="${2:-$1}"
  if command -v "$name" &>/dev/null; then
    log_skip "$name"; return 0
  fi
  if pip install "$pkg" --break-system-packages --quiet 2>/dev/null; then
    log_ok "$name"
  else
    log_fail "$name" "pip install failed"
  fi
}

install_apt() {
  local name="$1" pkg="${2:-$1}"
  if command -v "$name" &>/dev/null; then
    log_skip "$name"; return 0
  fi
  if apt-get install -y "$pkg" 2>/dev/null; then
    log_ok "$name"
  else
    log_fail "$name" "apt-get install failed"
  fi
}

echo "=== KAISON AI Community Tools Installer ==="
echo ""
echo "=== Phase 1: Passive Recon ==="
install_go "assetfinder" "github.com/tomnomnom/assetfinder@latest"
install_pip "findomain"
install_pip "chaos"
install_go "github-subdomains" "github.com/gwen001/github-subdomains@latest"

echo ""
echo "=== Phase 2: Fingerprinting ==="
install_apt "nmap"
install_apt "masscan"
install_pip "wafw00f"
install_go "gowitness" "github.com/sensepost/gowitness@latest"
install_pip "whatweb" || install_apt "whatweb"

echo ""
echo "=== Phase 3: Content Discovery ==="
install_go "katana" "github.com/projectdiscovery/katana/cmd/katana@latest"
install_pip "paramspider"
install_pip "arjun"
install_go "hakrawler" "github.com/hakluke/hakrawler@latest"
install_go "ffuf" "github.com/ffuf/ffuf/v2@latest"
install_go "gf" "github.com/tomnomnom/gf@latest"

echo ""
echo "=== Phase 4: OSINT ==="
install_pip "spiderfoot"
install_pip "sherlock-project"
install_pip "phoneinfoga"
install_pip "social-analyzer"

echo ""
echo "=== Phase 5: Dark Web ==="
install_apt "tor"
install_pip "torbot"
install_pip "onionsearch"
log_ok "ahmia-client (requests-based)"

echo ""
echo "=== Phase 6: Secret Scanning ==="
install_go "trufflehog" "github.com/trufflesecurity/trufflehog/v3@latest"
install_go "gitleaks" "github.com/gitleaks/gitleaks/v8@latest"

echo ""
echo "=== Phase 7: Vulnerability ==="
install_apt "nikto"
install_pip "smuggler"

echo ""
echo "=== Phase 8: API Testing ==="
install_pip "graphql-cop"
install_pip "clairvoyance"

echo ""
echo "=== Verification ==="
echo "Tools installed. Ready for ./k1 start"
