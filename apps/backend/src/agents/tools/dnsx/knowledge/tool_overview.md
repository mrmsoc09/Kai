# dnsx — Tool Overview

dnsx is a fast DNS resolution toolkit by ProjectDiscovery. It takes a list of subdomains and resolves them to IP addresses, discovers DNS record types, and identifies live hosts.

## Primary Role
Verify which discovered subdomains actually resolve. Subfinder and amass find subdomain names — dnsx confirms they exist in DNS.

## Output Format
JSON with record arrays (with `-json`) or plaintext.

## Key Finding Type
CNAME records pointing to cloud services are potential subdomain takeover candidates.

## Pipeline Role
Phase 1, after subfinder + amass. Input: combined deduplicated subdomain list. Output: resolved subdomains with IPs → feed to httpx.
