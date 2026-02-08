# Tool Integration System

## Overview

The Kaison K1 Platform integrates 150+ OSINT and security tools through a unified Adapter Pattern architecture. Tools are organized by capability, automatically discovered, and intelligently selected based on requirements.

## Architecture

### Core Components

1. **BaseToolAdapter** - Abstract base class for all tool integrations
2. **CapabilityProvider** - Groups tools by functional capabilities
3. **ToolRegistry** - Central registry for tool discovery and selection
4. **Tool Adapters** - Individual tool implementations

### Design Pattern: Adapter Pattern

```
┌─────────────────────────────────────┐
│         ToolRegistry                │
│  (Central Discovery & Selection)    │
└────────────┬────────────────────────┘
             │
             │ registers/discovers
             │
   ┌─────────┴──────────┬──────────┬───────────┐
   │                    │          │           │
┌──▼──────────┐  ┌──────▼────┐  ┌─▼────────┐  │
│  Amass      │  │  Nuclei   │  │TruffleHog│  ...
│  Adapter    │  │  Adapter  │  │ Adapter  │
└─────────────┘  └───────────┘  └──────────┘

Each adapter implements:
- get_capabilities() - What it can do
- check_availability() - Is it installed?
- execute() - Run the tool
- parse_output_to_findings() - Standardize results
```

## Tool Categories

### 1. Domain & Infrastructure Recon (30 tools planned)
**Implemented:**
- ✅ Amass - Subdomain enumeration, DNS reconnaissance
- ✅ Subfinder - Fast passive subdomain discovery

**Planned:**
- MassDNS - High-performance DNS resolver
- DNSRecon - DNS enumeration
- Fierce - DNS reconnaissance
- ... (25 more)

### 2. Vulnerability Scanning (DAST/SAST/SCA)
**Implemented:**
- ✅ Nuclei - Fast vulnerability scanner (5000+ templates)

**Planned:**
- ZAP - Web application security scanner
- Nikto - Web server scanner
- SQLMap - SQL injection tool
- ... (10+ more)

### 3. Code, Metadata & File Forensics (20 tools planned)
**Implemented:**
- ✅ TruffleHog - Secret and credential scanner

**Planned:**
- GitLeaks - Git secret scanner
- Semgrep - SAST for code patterns
- ExifTool - Metadata extraction
- ... (17 more)

### 4. Identity, Email & Credential Intelligence (25 tools planned)
**Planned:**
- TheHarvester - Email/subdomain harvesting
- Sherlock - Username enumeration
- h8mail - Breach data search
- ... (22 more)

### 5. Specialized & Automation Frameworks (15 tools planned)
**Planned:**
- Metasploit - Exploit framework
- Burp Suite - Web security testing platform
- Maltego - OSINT and link analysis
- ... (12 more)

### 6. Dark Web & Threat Intel (10 tools planned)
**Planned:**
- Shodan - Internet-wide scanning
- Censys - Internet asset discovery
- OnionScan - Dark web analysis
- ... (7 more)

## Capability Types

Tools advertise capabilities they provide:

```python
class CapabilityType(Enum):
    # Domain & Infrastructure
    SUBDOMAIN_ENUMERATION = "subdomain_enumeration"
    DNS_RECONNAISSANCE = "dns_reconnaissance"
    PORT_SCANNING = "port_scanning"
    WEB_CRAWLING = "web_crawling"
    SSL_TLS_ANALYSIS = "ssl_tls_analysis"
    CLOUD_ASSET_DISCOVERY = "cloud_asset_discovery"

    # Identity & Credentials
    EMAIL_HARVESTING = "email_harvesting"
    USERNAME_ENUMERATION = "username_enumeration"
    BREACH_DATA_SEARCH = "breach_data_search"
    PASSWORD_ANALYSIS = "password_analysis"
    SOCIAL_MEDIA_OSINT = "social_media_osint"

    # Code & Files
    SECRET_SCANNING = "secret_scanning"
    METADATA_EXTRACTION = "metadata_extraction"
    CODE_ANALYSIS = "code_analysis"
    DEPENDENCY_SCANNING = "dependency_scanning"

    # Vulnerability Discovery
    DAST = "dast"  # Dynamic Application Security Testing
    SAST = "sast"  # Static Application Security Testing
    SCA = "sca"    # Software Composition Analysis
    FUZZING = "fuzzing"
    API_SECURITY_TESTING = "api_security_testing"

    # Exploit & Validation
    EXPLOIT_DEVELOPMENT = "exploit_development"
    PAYLOAD_GENERATION = "payload_generation"
    VULNERABILITY_VALIDATION = "vulnerability_validation"
```

