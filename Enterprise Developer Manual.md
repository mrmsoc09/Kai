# Enterprise Developer Manual

This manual provides comprehensive guidance for developers working with the KaisonOne platform. It covers API usage, tool development, architectural insights, and integration guides to help extend and customize the platform.

## Table of Contents

1. [Platform Overview (Developer Perspective)](#platform-overview-developer-perspective)
2. [API Usage Examples](#api-usage-examples)
    2.1. [Tool Operations](#tool-operations)
    2.2. [Program Operations](#program-operations)
3. [Architecture Overview](#architecture-overview)
4. [Tool Development Guide](#tool-development-guide)
    4.1. [Creating a New Tool](#creating-a-new-tool)
5. [Branding Customization (Frontend)](#branding-customization-frontend)
6. [Support and Documentation](#support-and-documentation)
    6.1. [Community & Support](#community--support)
7. [What's Next (Roadmap for Developers)](#whats-next-roadmap-for-developers)
8. [General Usage Information](#general-usage-information)
    8.1. [Unified Tool Framework (Developer Details)](#unified-tool-framework-developer-details)
    8.2. [Program Discovery System (Developer Details)](#program-discovery-system-developer-details)
    8.3. [Neural RAG System (Developer Details)](#neural-rag-system-developer-details)
9. [Integration Guides](#integration-guides)
    9.1. [CRLFuzz Agent Integration](#crlfuzz-agent-integration)
    9.2. [DALFox Integration Quick Start](#dalfox-integration-quick-start)
    9.3. [DALFox XSS Agent Integration](#dalfox-xss-agent-integration)
    9.4. [DNSX Integration Quick Start](#dnsx-integration-quick-start)
    9.5. [DNSX Resolver Agent Integration](#dnsx-resolver-agent-integration)
    9.6. [GAU Archive Agent Integration](#gau-archive-agent-integration)
    9.7. [GAU Integration Quick Start](#gau-integration-quick-start)
    9.8. [SSRFMap Agent Integration](#ssrfmap-agent-integration)
    9.9. [Waybackurls Archive Agent Integration](#waybackurls-archive-agent-integration)
    9.10. [Waybackurls Integration Quick Start](#waybackurls-integration-quick-start)
10. [Frontend Developer Documentation](#frontend-developer-documentation)
    10.1. [DASHBOARD README](#dashboard-readme)
    10.2. [Frontend Integration Guide](#frontend-integration-guide)
    10.3. [Kinetic Finish Polish](#kinetic-finish-polish)
    10.4. [Frontend README](#frontend-readme)
    10.5. [Structural Integrity Fixes](#structural-integrity-fixes)
    10.6. [DEV STACK RUN](#dev-stack-run)
    10.7. [DEV TESTING README](#dev-testing-readme)
    10.8. [HiL Gate Spec](#hil-gate-spec)
    10.9. [KEY INTAKE](#key-intake)
    10.10. [SCOPE ENFORCEMENT](#scope-enforcement)
    10.11. [THEHIVE BOOTSTRAP](#thehive-bootstrap)
    10.12. [VECTOR MEMORY](#vector-memory)
11. [Miscellaneous Developer-Relevant Information](#miscellaneous-developer-relevant-information)
    11.1. [Benchmarks README](#benchmarks-readme)
    11.2. [Benchmark Scenarios README](#benchmark-scenarios-readme)
    11.3. [CLAUDE (Developer Overview)](#claude-developer-overview)
    11.4. [Deduplication Report (Developer Context)](#deduplication-report-developer-context)
    11.5. [Docker README](#docker-readme)
    11.6. [Docker Sandbox README](#docker-sandbox-readme)
    11.7. [Hooks README](#hooks-readme)
    11.8. [Orchestration README](#orchestration-readme)
    11.9. [Prompts README](#prompts-readme)
    11.10. [Real Scan Data README](#real-scan-data-readme)
    11.11. [Skills README](#skills-readme)
    11.12. [Tools Engine README](#tools-engine-readme)
    11.13. [Tools Wrappers README](#tools-wrappers-readme)

---

## 1. Platform Overview (Developer Perspective)

### 1.1. Unified Tool Framework (Developer Details)

A complete system for creating, managing, and orchestrating AI-powered tools with autonomy tiers and human-in-the-loop approval workflows. Developers can extend existing tools or create new ones using the provided framework.

**Key Features (Developer Focus):**
-   Tool schema generation for LLM function calling
-   Autonomy tier gating (TIER 0-3)
-   Built-in metrics and statistics
-   Streaming execution support
-   Background async execution
-   Tool result serialization and storage-ready

### 1.2. Program Discovery System (Developer Details)

Automated discovery and scraping of 50+ bug bounty programs with payout estimation. The system's extensible scraper architecture allows developers to add support for new platforms.

**Capabilities (Developer Focus):**
-   Async scraping with progress streaming
-   Scope management (allowed/excluded items)
-   Payout estimation by severity
-   Program filtering and matching
-   Real-time program matching for findings
-   Extensible scraper architecture

### 1.3. Neural RAG System (Developer Details)

Hybrid retrieval-augmented generation with OpenAI embeddings and local fallback. Developers can configure embedding providers and integrate new vector stores.

**Features (Developer Focus):**
-   OpenAI text-embedding-3-large (3072 dims) as primary
-   Local Sentence-Transformers (384 dims) as fallback
-   Automatic provider switching on failure
-   Cosine similarity search
-   Metadata-based filtering
-   Batch embedding operations
-   Production-ready for pgvector

---

## 2. API Usage Examples

### 2.1. Tool Operations

**List all tools:**
```bash
curl http://localhost:8000/api/v1/tools
```

**Get tool details:**
```bash
curl http://localhost:8000/api/v1/tools/finding_validator
```

**Execute a tool (with auto approval):**
```bash
curl -X POST http://localhost:8000/api/v1/tools/quick_classifier/execute 
  -H "Content-Type: application/json" 
  -d '{
    "finding_text": "SQL injection in user search"
  }'
```

**Execute tool requiring approval:**
```bash
curl -X POST http://localhost:8000/api/v1/tools/finding_validator/execute 
  -H "Content-Type: application/json" 
  -d '{
    "finding_title": "XSS in Comment Form",
    "finding_description": "User input not escaped",
    "asset_type": "web",
    "estimated_severity": "high"
  }'
# Returns: {"execution_id": "...", "status": "pending_approval"}

# Approve execution
curl -X POST http://localhost:8000/api/v1/tools/finding_validator/approve 
  ?execution_id=... 
  ?user_id=admin
```

**Execute tool workflow (chaining):**
```bash
curl -X POST http://localhost:8000/api/v1/tools/orchestrate 
  -H "Content-Type: application/json" 
  -d '{
    "steps": [
      {
        "tool_id": "quick_classifier",
        "params": {"finding_text": "RCE in API"}
      },
      {
        "tool_id": "vulnerability_analyzer",
        "params": {
          "vulnerability_type": "rce",
          "affected_technology": "Node.js API",
          "attack_description": "...",
          "exploitation_difficulty": "easy"
        }
      },
      {
        "tool_id": "program_matcher",
        "params": {
          "finding_title": "RCE in API",
          "finding_scope": "*.example.com",
          "severity": "critical"
        }
      }
    ]
  }'
```

---

### 2.2. Program Operations

**List programs:**
```bash
curl 'http://localhost:8000/api/v1/programs?limit=20&min_payout=1000'
```

**Get program details:**
```bash
curl http://localhost:8000/api/v1/programs/google_vrp_main
```

**Start scraping:**
```bash
curl -X POST http://localhost:8000/api/v1/programs/scrape/google_vrp

# Check status
curl http://localhost:8000/api/v1/programs/scrape-status/google_vrp_1706808123
```

**Stream scrape (Server-Sent Events):**
```bash
curl http://localhost:8000/api/v1/programs/scrape/stream/microsoft 
  --header "Accept: text/event-stream"
```

**Match programs to finding:**
```bash
curl 'http://localhost:8000/api/v1/programs/match?finding_title=RCE&finding_scope=api.company.com&severity=critical'
```

**Get statistics:**
```bash
curl http://localhost:8000/api/v1/programs/statistics
```

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      Frontend (React/TS)                     │
│              Branding: theme/branding.ts/.css               │
│           Components: Tools UI, Programs UI, Workflows       │
└────────────────────┬────────────────────────────────────────┘
                     │ REST/WebSocket
┌────────────────────▼────────────────────────────────────────┐
│                  FastAPI Backend (Python)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ Tool Routers │  │ Program API  │  │ Embeddings   │       │
│  ├──────────────┤  ├──────────────┤  │ API (future) │       │
│  │ Validators   │  │ Scrapers     │  └──────────────┘       │
│  │ Analyzers    │  │ Discovery    │                          │
│  │ Orchestration│  │ Matching     │                          │
│  └──────────────┘  └──────────────┘                          │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Core Systems                            │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────────────┐    │   │
│  │  │LLM Client│ │Tool Frame│ │Embeddings Client│    │   │
│  │  │(OpenAI, │ │(Registry,│ │(OpenAI + Local) │    │   │
│  │  │Anthropic)│ │Registry) │ │Vector Store     │    │   │
│  │  └──────────┘ └──────────┘ └──────────────────┘    │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
│  Middleware: Security Headers | CSRF | Rate Limit | CORS    │
└────────────────────┬─────────────────────────────────────────┘
                     │ SQL/Redis
┌────────────────────▼────────────────────────────────────────┐
│              Data Layer                                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐                  │
│  │PostgreSQL│  │ pgvector │  │  Redis   │                  │
│  │Findings  │  │Embeddings│  │Caching   │                  │
│  │Programs  │  │          │  │Job Queue │                  │
│  └──────────┘  └──────────┘  └──────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Tool Development Guide

### 4.1. Creating a New Tool

```python
from src.core.tools import (
    BaseTool,
    ToolCategory,
    ToolParameter,
    ToolResult,
    ToolStatus,
    ToolAutonomyTier,
    register_tool,
)

class MyCustomTool(BaseTool):
    def __init__(self):
        parameters = [
            ToolParameter(
                name="input_param",
                type="string",
                description="Input parameter",
                required=True,
            ),
        ]

        super().__init__(
            id="my_custom_tool",
            name="My Custom Tool",
            description="Does something useful",
            category=ToolCategory.ANALYSIS,  # Pick appropriate category
            autonomy_tier=ToolAutonomyTier.TIER_2_APPROVE,  # Or TIER_0_AUTO
            parameters=parameters,
            version="1.0.0",
        )

    def execute(self, **kwargs) -> ToolResult:
        import time
        start_time = time.time()

        try:
            # Validate inputs
            is_valid, error = self.validate_parameters(**kwargs)
            if not is_valid:
                return ToolResult(
                    tool_id=self.id,
                    status=ToolStatus.FAILED,
                    output=None,
                    error=error,
                    execution_time_ms=(time.time() - start_time) * 1000,
                )

            # Your business logic here
            result = my_logic(kwargs.get("input_param"))

            # Record execution
            self.record_execution(...)

            return ToolResult(
                tool_id=self.id,
                status=ToolStatus.COMPLETED,
                output=result,
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        except Exception as e:
            return ToolResult(
                tool_id=self.id,
                status=ToolStatus.FAILED,
                output=None,
                error=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )

# Register the tool
register_tool(MyCustomTool())
```

---

## 5. Branding Customization (Frontend)

### TypeScript Constants (`branding.ts`):
```typescript
import { COLORS, UI, COMPONENT_STYLES } from '@/theme/branding'

// Use in components
const buttonStyle = COMPONENT_STYLES.button.primary
const primaryColor = COLORS.primary.main
```

**CSS Variables (`branding.css`):**
```css
/* Use in CSS */
button {
  background-color: var(--color-primary-main);
  color: var(--color-primary-contrast);
  padding: var(--spacing-md);
  border-radius: var(--border-radius-medium);
}
```

---

## 6. Support and Documentation

### 6.1. Community & Support
- GitHub Issues: Report bugs and request features
- Contributing: Follow the development guide

---

## 7. What's Next (Roadmap for Developers)

### 7.1. Phase 7d: DAG Orchestration (In Progress)
- Parallel task execution with dependencies
- Conditional branching
- Workflow composition
- Error recovery and retry logic

### 7.2. Phase 7e: Intelligent Agent Routing (Planned)
- Task classification engine
- Dynamic agent selection
- Confidence-based escalation
- Self-adaptive routing

### 7.3. Phase 7f: Advanced Detection (Planned)
- Fuzzing module
- Pattern detection
- Code analysis
- Full LangSmith integration
- Comprehensive documentation

---

## 8. General Usage Information

This section consolidates general usage information that is relevant to developers across the KaisonOne platform.

### 8.1. Unified Tool Framework (Developer Details)

The Unified Tool Framework provides a structured approach for creating, managing, and orchestrating AI-powered tools. For developers, this means understanding the tool schema generation, autonomy tier gating, and how to leverage features like streaming execution and background async operations. The framework is designed for extensibility and provides mechanisms for metrics, statistics, and result serialization.

### 8.2. Program Discovery System (Developer Details)

The Program Discovery System automates the identification and scraping of bug bounty programs. Developers interested in extending this system can focus on the extensible scraper architecture to add support for new platforms or customize existing scraping logic. Understanding scope management and real-time program matching is also crucial for developers building on this system.

### 8.3. Neural RAG System (Developer Details)

The Neural RAG System implements a hybrid retrieval-augmented generation approach. Developers should be familiar with configuring primary (OpenAI) and fallback (local Sentence-Transformers) embedding providers, as well as integrating new vector stores for cosine similarity search and metadata-based filtering. The system supports batch embedding operations and is production-ready for pgvector integration.

---

## 9. Integration Guides

This section provides quick start guides and integration details for various backend tools and agents.

### 9.1. CRLFuzz Agent Integration

Detailed integration steps for the CRLFuzz agent.

### 9.2. DALFox Integration Quick Start

Quick start guide for integrating DALFox.

### 9.3. DALFox XSS Agent Integration

Integration details for the DALFox XSS agent.

### 9.4. DNSX Integration Quick Start

Quick start guide for integrating DNSX.

### 9.5. DNSX Resolver Agent Integration

Integration details for the DNSX Resolver agent.

### 9.6. GAU Archive Agent Integration

Integration details for the GAU Archive agent.

### 9.7. GAU Integration Quick Start

Quick start guide for integrating GAU.

### 9.8. SSRFMap Agent Integration

Integration details for the SSRFMap agent.

### 9.9. Waybackurls Archive Agent Integration

Integration details for the Waybackurls Archive agent.

### 9.10. Waybackurls Integration Quick Start

Quick start guide for integrating Waybackurls.

---

## 10. Frontend Developer Documentation

This section contains documentation relevant to frontend development, including dashboard specifics, integration guides, and testing procedures.

### 10.1. DASHBOARD README

Overview and setup instructions for the frontend dashboard.

### 10.2. Frontend Integration Guide

Guide for integrating various components and services within the frontend.

### 10.3. Kinetic Finish Polish

Notes and guidelines for applying final polish and performance optimizations to the frontend.

### 10.4. Frontend README

General README for the frontend application.

### 10.5. Structural Integrity Fixes

Documentation on past structural integrity fixes in the frontend.

### 10.6. DEV STACK RUN

Instructions for running the development stack.

### 10.7. DEV TESTING README

README specifically for development testing procedures.

### 10.8. HiL Gate Spec

Specifications for Human-in-the-Loop gates from a frontend perspective.

### 10.9. KEY INTAKE

Documentation on key intake mechanisms within the frontend.

### 10.10. SCOPE ENFORCEMENT

Frontend aspects of scope enforcement.

### 10.11. THEHIVE BOOTSTRAP

Bootstrap procedures related to TheHive integration.

### 10.12. VECTOR MEMORY

Frontend documentation related to vector memory implementation.

---

## 11. Miscellaneous Developer-Relevant Information

This section contains other relevant documentation for developers.

### 11.1. Benchmarks README

Overview of benchmarks and how to run them.

### 11.2. Benchmark Scenarios README

Details on specific benchmark scenarios.

### 11.3. CLAUDE (Developer Overview)

Developer-focused overview of Claude integration.

### 11.4. Deduplication Report (Developer Context)

Context for developers regarding deduplication reports.

### 11.5. Docker README

Developer-relevant information about Docker usage.

### 11.6. Docker Sandbox README

Details about the Docker sandbox environment.

### 11.7. Hooks README

Documentation on implementing and using various hooks.

### 11.8. Orchestration README

Developer insights into orchestration mechanisms.

### 11.9. Prompts README

Details on prompt structures and usage for agents.

### 11.10. Real Scan Data README

Information about real scan data for development and testing.

### 11.11. Skills README

Overview of skill definitions and development.

### 11.12. Tools Engine README

Developer-centric documentation for the tools engine.

### 11.13. Tools Wrappers README

Details on creating and using tool wrappers.
