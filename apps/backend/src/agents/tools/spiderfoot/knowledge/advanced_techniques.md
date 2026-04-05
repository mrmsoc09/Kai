# SpiderFoot Advanced Techniques

## Module Selection
Use orchestrator-driven `SPIDERFOOT_MODULES` environment profiles:
- Tier 0: low-risk passive sources
- Tier 1: broader enrichment
- Tier 2: constrained higher-risk source sets

## Output Handling
Prefer JSON output for deterministic parsing, typed findings, and audit-ready artifact retention.

## Escalation Trigger
Credential- or compromise-related data types should be escalated immediately to analyst review workflows.