## Tool Tiers

### Community Tier
- Free, open-source features
- Basic functionality
- No API keys required

### Pro Tier
- Advanced features
- API integrations
- Requires configuration/API keys

### Enterprise Tier
- Commercial features
- Advanced automation
- Requires license

**Example:**
- Amass Community: Basic subdomain enumeration
- Amass Pro: API integrations (Shodan, Censys, VirusTotal)

## Usage Examples

### 1. Get Tool by Name

```python
from apps.backend.src.core.tool_adapters.tool_registry import get_tool_registry

# Get registry
registry = get_tool_registry()

# Get specific tool
amass = registry.get_tool("amass")

# Execute
if await amass.is_available():
    result = await amass.execute("example.com")
    print(f"Found {len(result.findings)} subdomains")
```

### 2. Select Best Tool for Capability

```python
from apps.backend.src.core.tool_adapters import CapabilityType, ToolTier

# Select best subdomain enumeration tool
tool = await registry.select_best_tool(
    capability=CapabilityType.SUBDOMAIN_ENUMERATION,
    tier=ToolTier.COMMUNITY
)

# Execute
result = await tool.execute("example.com")
```

### 3. Get All Tools by Category

```python
from apps.backend.src.core.tool_adapters import ToolCategory

# Get all vulnerability scanning tools
vuln_scanners = registry.get_tools_by_category(
    ToolCategory.VULNERABILITY_SCANNING
)

# Execute all available scanners
for scanner in vuln_scanners:
    if await scanner.is_available():
        result = await scanner.execute("https://example.com")
        print(f"{scanner.tool_name}: {len(result.findings)} vulnerabilities")
```

### 4. Get Registry Statistics

```python
# Get stats
stats = await registry.get_stats()

print(f"Total tools: {stats.total_tools}")
print(f"Available: {stats.available_tools}")
print(f"By category: {stats.by_category}")
print(f"By capability: {stats.by_capability}")
```

## Creating a New Tool Adapter

### Step 1: Create Adapter Class

```python
# apps/backend/src/core/tool_adapters/mytool_adapter.py

from .base_adapter import (
    BaseToolAdapter,
    ToolCategory,
    ToolTier,
    CapabilityType,
    ToolExecutionResult,
    ToolCapability
)

class MyToolAdapter(BaseToolAdapter):
    def get_tool_name(self) -> str:
        return "mytool"

    def get_tool_category(self) -> ToolCategory:
        return ToolCategory.DOMAIN_INFRASTRUCTURE

    def get_capabilities(self) -> List[ToolCapability]:
        return [
            ToolCapability(
                capability_type=CapabilityType.SUBDOMAIN_ENUMERATION,
                confidence=0.85,
                description="My tool subdomain discovery",
                tier_required=ToolTier.COMMUNITY
            )
        ]

    async def check_availability(self) -> bool:
        # Check if tool is installed
        import shutil
        return shutil.which("mytool") is not None

    async def execute(self, target: str, options: Optional[Dict[str, Any]] = None):
        # Execute tool and return results
        started_at = datetime.utcnow()

        # Run tool...
        # cmd = ["mytool", target]
        # proc = await asyncio.create_subprocess_exec(...)

        # Parse output
        findings = self.parse_output_to_findings(raw_output, target)

        return ToolExecutionResult(
            tool_name=self.tool_name,
            success=True,
            started_at=started_at,
            completed_at=datetime.utcnow(),
            duration_seconds=duration,
            findings=findings,
            raw_output=raw_output
        )

    def parse_output_to_findings(self, raw_output: str, target: str):
        # Parse tool-specific output format
        findings = []
        # ... parsing logic ...
        return findings
```

