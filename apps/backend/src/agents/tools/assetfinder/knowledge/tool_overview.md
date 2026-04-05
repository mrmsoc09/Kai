# Assetfinder

Assetfinder is a fast passive subdomain discovery utility by tomnomnom. It pulls from certificate transparency and domain relationship sources to produce quick, low-noise candidate hostnames for recon triage.

## Primary Purpose
Passive subdomain enumeration without direct probing of target infrastructure.

## Output Format
One candidate domain per line in plaintext. Output is intentionally minimal and easy to merge with other passive sources.

## Pipeline Role
Run in parallel with subfinder and amass during Phase 1. Combined output is deduplicated, then sent to dnsx for validation and takeover checks.

## Strengths
Very fast startup and quick first-pass coverage, useful for immediate downstream probing while slower tools run.

## Limitations
Source coverage is narrower than subfinder + amass combined. Historical CT noise can include retired assets.
