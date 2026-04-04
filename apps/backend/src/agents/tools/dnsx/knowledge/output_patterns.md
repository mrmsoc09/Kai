# dnsx — Output Patterns

## HIGH SIGNAL
- CNAME pointing to cloud service → subdomain takeover check
- AAAA record → IPv6 enabled, often less tested
- MX record on unexpected subdomain → may indicate email service

## NOISE
- A record to Cloudflare IP (104.x.x.x, 172.64.x.x) → CDN, not directly testable
- NXDOMAIN → subdomain does not exist

## Takeover Candidate Indicators
Any CNAME resolving to an unclaimed third-party service. Verify by:
1. Follow the CNAME
2. Check if the service shows a "not found" or "no such site" page
3. If the service allows registration of that name → takeover possible