### Step 2: Register in Tool Registry

```python
# apps/backend/src/core/tool_adapters/tool_registry.py

from .mytool_adapter import MyToolAdapter

class ToolRegistry:
    def _register_core_tools(self):
        # ... existing tools ...
        self.register_tool(MyToolAdapter())
```

### Step 3: Test

```python
# Test availability
tool = registry.get_tool("mytool")
available = await tool.is_available()
print(f"mytool available: {available}")

# Test execution
if available:
    result = await tool.execute("example.com")
    print(f"Found {len(result.findings)} results")
```

## High-Priority Tools

### 1. Maltego Community/Pro
**Status:** Planned
**Category:** Specialized & Automation Frameworks
**Capabilities:**
- Link analysis
- OSINT data aggregation
- Visual relationship mapping

**Integration Notes:**
- Community: Basic transforms
- Pro: Full transform library + custom transforms

### 2. Burp Suite Community/Pro
**Status:** Planned
**Category:** Vulnerability Scanning
**Capabilities:**
- Web application security testing
- Proxy and interceptor
- Scanner and intruder

**Integration Notes:**
- Community: Manual testing tools
- Pro: Automated scanner + advanced features

### 3. Metasploit Framework
**Status:** Planned
**Category:** Exploit Validation
**Capabilities:**
- Exploit development
- Payload generation
- Vulnerability validation

**Integration Notes:**
- Community: Full framework
- Pro: Commercial modules + support

## Tool Discovery & Installation

Tools are discovered at runtime. If a tool is not installed, the platform logs a warning but continues operating.

### Recommended Installation

```bash
# Domain & Infrastructure
go install -v github.com/owasp-amass/amass/v4/...@master

# Vulnerability Scanning
go install -v github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest
nuclei -update-templates

# Secret Scanning
brew install trufflehog
# or: go install github.com/trufflesecurity/trufflehog/v3@latest

# ... install other tools as needed
```

## API Integration

Some tools require API keys for Pro features:

**Amass (Pro):**
```ini
# ~/.config/amass/config.ini
[data_sources.Shodan]
[data_sources.Shodan.Credentials]
apikey = YOUR_API_KEY

[data_sources.Censys]
[data_sources.Censys.Credentials]
apikey = YOUR_API_KEY
secret = YOUR_SECRET
```

**Shodan:**
```bash
export SHODAN_API_KEY=your_key_here
```

## Performance & Optimization

### Parallel Execution

Tools can be executed in parallel for faster results:

```python
import asyncio

# Get multiple tools
tools = await registry.get_available_tools(
    category=ToolCategory.DOMAIN_INFRASTRUCTURE
)

# Execute in parallel
results = await asyncio.gather(*[
    tool.execute("example.com") for tool in tools
])
```

### Caching

Tool results are cached to avoid redundant scans:
- Subdomain results cached for 24 hours
- Vulnerability scan results cached for 1 hour
- Secret scan results never cached (always fresh)

## Integration with Autonomous Scanning

Tools are automatically selected and executed during autonomous BBP scanning workflow:

```
Phase 3: Reconnaissance
  ↓
Select best SUBDOMAIN_ENUMERATION tool
  ↓
Execute tool (e.g., Amass)
  ↓
Parse findings to standard format
  ↓
Pass to next phase
```

## Future Enhancements

1. **Tool Chains** - Sequential execution of related tools
2. **Smart Selection** - ML-based tool selection based on target characteristics
3. **Resource Management** - CPU/memory limits per tool
4. **Distributed Execution** - Run tools on separate worker nodes
5. **Custom Tool Configs** - Per-tool configuration profiles

## Summary

The Tool Integration System provides:

✅ Unified interface for 150+ tools
✅ Automatic tool discovery
✅ Intelligent capability-based selection
✅ Community and Pro tier support
✅ Standardized output format
✅ Parallel execution support
✅ Extensible adapter pattern

**Current Status:** 3 tools implemented, 147 planned

**Next Priority Tools:**
1. Shodan (API-based scanning)
2. TheHarvester (email/subdomain)
3. Subfinder (subdomain enumeration)
4. GitLeaks (secret scanning)
5. Semgrep (SAST)
