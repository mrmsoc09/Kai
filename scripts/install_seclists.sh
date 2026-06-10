#!/usr/bin/env bash
set -e

DEST="${K1_SECLISTS_PATH:-/opt/seclists}"
SPARSE="${K1_SECLISTS_SPARSE:-1}"
REPO="https://github.com/danielmiessler/SecLists.git"

echo "[*] Installing SecLists to $DEST..."
mkdir -p "$DEST"
cd "$DEST"

# If the directory is already a git repo, clean it up to restart freshly
if [ -d ".git" ]; then
    echo "[*] Git repository already initialized. Cleaning up to restart..."
    rm -rf .git
    rm -rf *
fi

git init
git remote add origin "$REPO"

if [ "$SPARSE" = "1" ]; then
    echo "[*] Configuring ultra-sparse-checkout for exact files..."
    git config core.sparseCheckout true
    
    cat <<EOF > .git/info/sparse-checkout
# Content Discovery
Discovery/Web-Content/common.txt
Discovery/Web-Content/big.txt
Discovery/Web-Content/quickhits.txt
Discovery/Web-Content/directory-list-2.3-small.txt
Discovery/Web-Content/directory-list-2.3-medium.txt
Discovery/Web-Content/directory-list-2.3-big.txt
Discovery/Web-Content/raft-small-words.txt
Discovery/Web-Content/raft-medium-words.txt
Discovery/Web-Content/raft-large-words.txt
Discovery/Web-Content/raft-small-directories.txt
Discovery/Web-Content/raft-medium-directories.txt

# API Discovery
Discovery/Web-Content/api/api-endpoints.txt
Discovery/Web-Content/api/api-endpoints-res.txt
Discovery/Web-Content/api/objects.txt
Discovery/Web-Content/api/actions.txt

# CMS
Discovery/Web-Content/CMS/wordpress.fuzz.txt
Discovery/Web-Content/CMS/drupal.txt
Discovery/Web-Content/CMS/joomla.txt
Discovery/Web-Content/CMS/magento.txt
Discovery/Web-Content/CMS/sharepoint.txt

# DNS / Subdomains
Discovery/DNS/subdomains-top1million-5000.txt
Discovery/DNS/subdomains-top1million-20000.txt
Discovery/DNS/subdomains-top1million-110000.txt
Discovery/DNS/bitquark-subdomains-top100000.txt
Discovery/DNS/fierce-hostlist.txt
Discovery/DNS/shubs-subdomains.txt

# Fuzzing Payloads
Fuzzing/SQLi/Generic-SQLi.txt
Fuzzing/SQLi/quick-SQLi.txt
Fuzzing/XSS/XSS-Jhaddix.txt
Fuzzing/XSS/XSS-BruteLogic.txt
Fuzzing/LFI/LFI-Jhaddix.txt
Fuzzing/LFI/LFI-gracefulsecurity-linux.txt
Fuzzing/LFI/LFI-gracefulsecurity-windows.txt
Fuzzing/SSRF/Ssrf.php.txt
Fuzzing/XXE/XXEFuzzing.txt
Fuzzing/SSTI/ssti.txt
Fuzzing/traversal.txt
Fuzzing/polyglots.txt
Fuzzing/Open-Redirect/Open-Redirect.txt

# Passwords
Passwords/Common-Credentials/10k-most-common.txt
Passwords/Common-Credentials/100k-most-common.txt
Passwords/Common-Credentials/top-20-common-SSH-passwords.txt
Passwords/Common-Credentials/common-passwords-win.txt
Passwords/Leaked-Databases/rockyou-75.txt

# Usernames
Usernames/top-usernames-shortlist.txt
Usernames/Names/names.txt
Usernames/xato-net-10-million-usernames.txt
EOF
fi

echo "[*] Fetching SecLists metadata (depth=1)..."
git fetch --depth=1 --filter=blob:none origin master

echo "[*] Downloading only selected wordlist files..."
git checkout FETCH_HEAD

echo "[*] SecLists installation complete."
