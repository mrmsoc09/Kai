# AGENTS.md

Kai Autonomous Security Research Platform
AI Development Specification

---

# 1. Purpose

Kai (K1) is an autonomous security research and bug bounty orchestration platform.

The platform is designed to assist security researchers by automating:

* Opportunity intelligence
* Asset discovery
* Reconnaissance
* Vulnerability signal detection
* Evidence collection
* Benchmark validation
* Reporting preparation

Kai is designed as a **defensive research platform operating within authorized scopes only**.

Kai must **never perform unauthorized scanning or exploitation**.

---

# 2. Platform Development Priorities

Kai development must maintain equal priority across:

1. Core platform backend
2. Tool orchestration and automation scripts
3. Evidence and intelligence engines
4. System installers and update systems
5. Worker infrastructure
6. Operator UI/UX

Frontend improvements must **never come at the expense of backend capability or platform automation**.

Kai is primarily an **automation and intelligence platform**, not a UI-first product.

---

# 3. Platform Architecture

Kai consists of six primary subsystems.

---

## 3.1 Opportunity Intelligence Engine

This subsystem selects and ranks bug bounty opportunities.

Inputs include:

* program scope
* payout likelihood
* payout amount
* platform popularity
* recent vulnerability reports
* exploit availability
* exposed technologies
* recon intelligence

Sources include:

* NVD
* ExploitDB
* CISA KEV
* vendor advisories
* threat intelligence feeds
* recon results

The system produces **ranked hunt plans**.

Each plan must include:

* target ranking
* vulnerability pressure score
* expected effort cost
* reasoning summary
* supporting evidence references

Location:

```
core/intelligence/
```

---

## 3.2 Scope and Authorization Gate

All scanning and testing must pass through scope validation.

Required validation:

* program identifier
* authorization certificate
* allowed testing methods
* excluded assets

No tool may run without scope validation.

All tool execution must call:

```
scope_validator()
authorization_certificate_check()
```

---

## 3.3 Tool Orchestration Layer

Kai orchestrates tools using workers.

Workers must:

* enforce OPSEC limits
* control rate limits
* capture artifacts
* generate evidence objects
* respect scope validation

Workers run in asynchronous queues.

Location:

```
workers/
```

---

## 3.4 Tool Adapter Layer

External tools must be wrapped in adapters.

Adapters provide:

* input schema
* safe execution
* output normalization
* evidence generation

Location:

```
adapters/
```

Adapters must never be bypassed.

---

## 3.5 Evidence and Knowledge Layer

All findings must produce **Evidence Objects**.

Evidence objects provide:

* normalized data
* artifact hashes
* provenance tracking
* confidence scoring

Evidence objects are stored in:

```
core/evidence/
```

Evidence is indexed for retrieval using:

* vector search
* graph relationships
* artifact storage

LlamaIndex or equivalent may be used.

---

## 3.6 Platform Operations Layer

Kai includes operational tooling to support the platform.

Responsibilities include:

* system installation
* dependency management
* weekly tool updates
* health monitoring
* platform benchmarking

Location:

```
ops/
```

---

# 4. Supported Operating Systems

Primary supported systems:

* Debian 13
* Ubuntu 22.04 LTS

Compatible environments:

* Kali Linux
* Parrot Security OS
* Tsurugi OS

Primary testing must occur on Debian and Ubuntu.

Other systems are supported through containerized toolpacks.

---

# 5. Toolpack Architecture

Kai manages external tools using toolpacks.

A toolpack defines:

* tool installation method
* update method
* adapter mapping
* evidence output type
* required dependencies

Example toolpack categories:

Recon Tools
Vulnerability Detection
OSINT
Mobile Security
Supply Chain Security
Threat Intelligence
Automation Systems
SOC Integration

Toolpacks must be defined in:

```
ops/toolpacks.yaml
```

---

# 6. Supported Tool Ecosystem

Kai supports integration with the following tools.

Recon and Asset Discovery

* Subfinder
* Amass
* PureDNS
* Dnsx
* Massdns
* Naabu
* Nmap
* Masscan
* Httpx
* Httprobe
* Wafw00f
* BuiltWith
* Gau
* Waymore

Web and API Testing

* ffuf
* Feroxbuster
* Arjun
* ParamMiner
* LinkFinder
* SecretFinder
* Nuclei
* Dalfox
* Sqlmap
* XSStrike
* Commix

OSINT and Intelligence

