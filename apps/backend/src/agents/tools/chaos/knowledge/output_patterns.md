# Chaos Output Patterns

## Typical Output
One hostname per line with very little formatting noise.

## Common High-Value Labels
- `api.target.com`
- `admin.target.com`
- `internal.target.com`
- `dev.target.com`
- `staging.target.com`

Because chaos entries are often community-confirmed, these labels are strong candidates for early triage queues.

## Follow-On
Resolve immediately with dnsx and route live HTTP endpoints to visual and vuln fingerprinting.
