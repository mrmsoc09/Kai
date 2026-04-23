#!/usr/bin/env bash
set -u
set -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/output/logs"
REPORT_JSON="$LOG_DIR/manual_tool_install_report.json"
REPORT_TXT="$LOG_DIR/manual_tool_install_report.txt"
LOCAL_BIN="$HOME/.local/bin"
GOBIN_DIR="$(go env GOPATH 2>/dev/null)/bin"
TOOLS_DIR="$ROOT_DIR/runtime/tools-cache"
mkdir -p "$LOG_DIR" "$LOCAL_BIN" "$TOOLS_DIR"

export PATH="$LOCAL_BIN:$GOBIN_DIR:$PATH"

if command -v sudo >/dev/null 2>&1 && sudo -n true >/dev/null 2>&1; then
  HAS_SUDO=1
else
  HAS_SUDO=0
fi

if command -v npm >/dev/null 2>&1; then
  HAS_NPM=1
else
  HAS_NPM=0
fi

if command -v python3 >/dev/null 2>&1; then
  HAS_PY=1
else
  HAS_PY=0
fi

if command -v go >/dev/null 2>&1; then
  HAS_GO=1
else
  HAS_GO=0
fi

TMP_JSON="$REPORT_JSON.tmp"
: > "$REPORT_TXT"
printf '{\n  "generated_at": "%s",\n  "items": [\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" > "$TMP_JSON"
FIRST=1

json_escape() {
  python3 - <<'PY' "$1"
import json,sys
print(json.dumps(sys.argv[1]))
PY
}

write_item() {
  local name="$1" status="$2" method="$3" detail="$4"
  if [ "$FIRST" -eq 1 ]; then
    FIRST=0
  else
    printf ',\n' >> "$TMP_JSON"
  fi
  printf '    {"name": %s, "status": %s, "method": %s, "detail": %s}' \
    "$(json_escape "$name")" \
    "$(json_escape "$status")" \
    "$(json_escape "$method")" \
    "$(json_escape "$detail")" >> "$TMP_JSON"
  printf '%-24s | %-12s | %-12s | %s\n' "$name" "$status" "$method" "$detail" >> "$REPORT_TXT"
}

already_installed() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1
}

copy_go_bin() {
  local cmd="$1"
  if [ -x "$GOBIN_DIR/$cmd" ]; then
    cp "$GOBIN_DIR/$cmd" "$LOCAL_BIN/$cmd" 2>/dev/null || true
    chmod +x "$LOCAL_BIN/$cmd" 2>/dev/null || true
  fi
}

install_go() {
  local name="$1" cmd="$2" pkg="$3"
  if [ "$HAS_GO" -ne 1 ]; then
    write_item "$name" "failed" "go" "go not found"
    return
  fi
  if already_installed "$cmd"; then
    write_item "$name" "present" "go" "already in PATH"
    return
  fi
  if go install "$pkg" >/dev/null 2>&1; then
    copy_go_bin "$cmd"
    if already_installed "$cmd" || [ -x "$LOCAL_BIN/$cmd" ] || [ -x "$GOBIN_DIR/$cmd" ]; then
      write_item "$name" "installed" "go" "$pkg"
    else
      write_item "$name" "failed" "go" "installed package but binary not found"
    fi
  else
    write_item "$name" "failed" "go" "$pkg"
  fi
}

install_git_py() {
  local name="$1" cmd="$2" repo="$3"
  local clone_dir="$TOOLS_DIR/$name"
  if already_installed "$cmd"; then
    write_item "$name" "present" "git" "already in PATH"
    return
  fi
  rm -rf "$clone_dir" >/dev/null 2>&1 || true
  if git clone --depth 1 "$repo" "$clone_dir" >/dev/null 2>&1; then
    if [ -f "$clone_dir/requirements.txt" ] && [ "$HAS_PY" -eq 1 ]; then
      python3 -m pip install --user -r "$clone_dir/requirements.txt" >/dev/null 2>&1 || true
    fi
    if [ -f "$clone_dir/setup.py" ] || [ -f "$clone_dir/pyproject.toml" ]; then
      python3 -m pip install --user "$clone_dir" >/dev/null 2>&1 || true
    fi
    if already_installed "$cmd"; then
      write_item "$name" "installed" "git" "$repo"
      return
    fi
    if [ -f "$clone_dir/$cmd.py" ]; then
      ln -sf "$clone_dir/$cmd.py" "$LOCAL_BIN/$cmd" >/dev/null 2>&1 || true
      chmod +x "$LOCAL_BIN/$cmd" >/dev/null 2>&1 || true
      write_item "$name" "installed" "git" "$repo"
      return
    fi
    write_item "$name" "cloned" "git" "$repo"
  else
    write_item "$name" "failed" "git" "$repo"
  fi
}

