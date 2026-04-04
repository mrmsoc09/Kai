# Kiterunner — False Positives

## Wildcard Routing (Most Common FP)
Some applications return `200 OK` for ALL paths (wildcard routing). These are not real endpoints.

**Detection:** Compare response body length to known 404 equivalent. If identical = wildcard routing.

**Fix:** Use `--fail-status-codes` or post-filter by response length:
- Find the most common content-length in output
- Treat that length as the "404 equivalent" and exclude it

## CDN Cached 200s
CDN may serve cached content for paths that no longer exist on origin. Verify directly against origin IP if possible.

## Parameter-Required Endpoints
Some endpoints return 400/500 because they require specific parameters — these ARE real endpoints, not FPs. They need parameter fuzzing (arjun) before dismissing.
