# FFUF Overview

FFUF is a flexible fuzzing framework that supports multiple modes including directory/file discovery and virtual-host probing. In KAISON it runs with JSON output for deterministic parsing and adaptive threading.

## Core Role
- Discover hidden paths and vhosts
- Adapt threading/rate based on WAF context
- Feed validated paths to parameter and template scanners

## Multi-Mode Strength
One agent can pivot between directory and vhost discovery based on context flags.