install_pip_pkg() {
  local name="$1" cmd="$2" pkg="$3"
  if [ "$HAS_PY" -ne 1 ]; then
    write_item "$name" "failed" "pip" "python3 not found"
    return
  fi
  if already_installed "$cmd"; then
    write_item "$name" "present" "pip" "already in PATH"
    return
  fi
  if python3 -m pip install --user "$pkg" >/dev/null 2>&1; then
    if already_installed "$cmd" || [ -x "$HOME/.local/bin/$cmd" ]; then
      write_item "$name" "installed" "pip" "$pkg"
    else
      write_item "$name" "partial" "pip" "$pkg installed but executable missing"
    fi
  else
    write_item "$name" "failed" "pip" "$pkg"
  fi
}

install_npm_pkg() {
  local name="$1" cmd="$2" pkg="$3"
  if [ "$HAS_NPM" -ne 1 ]; then
    write_item "$name" "failed" "npm" "npm not found"
    return
  fi
  if already_installed "$cmd"; then
    write_item "$name" "present" "npm" "already in PATH"
    return
  fi
  if npm install -g --prefix "$HOME/.local" "$pkg" >/dev/null 2>&1; then
    if already_installed "$cmd" || [ -x "$HOME/.local/bin/$cmd" ]; then
      write_item "$name" "installed" "npm" "$pkg"
    else
      write_item "$name" "partial" "npm" "$pkg installed but executable missing"
    fi
  else
    write_item "$name" "failed" "npm" "$pkg"
  fi
}

install_apt_pkg() {
  local name="$1" cmd="$2" pkg="$3"
  if already_installed "$cmd"; then
    write_item "$name" "present" "apt" "already in PATH"
    return
  fi
  if [ "$HAS_SUDO" -ne 1 ]; then
    write_item "$name" "skipped" "apt" "sudo passwordless unavailable"
    return
  fi
  if sudo apt-get install -y "$pkg" >/dev/null 2>&1; then
    if already_installed "$cmd"; then
      write_item "$name" "installed" "apt" "$pkg"
    else
      write_item "$name" "partial" "apt" "$pkg installed but cmd missing"
    fi
  else
    write_item "$name" "failed" "apt" "$pkg"
  fi
}

install_custom_placeholder() {
  local name="$1" detail="$2"
  write_item "$name" "custom_needed" "script" "$detail"
}

# Go-first tools
install_go "amass" "amass" "github.com/owasp-amass/amass/v4/...@master"
install_go "subfinder" "subfinder" "github.com/projectdiscovery/subfinder/v2/cmd/subfinder@latest"
install_go "gau" "gau" "github.com/lc/gau/v2/cmd/gau@latest"
install_go "waybackurls" "waybackurls" "github.com/tomnomnom/waybackurls@latest"
install_go "naabu" "naabu" "github.com/projectdiscovery/naabu/v2/cmd/naabu@latest"
install_go "httpx" "httpx" "github.com/projectdiscovery/httpx/cmd/httpx@latest"
install_go "webanalyze" "webanalyze" "github.com/rverton/webanalyze/cmd/webanalyze@latest"
install_go "nuclei" "nuclei" "github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest"
install_go "katana" "katana" "github.com/projectdiscovery/katana/cmd/katana@latest"
install_go "dalfox" "dalfox" "github.com/hahwul/dalfox/v2@latest"
install_go "kiterunner" "kr" "github.com/assetnote/kiterunner@latest"
install_go "grpcurl" "grpcurl" "github.com/fullstorydev/grpcurl/cmd/grpcurl@latest"
install_go "tfsec" "tfsec" "github.com/aquasecurity/tfsec/cmd/tfsec@latest"
install_go "kube-bench" "kube-bench" "github.com/aquasecurity/kube-bench@latest"
install_go "githound" "git-hound" "github.com/tillson/git-hound@latest"
install_go "trufflehog" "trufflehog" "github.com/trufflesecurity/trufflehog/v3@latest"
install_go "dnsreaper" "dnsreaper" "github.com/punk-security/dnsReaper@latest"

# Apt tools when possible
install_apt_pkg "nmap" "nmap" "nmap"
install_apt_pkg "masscan" "masscan" "masscan"
install_apt_pkg "sqlmap" "sqlmap" "sqlmap"
install_apt_pkg "hydra" "hydra" "hydra"
install_apt_pkg "enum4linux-ng" "enum4linux-ng" "enum4linux-ng"
install_apt_pkg "onesixtyone" "onesixtyone" "onesixtyone"
install_apt_pkg "ipv6-toolkit" "alive6" "ipv6-toolkit"