* Spiderfoot
* Sherlock
* Maigret
* Social Analyzer
* Lampyre
* IntelX
* BreachDirectory
* Hudson Rock Cavalier
* Flare.io

Infrastructure Intelligence

* Shodan
* Censys
* Hunter.io
* crt.sh

Mobile and Reverse Engineering

* Frida
* Objection
* MobSF
* Ghidra
* Jadx

AI Security Testing

* Garak
* PyRIT

Supply Chain Security

* Trivy
* Syft
* Grype
* Cycode
* Socket.dev
* Snyk
* Endor Labs

Automation and Security Platforms

* n8n
* Shuffle
* TheHive
* Cortex
* Wazuh

Bug Bounty Infrastructure

* Rengine
* BBRF
* Axiom

Security Testing Suites

* Burp Suite Pro
* Caido
* OWASP ZAP

Monitoring and Analysis

* Wireshark
* Cyber Triage
* PlexTrac

Threat Intelligence Platforms

* Wiz
* Sysdig Secure
* ThreatModeler
* Vanta
* Chainalysis Reactor

Agent and Automation Frameworks

* Agent-Zero
* LangChain
* LangGragh
* LangSmith
* DeepAgents
* Praison AI
* CAI
* PentAGI
* PentestAgents

Knowledge Systems

* LlamaIndex
* VertexAI

---

# 7. Tool Adapter Contract

All tools must implement adapters.

Example:

```
class ToolAdapter(BaseAdapter):

    tool_id: str
    version: str
    supported_targets: list

    async def run(self, target, config):
        pass
```

Adapters must:

* enforce OPSEC rules
* normalize outputs
* generate evidence objects
* store artifacts

Artifacts must be written to:

```
artifacts/<run_id>/<tool_id>/
```

Artifacts must include SHA256 hashes.

---

# 8. Evidence Object Schema

Evidence objects contain:

```
evidence_id
type
tool
target
timestamp
structured_data
confidence_score
artifacts
scope_status
```

Artifact metadata must include:

```
artifact_path
sha256
mime_type
description
```

---

# 9. Benchmark and Proof Engine

Kai must validate all platform claims using benchmark scenarios.

Benchmarks must run on:

* synthetic datasets
* offline fixtures
* deterministic inputs

Location:

```
benchmarks/
```

Metrics include:

Coverage

```
discovered_assets / total_assets
```

Precision

```
true_positives / reported_positives
```

Recall

```
true_positives / ground_truth
```

Runtime

```
total_execution_time
```

Cost

```
LLM token usage
API usage
```

Reliability

```
error_rate
retry_rate
```

---

# 10. Claim Registry

Platform capability claims must be defined in:

```
claims/claims.yaml
```

Each claim must include:

* metric
* threshold
* benchmark scenario
* validation condition

Claims must be validated automatically during benchmark runs.

---

# 11. Weekly Tool Update System

Kai must maintain weekly tool updates.

Update automation scripts live in:

```
ops/update_weekly.sh
```

Updates must:

* refresh tool repositories
* rebuild docker toolpacks
* update adapters
* validate version outputs
* run health checks

Updates must not break adapter compatibility.

---

# 12. Testing Requirements

Each tool adapter must include tests.

Required tests:

* adapter contract test
* output normalization test
* artifact hash test
* benchmark fixture test

Tests must not perform external scanning.

Fixtures must live in:

```
tests/fixtures/
```

---

# 13. Coding Rules

Allowed:

* typed Python code
* async execution
* modular architecture
* Pydantic schemas

Forbidden:

* direct CLI parsing in API layer
* bypassing adapter interfaces
* writing artifacts outside artifact directories
* embedding secrets in code

---

# 14. Documentation Requirements

New tools must update documentation.

Required files:

```
docs/cheatsheets/tool_adapters.md
docs/cheatsheets/operator_playbook.md
docs/cheatsheets/evidence_model.md
```

---

# 15. Development Workflow

When implementing a new tool:

1 Create adapter skeleton
2 Implement parser
3 Normalize evidence output
4 Add tests
5 Add benchmark scenario
6 Update documentation

---

# 16. Safety Policy

Kai must not generate or execute code that:

* performs exploitation
* performs denial of service
* bypasses scope validation
* automates credential attacks

Kai is strictly a **defensive research platform**.

---

# 17. AI Agent Responsibilities

AI coding agents working on this repository must:

* preserve architecture
* respect tool adapter contracts
* enforce evidence schemas
* maintain reproducible benchmarks
* respect authorization boundaries

When uncertain about architecture, agents must propose changes rather than implementing them directly.

---
