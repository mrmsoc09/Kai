# GF Overview

GF applies reusable pattern definitions to URL corpora to pre-classify likely vulnerability classes. In KAISON it is the routing nexus that maps URL categories to specialized Phase 7 agents.

## Core Role
- Categorize URLs by pattern (`sqli`, `xss`, `ssrf`, `redirect`, `idor`, `rce`)
- Produce focused inputs for downstream exploit-check agents
- Keep high-risk categories (`rce`) under manual review constraints

## Operational Importance
GF converts broad URL sets into targeted test queues, improving precision and reducing noise.
