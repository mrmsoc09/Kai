# KAISON AI Setup Integration Guide

## Wave 7 Tool Installation System

This guide documents how testssl.sh, spiderfoot, and graphql-cop integrate with the KAISON AI bootstrap system.

### Architecture Overview

```
bootstrap.sh
    ↓
scripts/setup.sh (main orchestrator)
    ↓
scripts/tools-bootstrap-functions.sh (Wave 7 tool install functions)
    ↓
[install_testssl | install_spiderfoot | install_graphql_cop]
    ↓
~/.local/bin/ (symlinks/wrappers)
    ↓
Tool availability in PATH
```

### Bootstrap Flow

#### 1. Entry Point: bootstrap.sh

```bash
./bootstrap.sh
```

Delegates to `scripts/setup.sh`.

#### 2. Main Orchestrator: scripts/setup.sh

- Sources `scripts/tools-bootstrap-functions.sh` early (after function definitions)
- Loads enabled tools from `tools/registry/tool_registry.yaml`
- For each tool with `execution_mode: native`:
  - Runs `install_verification_cmd` to check if tool is available
  - If missing and `installation_mode` is supported → calls `install_native_tool(name)`
  - Logs success/failure to readiness summary

#### 3. Bootstrap Functions: scripts/tools-bootstrap-functions.sh

Three main install functions with error handling and logging:

**install_testssl()**
```bash
# Creates ~/.local/share/kaison-tools/testssl/
# Clones: https://github.com/testssl/testssl.sh.git
# Makes: testssl.sh executable
# Symlinks: ~/.local/bin/testssl.sh → repo copy
```

**install_spiderfoot()**
```bash
# Creates ~/.local/share/kaison-tools/spiderfoot/
# Clones: https://github.com/smicallef/spiderfoot.git
# Installs Python deps: pip install -r requirements.txt
# Wrapper: ~/.local/bin/spiderfoot → python3 sf.py
```

**install_graphql_cop()**
```bash
# Attempts binary download first (x86_64/arm64):
#   - Fetches latest release from GitHub API
#   - Downloads pre-built binary for platform
#   - Creates symlink ~/.local/bin/graphql-cop
#
# Falls back to source build if binary unavailable:
#   - Clones: https://github.com/dolevf/graphql-cop.git
#   - Detects build system (Go, Python, etc.)
#   - Builds/installs and creates symlink
```

#### 4. PATH Registration

In `scripts/setup.sh` (line 443):
```bash
source .venv/bin/activate
export PATH="${HOME}/.local/bin:${PATH}"
```

All Wave 7 tool symlinks/wrappers in `~/.local/bin/` are immediately discoverable.

### Tool Registry Schema

Located: `tools/registry/tool_registry.yaml`

Entries for Wave 7 tools (Phase 2 onwards):

```yaml
- name: testssl
  agent_class: TestsslAgent
  category: vulnerability_scanning
  execution_mode: native
  binary_path: testssl.sh
  install_verification_cmd: ["testssl.sh", "--version"]
  timeout_seconds: 300
  safety_classification: passive

- name: spiderfoot
  agent_class: SpiderfootAgent
  category: intelligence_osint
  execution_mode: native
  binary_path: spiderfoot    # Wrapper script
  install_verification_cmd: ["spiderfoot", "--help"]
  timeout_seconds: 900
  safety_classification: passive

- name: graphql-cop
  agent_class: GraphqlCopAgent
  category: api_security
  execution_mode: native
  binary_path: graphql-cop
  install_verification_cmd: ["graphql-cop", "--help"]
  timeout_seconds: 180
  safety_classification: intrusive
```

### File Locations

```
~/.local/
├── bin/
│   ├── testssl.sh → ~/.local/share/kaison-tools/testssl/testssl.sh
│   ├── spiderfoot → [wrapper script calling sf.py]
│   └── graphql-cop → [symlink to binary or wrapper]
│
└── share/kaison-tools/
    ├── testssl/
    │   ├── testssl.sh (executable)
    │   └── ... (supporting files from repo)
    │
    ├── spiderfoot/
    │   ├── sf.py
    │   ├── requirements.txt
    │   └── ... (cloned repo)
    │
    └── graphql-cop/
        ├── (binary or source)
        └── ...
```

### Error Handling

#### Install Failures

If any Wave 7 tool fails to install:

1. Error logged to console with `[k1-tools]` prefix
2. Tool added to `TOOL_ERRORS` array in setup.sh
3. Bootstrap continues (non-fatal per default config)
4. Readiness summary shows tool as ✗

