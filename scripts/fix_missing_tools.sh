#!/bin/bash
# KAISON AI — Tool Installation Recovery Script
# Installs all tools that failed in install_community_tools.sh
# Run from: ~/Kai with .venv activated

set -uo pipefail

GOPATH_BIN="$(go env GOPATH 2>/dev/null)/bin"
LOCAL_BIN="$HOME/.local/bin"

mkdir -p "$LOCAL_BIN"
mkdir -p "$GOPATH_BIN"

log_ok()   { echo "  ✓ $1"; }
log_fail() { echo "  ✗ $1 — $2"; }
log_skip() { echo "  → $1 already installed"; }

# Ensure Go binaries and local bin are in PATH
export PATH="$PATH:$GOPATH_BIN:$LOCAL_BIN"

echo ""
echo "=== KAISON AI Tool Recovery Script ==="
echo ""

# ─────────────────────────────────────────
# GO TOOLS
# ─────────────────────────────────────────
echo "=== Installing Go-based tools ==="

install_go() {
    local name="$1"
    local pkg="$2"
    if command -v "$name" &>/dev/null; then
        log_skip "$name"
        return 0
    fi
    echo "  Installing $name..."
    if go install "$pkg" 2>/dev/null; then
        # Copy to local bin for PATH consistency
        cp "$GOPATH_BIN/$name" "$LOCAL_BIN/$name" \
            2>/dev/null || true
        log_ok "$name"
    else
        log_fail "$name" "go install $pkg failed"
    fi
}

install_go "nuclei" \
    "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"

install_go "dalfox" \
    "github.com/hahwul/dalfox/v2@latest"

install_go "katana" \
    "github.com/projectdiscovery/katana/cmd/katana@latest"

install_go "ffuf" \
    "github.com/ffuf/ffuf/v2@latest"

install_go "trufflehog" \
    "github.com/trufflesecurity/trufflehog/v3@latest"

# ─────────────────────────────────────────
# BINARY DOWNLOADS
# ─────────────────────────────────────────
echo ""
echo "=== Installing binary downloads ==="

# feroxbuster
if command -v feroxbuster &>/dev/null; then
    log_skip "feroxbuster"
else
    echo "  Installing feroxbuster..."
    FEROX_URL="https://github.com/epi052/feroxbuster/releases/latest/download/x86_64-linux-feroxbuster.zip"
    if curl -sL "$FEROX_URL" -o /tmp/ferox.zip \
        && unzip -q /tmp/ferox.zip \
           -d /tmp/ferox_extract 2>/dev/null \
        && cp /tmp/ferox_extract/feroxbuster \
           "$LOCAL_BIN/feroxbuster" \
        && chmod +x "$LOCAL_BIN/feroxbuster"; then
        log_ok "feroxbuster"
    else
        # Fallback: try direct binary
        if curl -sL \
            "https://github.com/epi052/feroxbuster/releases/latest/download/feroxbuster" \
            -o "$LOCAL_BIN/feroxbuster" \
            && chmod +x "$LOCAL_BIN/feroxbuster"; then
            log_ok "feroxbuster (direct binary)"
        else
            log_fail "feroxbuster" "download failed"
        fi
    fi
    rm -rf /tmp/ferox.zip /tmp/ferox_extract 2>/dev/null || true
fi

# sqlmap
if command -v sqlmap &>/dev/null; then
    log_skip "sqlmap"
else
    echo "  Installing sqlmap..."
    if pip install sqlmap \
       --break-system-packages --quiet 2>/dev/null; then
        log_ok "sqlmap"
    elif [ ! -d /opt/sqlmap ]; then
        git clone --quiet --depth 1 \
            https://github.com/sqlmapproject/sqlmap \
            /opt/sqlmap 2>/dev/null \
        && ln -sf /opt/sqlmap/sqlmap.py \
           "$LOCAL_BIN/sqlmap" \
        && chmod +x "$LOCAL_BIN/sqlmap" \
        && log_ok "sqlmap (git)" \
        || log_fail "sqlmap" "all methods failed"
    else
        ln -sf /opt/sqlmap/sqlmap.py \
            "$LOCAL_BIN/sqlmap" 2>/dev/null || true
        log_ok "sqlmap (existing git)"
    fi
fi

# ─────────────────────────────────────────
# APT TOOLS
# ─────────────────────────────────────────
echo ""
echo "=== Installing apt-based tools ==="

install_apt() {
    local name="$1"
    local pkg="${2:-$1}"
    if command -v "$name" &>/dev/null; then
        log_skip "$name"
        return 0
    fi
    echo "  Installing $name..."
    if sudo apt-get install -y "$pkg" \
       -qq 2>/dev/null; then
        log_ok "$name"
    else
        log_fail "$name" "apt-get install $pkg failed"
    fi
}

