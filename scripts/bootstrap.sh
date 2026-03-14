#!/bin/bash
# Kai Platform Bootstrap for Ubuntu 22.04 LTS
set -e

echo "[+] Initializing Kai Environment..."

# Update and Install Core Dependencies
sudo apt-get update && sudo apt-get install -y \
    git python3 python3-pip golang-go nmap masscan \
    libpcap-dev libxml2-dev libxslt1-dev zlib1g-dev \
    libsqlite3-dev build-essential jq curl wget zip

# Install Rust (for tools like rustscan)
if ! command -v cargo &> /dev/null; then
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source $HOME/.cargo/env
fi

# Install Go-based Tools
echo "[+] Installing Go-based reconnaissance tools..."
export GOPATH=$HOME/go
export PATH=$PATH:/usr/local/go/bin:$GOPATH/bin

go install -v github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest
go install -v github.com/projectdiscovery/httpx/cmd/httpx@latest
go install -v github.com/projectdiscovery/naabu/v2/cmd/naabu@latest
go install -v github.com/projectdiscovery/nuclei/v2/cmd/nuclei@latest
go install -v github.com/projectdiscovery/katana/cmd/katana@latest
go install -v github.com/tomnomnom/assetfinder@latest
go install -v github.com/lc/gau/v2/cmd/gau@latest

# Install Python-based Tools
echo "[+] Installing Python-based vulnerability scanners..."
pip3 install sqlmap ffuf dalfox trufflehog

echo "[+] Bootstrap Complete. Please configure .env before running workflows."
