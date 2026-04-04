# Subfinder — Output Patterns

## HIGH SIGNAL Subdomains
- `admin.target.com` — admin panel
- `api.target.com` — API endpoint
- `api-v2.target.com` — versioned API
- `staging-api.target.com` — staging environment
- `internal.target.com` — internal tooling
- `jenkins.target.com` — CI/CD system
- `grafana.target.com` — metrics dashboard
- `vault.target.com` — secrets management
- `k8s.target.com` — Kubernetes
- `dev-portal.target.com` — developer portal

## LOW SIGNAL / NOISE
- `mail.target.com` — standard mail server
- `smtp.target.com` — standard mail
- `ftp.target.com` — standard FTP
- `www.target.com` — main website (known)
- `cdn.target.com` — CDN (usually not testable)

## False Positive Patterns
- `*.target.com` — wildcard DNS record
- Subdomains resolving to same IP as www may be wildcard
- Test: `dig randomstring.target.com` — if it resolves, wildcard DNS is configured
