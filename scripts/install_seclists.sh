#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# install_seclists.sh  — Clone or update SecLists into K1_SECLISTS_PATH
#
# Usage:
#   ./scripts/install_seclists.sh              # clone/update to default path
#   K1_SECLISTS_PATH=/data/seclists ./scripts/install_seclists.sh
#
# Default install path: /opt/seclists  (override with K1_SECLISTS_PATH)
# Requires: git (and ~1.7 GB disk space for full SecLists)
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

DEST="${K1_SECLISTS_PATH:-/opt/seclists}"
REPO="https://github.com/danielmiessler/SecLists.git"
SPARSE="${K1_SECLISTS_SPARSE:-0}"   # set to 1 to only clone high-priority lists

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
info()  { echo -e "${GREEN}[seclists]${NC} $*"; }
warn()  { echo -e "${YELLOW}[seclists]${NC} $*"; }
error() { echo -e "${RED}[seclists]${NC} $*" >&2; }

if ! command -v git &>/dev/null; then
    error "git is required. Install with: apt-get install -y git"
    exit 1
fi

# ── Check available disk space (need ~2 GB) ───────────────────────────────
FREE_KB=$(df -k "$(dirname "$DEST")" | awk 'NR==2 {print $4}')
if [[ "$FREE_KB" -lt 1800000 ]]; then
    warn "Less than 1.8 GB free — sparse checkout enabled automatically"
    SPARSE=1
fi

# ── Clone or pull ─────────────────────────────────────────────────────────
if [[ -d "$DEST/.git" ]]; then
    info "SecLists already cloned at $DEST — pulling latest..."
    git -C "$DEST" pull --ff-only origin master 2>&1 | tail -3
    info "SecLists updated."
else
    info "Cloning SecLists into $DEST ..."

    if [[ "$SPARSE" == "1" ]]; then
        warn "Sparse checkout: fetching high-priority lists only (~200 MB)"
        mkdir -p "$DEST"
        git -C "$DEST" init
        git -C "$DEST" remote add origin "$REPO"
        git -C "$DEST" config core.sparseCheckout true

        # Write sparse-checkout paths (high-value lists for bug bounty)
        mkdir -p "$DEST/.git/info"
        cat > "$DEST/.git/info/sparse-checkout" <<'EOF'
Discovery/Web-Content/big.txt
Discovery/Web-Content/common.txt
Discovery/Web-Content/directory-list-2.3-small.txt
Discovery/Web-Content/directory-list-2.3-medium.txt
Discovery/Web-Content/raft-small-words.txt
Discovery/Web-Content/raft-medium-words.txt
Discovery/Web-Content/raft-large-words.txt
Discovery/Web-Content/quickhits.txt
Discovery/Web-Content/api/
Discovery/Web-Content/CMS/
Discovery/Web-Content/SVNDigger/
Discovery/DNS/subdomains-top1million-5000.txt
Discovery/DNS/subdomains-top1million-20000.txt
Discovery/DNS/subdomains-top1million-110000.txt
Discovery/DNS/bitquark-subdomains-top100000.txt
Fuzzing/LFI/
Fuzzing/SQLi/
Fuzzing/XSS/
Fuzzing/SSRF/
Fuzzing/XXE/
Fuzzing/SSTI/
Fuzzing/traversal/
Fuzzing/polyglots.txt
Passwords/Common-Credentials/10k-most-common.txt
Passwords/Common-Credentials/100k-most-common.txt
Passwords/Common-Credentials/common-passwords-win.txt
Usernames/Names/names.txt
Usernames/top-usernames-shortlist.txt
Usernames/xato-net-10-million-usernames.txt
EOF
        git -C "$DEST" pull origin master
    else
        info "Full clone (~1.7 GB) — set K1_SECLISTS_SPARSE=1 to reduce this"
        git clone --depth 1 "$REPO" "$DEST"
    fi

    info "SecLists installed at $DEST"
fi

# ── Write a marker file with install metadata ────────────────────────────
COMMIT=$(git -C "$DEST" rev-parse --short HEAD 2>/dev/null || echo "unknown")
DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
cat > "$DEST/.kai_installed" <<EOF
installed_at=$DATE
commit=$COMMIT
path=$DEST
sparse=$SPARSE
EOF

info "Done. Commit: $COMMIT"
info "Set K1_SECLISTS_PATH=$DEST in your environment or .env file."
