#!/usr/bin/env bash
set -e

DEST="${K1_SECLISTS_PATH:-/opt/seclists}"
SPARSE="${K1_SECLISTS_SPARSE:-1}"
REPO="https://github.com/danielmiessler/SecLists.git"

echo "[*] Installing SecLists to $DEST..."
mkdir -p "$DEST"
cd "$DEST"

git init
git remote add origin "$REPO"

if [ "$SPARSE" = "1" ]; then
    echo "[*] Enabling sparse checkout..."
    git config core.sparseCheckout true
    
    cat <<EOF > .git/info/sparse-checkout
Discovery/Web-Content/
Discovery/DNS/
Fuzzing/
Passwords/Common-Credentials/
Passwords/Leaked-Databases/rockyou-75.txt
Usernames/
EOF
fi

echo "[*] Pulling from origin master (depth=1)..."
git pull --depth=1 origin master

echo "[*] SecLists installation complete."
