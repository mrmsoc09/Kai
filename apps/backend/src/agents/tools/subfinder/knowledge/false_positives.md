# Subfinder — False Positives

## Wildcard DNS False Positives
- **Symptom**: Every random subdomain resolves to same IP
- **Detection**: Generate random subdomain, run dig, if it resolves → wildcard configured
- **Filter**: Compare all subfinder results against wildcard IP, remove matches

## CDN-Hosted Subdomains
- Subdomains resolving to Cloudflare, Akamai, Fastly IPs are often not directly testable
- Note them but deprioritize for active scanning

## Parked Domains
- Subdomains returning 302 redirect to main domain or showing "coming soon" pages
- Deprioritize unless checking for subdomain takeover opportunity