install_apt "nikto"
install_apt "tor"

# testssl
if command -v testssl.sh &>/dev/null \
   || command -v testssl &>/dev/null; then
    log_skip "testssl"
else
    echo "  Installing testssl..."
    if [ ! -d /opt/testssl ]; then
        git clone --quiet --depth 1 \
            https://github.com/drwetter/testssl.sh \
            /opt/testssl 2>/dev/null \
        && ln -sf /opt/testssl/testssl.sh \
           "$LOCAL_BIN/testssl.sh" \
        && chmod +x "$LOCAL_BIN/testssl.sh" \
        && log_ok "testssl" \
        || log_fail "testssl" "git clone failed"
    else
        ln -sf /opt/testssl/testssl.sh \
            "$LOCAL_BIN/testssl.sh" 2>/dev/null || true
        log_ok "testssl (existing)"
    fi
fi

# ─────────────────────────────────────────
# PIP TOOLS
# ─────────────────────────────────────────
echo ""
echo "=== Installing pip-based tools ==="

install_pip() {
    local name="$1"
    local pkg="${2:-$1}"
    if command -v "$name" &>/dev/null; then
        log_skip "$name"
        return 0
    fi
    echo "  Installing $name..."
    if pip install "$pkg" \
       --break-system-packages --quiet 2>/dev/null; then
        log_ok "$name"
    else
        log_fail "$name" "pip install $pkg failed"
    fi
}

install_pip "paramspider" "paramspider"
install_pip "spiderfoot" "spiderfoot"
install_pip "smuggler" "smuggler"
install_pip "graphql-cop" "graphql-cop"
install_pip "wafw00f" "wafw00f"

# ─────────────────────────────────────────
# PATH PERSISTENCE
# ─────────────────────────────────────────
echo ""
echo "=== Updating PATH ==="

# Add to bashrc if not already present
GOPATH_EXPORT="export PATH=\$PATH:\$(go env GOPATH)/bin"
LOCAL_EXPORT="export PATH=\$PATH:\$HOME/.local/bin"

if ! grep -q "go env GOPATH" ~/.bashrc 2>/dev/null; then
    echo "$GOPATH_EXPORT" >> ~/.bashrc
    echo "  Added Go bin to ~/.bashrc"
fi

if ! grep -q ".local/bin" ~/.bashrc 2>/dev/null; then
    echo "$LOCAL_EXPORT" >> ~/.bashrc
    echo "  Added .local/bin to ~/.bashrc"
fi

# Apply to current session
export PATH="$PATH:$(go env GOPATH)/bin:$HOME/.local/bin"
echo "  PATH updated for current session"

# ─────────────────────────────────────────
# FINAL VERIFICATION
# ─────────────────────────────────────────
echo ""
echo "=== Final Verification ==="
echo ""

PASS=0
FAIL=0

check_tool() {
    local name="$1"
    if command -v "$name" &>/dev/null; then
        echo "  ✓ $name: $(which $name)"
        ((PASS++))
    else
        echo "  ✗ $name: STILL NOT FOUND"
        ((FAIL++))
    fi
}

echo "Go tools:"
check_tool "nuclei"
check_tool "dalfox"
check_tool "katana"
check_tool "ffuf"
check_tool "trufflehog"

echo ""
echo "Binary tools:"
check_tool "feroxbuster"
check_tool "sqlmap"
check_tool "testssl.sh"

echo ""
echo "Apt tools:"
check_tool "nikto"
check_tool "tor"

echo ""
echo "Pip tools:"
check_tool "wafw00f"
check_tool "paramspider"
check_tool "spiderfoot"
check_tool "smuggler"
check_tool "graphql-cop"

echo ""
echo "Previously confirmed:"
check_tool "subfinder"
check_tool "amass"
check_tool "dnsx"
check_tool "naabu"
check_tool "gau"
check_tool "waybackurls"
check_tool "gitleaks"
check_tool "sherlock"
check_tool "whatweb"

echo ""
echo "==============================="
echo "Results: $PASS installed, $FAIL failed"
echo ""

if [ $FAIL -eq 0 ]; then
    echo "ALL TOOLS READY — Platform ready for hunt"
else
    echo "$FAIL tools still missing."
    echo "Check /tmp/tool_install.log for details."
    echo "Some tools may need manual installation."
fi

echo ""
echo "Run 'source ~/.bashrc' to apply PATH changes"
echo "Then run './k1-start' to start the platform"
