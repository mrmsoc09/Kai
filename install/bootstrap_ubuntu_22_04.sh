#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root (or with sudo)." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive

# Pinned tool versions for reproducible bootstrap outcomes.
SUBFINDER_VERSION="${SUBFINDER_VERSION:-v2.6.8}"
HTTPX_VERSION="${HTTPX_VERSION:-v1.6.10}"
NAABU_VERSION="${NAABU_VERSION:-v2.3.4}"
DNSX_VERSION="${DNSX_VERSION:-v1.2.2}"
NUCLEI_VERSION="${NUCLEI_VERSION:-v3.3.8}"
KATANA_VERSION="${KATANA_VERSION:-v1.1.1}"
GAU_VERSION="${GAU_VERSION:-v2.2.4}"
WAYBACKURLS_VERSION="${WAYBACKURLS_VERSION:-v0.1.0}"
ASSETFINDER_VERSION="${ASSETFINDER_VERSION:-v0.1.1}"
FFUF_VERSION="${FFUF_VERSION:-v2.1.0}"

REQUIRED_TOOLS=(python3 pip3 nmap masscan curl jq)
OPTIONAL_TOOLS=(subfinder httpx naabu dnsx nuclei katana gau waybackurls assetfinder ffuf nikto)

apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  golang-go \
  git \
  jq \
  masscan \
  make \
  nmap \
  python3 \
  python3-pip \
  python3-venv \
  ruby-full \
  unzip

# Optional security packages available in Ubuntu repos.
apt-get install -y --no-install-recommends nikto || true

# Go-based tools (best effort).
if command -v go >/dev/null 2>&1; then
  export GOBIN=/usr/local/bin
  GO111MODULE=on go install -v "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@${SUBFINDER_VERSION}" || true
  GO111MODULE=on go install -v "github.com/projectdiscovery/httpx/cmd/httpx@${HTTPX_VERSION}" || true
  GO111MODULE=on go install -v "github.com/projectdiscovery/naabu/v2/cmd/naabu@${NAABU_VERSION}" || true
  GO111MODULE=on go install -v "github.com/projectdiscovery/dnsx/cmd/dnsx@${DNSX_VERSION}" || true
  GO111MODULE=on go install -v "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@${NUCLEI_VERSION}" || true
  GO111MODULE=on go install -v "github.com/projectdiscovery/katana/cmd/katana@${KATANA_VERSION}" || true
  GO111MODULE=on go install -v "github.com/lc/gau/v2/cmd/gau@${GAU_VERSION}" || true
  GO111MODULE=on go install -v "github.com/tomnomnom/waybackurls@${WAYBACKURLS_VERSION}" || true
  GO111MODULE=on go install -v "github.com/tomnomnom/assetfinder@${ASSETFINDER_VERSION}" || true
  GO111MODULE=on go install -v "github.com/ffuf/ffuf/v2@${FFUF_VERSION}" || true
fi

# Python tools
python3 -m pip install --upgrade pip
python3 -m pip install --upgrade \
  trufflehog \
  theHarvester || true

missing_required=()
for tool in "${REQUIRED_TOOLS[@]}"; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    missing_required+=("$tool")
  fi
done

if [[ "${#missing_required[@]}" -gt 0 ]]; then
  echo "Missing required tools: ${missing_required[*]}" >&2
  exit 2
fi

echo "Optional tool availability:"
for tool in "${OPTIONAL_TOOLS[@]}"; do
  if command -v "$tool" >/dev/null 2>&1; then
    echo "  [ok] $tool"
  else
    echo "  [missing] $tool"
  fi
done

echo "Bootstrap complete. Run scripts/verify_tool_registry_install.py for verification."
