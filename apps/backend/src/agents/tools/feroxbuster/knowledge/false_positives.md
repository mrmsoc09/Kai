# Feroxbuster False Positives

## Wildcard Routing
Some applications return a generic success-looking page for any path. This can flood output with fake positives.

## Detection Method
Compare repeated content-length values and body signatures across unrelated paths.

## Mitigation
Apply `--filter-size <wildcard_size>` or downstream content-length clustering before escalating findings.

## Edge/CDN Artifact
Cached 404 handling at CDN layers can return misleading `200` responses. Validate suspected paths with secondary probes.