#### Verification Command Failures

If `install_verification_cmd` fails after installation:

1. Install is considered unsuccessful
2. Error appended to `TOOL_ERRORS`
3. Operator prompted to resolve and re-run `./bootstrap.sh`

#### Network/Permission Issues

- Git clone failures: Network error logged, fallback if available
- Permission denied: Suggests directory creation with user umask
- Missing dependencies: Suggested install command logged

### Debugging Installation Issues

#### Check Tool Availability

```bash
# Verify symlink/wrapper exists
ls -la ~/.local/bin/testssl.sh ~/.local/bin/spiderfoot ~/.local/bin/graphql-cop

# Test verification commands
testssl.sh --version
spiderfoot --help
graphql-cop --help
```

#### Manual Reinstall

```bash
# Source bootstrap functions manually
source scripts/tools-bootstrap-functions.sh

# Reinstall specific tool
install_testssl
install_spiderfoot
install_graphql_cop
```

#### Check Installation Logs

```bash
# Find installation errors in .env or setup output
cat .env | grep -i tool
cat runtime/.bootstrap_ready
```

### Configuration

#### Enabling/Disabling Tools

In `tool_registry.yaml`:

```yaml
- name: testssl
  enabled_by_default: true  # Set to false to skip bootstrap
  ...
```

#### Require External Tools

In `.env`:

```bash
# Set to false to allow bootstrap to succeed even if tools fail
K1_BOOTSTRAP_REQUIRE_EXTERNAL_TOOLS=true
```

### Platform Support

#### Tested Platforms

- Linux (Ubuntu 20.04+, Debian 11+)
- x86_64 and aarch64 (ARM64) architectures

#### macOS / Windows

- testssl.sh: Likely works (bash + curl required)
- spiderfoot: Likely works (Python 3.8+)
- graphql-cop: Binary not available for macOS/Windows in GitHub releases
  - Fallback: Build from source if Go/Python toolchain available
  - Workaround: Use Docker execution mode

### Integration with KAISON AI Pipeline

Once installed, Wave 7 tools are used by:

1. **Phase 1 (Recon)**: Spiderfoot for OSINT reconnaissance
2. **Phase 2 (Fingerprinting)**: testssl.sh for TLS/SSL analysis
3. **Phase 8 (API/Auth Testing)**: graphql-cop for GraphQL security validation

Tool agents are located:

- `apps/backend/src/agents/tools/{testssl|spiderfoot|graphql_cop}/agent.py`

Each agent wraps the tool CLI and integrates with the LangGraph mission runtime.

### Maintenance

#### Updating Tools

To get latest versions:

```bash
cd ~/.local/share/kaison-tools/testssl/
git pull origin main

cd ~/.local/share/kaison-tools/spiderfoot/
git pull origin main
pip install -q -r requirements.txt

# graphql-cop: Re-run bootstrap (checks for latest release)
./bootstrap.sh
```

#### Cleanup

Remove Wave 7 tools:

```bash
rm -rf ~/.local/share/kaison-tools/testssl/
rm -rf ~/.local/share/kaison-tools/spiderfoot/
rm -rf ~/.local/share/kaison-tools/graphql-cop/

rm ~/.local/bin/testssl.sh
rm ~/.local/bin/spiderfoot
rm ~/.local/bin/graphql-cop
```

### Troubleshooting

| Issue | Root Cause | Solution |
|-------|-----------|----------|
| `testssl.sh: command not found` | Symlink not created | Check `~/.local/bin/testssl.sh` exists; re-run `install_testssl()` |
| `spiderfoot: ModuleNotFoundError` | Python deps not installed | `cd ~/.local/share/kaison-tools/spiderfoot && pip install -r requirements.txt` |
| `graphql-cop: no such file` | Binary download failed, source build failed | Check GitHub releases available for your arch; try manual clone and build |
| `Permission denied: ~/.local/bin/` | User lacks write permissions | Run `mkdir -p ~/.local/bin` and check directory ownership |
| Bootstrap fails with "git: command not found" | Git not installed | `sudo apt-get install git` (Debian/Ubuntu) or platform equivalent |

### References

- Tool Registry: `tools/registry/tool_registry.yaml`
- Wave 7 Metadata: `tools/registry/tool_registry_wave7_entries.yaml`
- Bootstrap Functions: `scripts/tools-bootstrap-functions.sh`
- Setup Orchestrator: `scripts/setup.sh`
- Tool Agents: `apps/backend/src/agents/tools/*/agent.py`
