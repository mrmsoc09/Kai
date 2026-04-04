# Amass — Output Patterns

## HIGH SIGNAL
Same patterns as subfinder: admin, api, staging, internal, jenkins, grafana, vault, k8s, dev, portal subdomains.

## ADDITIONAL SIGNAL FROM ASN ENUMERATION
Domains found via ASN enumeration are often missed by other tools:
- Related company infrastructure
- Acquired companies still running on old domains
- Subsidiaries with shared ASN

## Verbose Mode Format
`subdomain.target.com (source_name)` — source annotation in parentheses.
