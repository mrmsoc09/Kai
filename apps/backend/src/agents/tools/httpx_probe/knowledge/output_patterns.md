# httpx — Output Patterns

## HIGH SIGNAL Responses
- `401 Unauthorized` on `admin.*`, `api.*`, `internal.*` — exists, blocked by auth
- `403 Forbidden` on interesting subdomains — access controlled asset
- `200 OK` on `dev.*`, `staging.*`, `test.*` — reduced security environments
- `302` redirect to login on interesting subdomain

## Technology Fingerprints That Matter
- **Spring Boot** — check actuator endpoints
- **Django** — check `/admin/`
- **WordPress** — run WP-specific nuclei templates
- **GraphQL** — flag for introspection tests

## NOISE
- `404 Not Found` — nothing there
- Connection timeout — host dead
- CDN hosts returning non-auth responses
