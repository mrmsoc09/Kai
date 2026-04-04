# Corsy — False Positives

## The Exploitability Requirement
CORS misconfiguration is only exploitable if:
1. Reflected/wildcard origin is allowed, AND
2. Sensitive data exists in the response

A wildcard ACAO on a public endpoint with no sensitive data is **informational only**. Do not report as high severity.

## Verification Before Reporting
Verify what data is accessible via the misconfigured endpoint:
- Account data, tokens, PII = High severity
- Public content only = Info, not reportable

## Wildcard ACAO on Public Endpoints
`ACAO: *` is expected and intentional on public API endpoints. Only an issue when combined with `ACAC: true` or on authenticated endpoints that return sensitive data.

## CDN CORS Headers
Some CDNs add permissive CORS headers automatically. Verify the header comes from the application, not the CDN layer.
