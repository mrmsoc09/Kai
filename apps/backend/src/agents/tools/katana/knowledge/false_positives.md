# Katana False Positives

## Static Asset Flood
Large frontend bundles can generate many low-value static links.

## Duplicate Route Paths
Client-side routers may emit equivalent endpoint variants repeatedly.

## Non-Actionable CDN URLs
Cross-origin static CDNs may appear in crawl output but fall outside scope.

## Mitigation
Filter static file suffixes, de-duplicate normalized paths, and preserve only actionable endpoints for injection/test routing.
