# Chaos

Chaos (ProjectDiscovery) provides passive subdomain data from a curated community dataset. It is designed for immediate retrieval of known assets without active probing and is highly effective on popular bug bounty programs.

## Primary Purpose
Retrieve known subdomains with high confidence from a maintained passive dataset.

## Requirements
`CHAOS_API_KEY` is required. Free registration is available via ProjectDiscovery.

## Pipeline Role
Run early in passive recon; merge hits with subfinder/assetfinder/amass, then resolve with dnsx.

## Limitation
Coverage depends on dataset inclusion. Absence of results does not imply absence of assets.