# Python/pip tools
install_pip_pkg "spiderfoot" "spiderfoot" "spiderfoot"
install_pip_pkg "theharvester" "theHarvester" "theHarvester"
install_pip_pkg "torbot" "torbot" "torbot"
install_pip_pkg "scoutsuite" "scout" "scoutsuite"
install_pip_pkg "prowler" "prowler" "prowler"
install_pip_pkg "checkov" "checkov" "checkov"
install_pip_pkg "kube-hunter" "kube-hunter" "kube-hunter"
install_pip_pkg "s3scanner" "s3scanner" "s3scanner"
install_pip_pkg "jwt-tool" "jwt_tool" "jwt-tool"
install_pip_pkg "crackmapexec" "crackmapexec" "crackmapexec"
install_pip_pkg "bloodhound-python" "bloodhound-python" "bloodhound"
install_pip_pkg "domdig" "domdig" "domdig"
install_pip_pkg "nosqlmap" "nosqlmap" "nosqlmap"
install_pip_pkg "sslyze" "sslyze" "sslyze"
install_pip_pkg "dnsvalidator" "dnsvalidator" "dnsvalidator"
install_pip_pkg "apkleaks" "apkleaks" "apkleaks"
install_pip_pkg "mobsf" "mobsf" "mobsf"
install_pip_pkg "gopherus" "gopherus" "gopherus"
install_pip_pkg "onionscan" "onionscan" "onionscan"

# NPM tools
install_npm_pkg "wscat" "wscat" "wscat"
install_npm_pkg "csp-evaluator" "csp-evaluator" "@google/csp-evaluator"

# GitHub source installs
install_git_py "lazyrecon" "lazyrecon" "https://github.com/nahamsec/lazyrecon.git"
install_git_py "commix" "commix" "https://github.com/commixproject/commix.git"
install_git_py "tplmap" "tplmap" "https://github.com/epinna/tplmap.git"
install_git_py "corstest" "CORStest" "https://github.com/RUB-NDS/CORStest.git"
install_git_py "cloudmapper" "cloudmapper" "https://github.com/duo-labs/cloudmapper.git"
install_git_py "graphqlmap" "graphqlmap" "https://github.com/swisskyrepo/GraphQLmap.git"
install_git_py "restler" "restler" "https://github.com/microsoft/restler-fuzzer.git"
install_git_py "responder" "Responder" "https://github.com/lgandx/Responder.git"
install_git_py "testssl.sh" "testssl.sh" "https://github.com/drwetter/testssl.sh.git"
install_git_py "subover" "subover" "https://github.com/Ice3man543/SubOver.git"

# Custom/script-needed items from your list
install_custom_placeholder "darksearch-api" "API integration script needed"
install_custom_placeholder "openapi-introspection" "custom parser/orchestrator script needed"
install_custom_placeholder "inql" "Burp extension, manual install"
install_custom_placeholder "authmatrix" "Burp extension/manual workflow"
install_custom_placeholder "autorize-replacement" "custom authz diff script needed"
install_custom_placeholder "cloudsploit" "node project wiring needed"
install_custom_placeholder "trivy-k8s" "use trivy with k8s mode once trivy installed"
install_custom_placeholder "gitrob" "ruby toolchain needed"
install_custom_placeholder "oauth-scan" "custom script needed"
install_custom_placeholder "oidc-scan" "custom script needed"
install_custom_placeholder "mfa-sweep" "custom script needed"
install_custom_placeholder "racetheweb" "custom script needed"
install_custom_placeholder "turbo-intruder-alt" "Burp community replacement script needed"
install_custom_placeholder "rate-limit-tester" "custom script needed"
install_custom_placeholder "upload-scan-logic" "custom script needed"
install_custom_placeholder "payload-gen-verify" "custom script needed"
install_custom_placeholder "post-message-tracker" "custom browser instrumentation script needed"
install_custom_placeholder "burp-dominvader-replacement" "custom DOM sink scanner needed"
install_custom_placeholder "google-csp-tester" "custom script needed"
install_custom_placeholder "ppscan" "custom script needed"
install_custom_placeholder "protoscan" "custom script needed"
install_custom_placeholder "sharphound" "windows collector/manual"
install_custom_placeholder "ldap-tester" "custom script needed"
install_custom_placeholder "xpath-injector" "custom script needed"
install_custom_placeholder "xxe-injector" "custom script needed"
install_custom_placeholder "spring4shell-scanner" "use nuclei template/custom script"
install_custom_placeholder "spel-tester" "custom script needed"
install_custom_placeholder "hql-injector" "custom script needed"
install_custom_placeholder "mobsf-trufflehog-pipeline" "custom orchestration script needed"
install_custom_placeholder "nuclei-gitversioning" "custom orchestration script needed"
install_custom_placeholder "observatory" "API/client wiring needed"
install_custom_placeholder "testsslish" "alias to testssl.sh or wrapper needed"
install_custom_placeholder "nsbrute" "custom DNS brute script needed"
install_custom_placeholder "multi-engine-dorker" "custom multi-engine dorking script needed"

printf '\n  ]\n}\n' >> "$TMP_JSON"
mv "$TMP_JSON" "$REPORT_JSON"

echo "Report written to: $REPORT_JSON"
echo "Text summary: $REPORT_TXT"
