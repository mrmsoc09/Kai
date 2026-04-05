# Arjun Overview

Arjun discovers hidden HTTP parameters by probing endpoint behavior with smart parameter wordlists. It helps reveal backend-accepted keys not visible in normal traffic.

## Core Role
- Enumerate hidden GET/POST parameters
- Build endpoint-to-parameter maps
- Feed parameter injection tooling with focused input

## Operational Guidance
Run Arjun on specific discovered endpoints (from feroxbuster/katana), not broad root URLs.
