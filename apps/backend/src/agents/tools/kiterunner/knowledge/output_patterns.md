# Kiterunner — Output Patterns

## HIGH SIGNAL
- `200` responses with data on undocumented endpoints
- `401` responses — endpoint exists, requires authentication
- `403` responses — endpoint exists, access controlled
- `/api/admin/` paths — admin-only API surface
- `/api/internal/` paths — internal service endpoints
- `/api/v0/` paths — deprecated/beta API (often less secured)
- `/actuator/` endpoints — Spring Boot metrics/health/env
- `/metrics`, `/debug/` — monitoring endpoints often unauthenticated

## MEDIUM SIGNAL
- `301`/`302` redirects to interesting internal locations
- `500` errors on specific paths — server-side processing occurring
- Significantly different response times on specific paths

## Filtering False Positives
Responses with the same content length as the dominant response are likely 404-equivalents.
Filter by response length variation from baseline — identical lengths = false positive.
