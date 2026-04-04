# nuclei — False Positives

## Rate by Severity
- `info` severity: informational only, not a finding
- `low` severity: verify manually before reporting
- `medium` and above: run through vision validation

## CDN Response FPs
Some templates trigger on CDN default responses (Cloudflare 403, Akamai 400). A template match from a CDN-proxied host may be a CDN-level response, not the application.

## Template-Specific Notes
Track FP-prone templates in memory (findings_correlation.jsonl) with `confirmed: false` flag. Known FP-prone categories: some tech-detection templates trigger on partial header matches.
