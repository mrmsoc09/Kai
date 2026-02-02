#!/usr/bin/env bash
set -euo pipefail
# Bootstrap Docker Engine + compose plugin on Linux. Requires sudo.
if [[ $EUID -ne 0 ]]; then echo "Please run with sudo or as root: sudo $0" >&2; exit 1; fi
. /etc/os-release || true
case "${ID:-}" in
  ubuntu|debian)
    apt-get update -y
    apt-get install -y ca-certificates curl gnupg lsb-release jq
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/${ID}/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/${ID} $(. /etc/os-release && echo "$VERSION_CODENAME") stable" > /etc/apt/sources.list.d/docker.list
    apt-get update -y
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
    ;;
  fedora)
    dnf -y install dnf-plugins-core jq
    dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
    dnf -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
    ;;
  rhel|centos)
    yum -y install yum-utils jq
    yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
    yum -y install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
    ;;
  arch)
    pacman -Sy --noconfirm docker docker-compose jq
    systemctl enable --now docker
    ;;
  *)
    echo "Unsupported distro: ${ID:-unknown}. Install Docker + compose manually." >&2; exit 2
    ;;
esac
if id "${SUDO_USER:-$USER}" >/dev/null 2>&1; then usermod -aG docker "${SUDO_USER:-$USER}" || true; fi

docker --version || true; docker compose version || true
printf "Docker bootstrap complete. Re-login may be required to use docker without sudo.\n"
