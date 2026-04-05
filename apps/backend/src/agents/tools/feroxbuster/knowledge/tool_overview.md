# Feroxbuster Overview

Feroxbuster is a fast content discovery utility for recursive directory and file brute force. In KAISON it is used in structured JSON mode so findings can be parsed deterministically and routed to parameter discovery and vulnerability testing.

## Core Role
- Discover hidden paths quickly
- Prioritize high-value endpoints (`/admin`, `/api`, `/backup`, `/.git`)
- Adapt thread and request behavior when WAF telemetry is present

## Why It Is Preferred
Compared with legacy dirb/dirbuster workflows, feroxbuster has faster concurrency controls, richer filters, and cleaner JSON output for machine-driven handoff.
