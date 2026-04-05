# Findomain

Findomain is a high-speed passive subdomain discovery tool focused on certificate transparency and indexed internet data. It is distributed as a simple multiplatform binary and is optimized for fast, low-friction recon.

## Primary Purpose
Enumerate candidate subdomains quickly for early target expansion.

## Operational Characteristics
- Multiplatform binary release
- Supports quiet output for clean pipelines
- Supports file output directly from the command

## Pipeline Role
Runs in parallel with subfinder, assetfinder, and chaos (when available), then forwards deduplicated domains to dnsx.

## Constraints
Findomain is passive and does not validate liveness; DNS resolution is mandatory downstream.
