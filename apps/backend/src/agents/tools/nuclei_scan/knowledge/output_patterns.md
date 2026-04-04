# nuclei — Output Patterns

## Template Match Interpretation
Template match = potential finding, NOT confirmed. All nuclei findings go through vision validation before reporting.

## HIGH SIGNAL Template Categories
- CVE templates with CVSS > 7.0
- Exposed credential templates (`token-spray/`)
- Misconfiguration templates on admin panels
- Subdomain takeover templates (`http/takeovers/`)
- Spring Boot actuator exposure (`/actuator/env`, `/actuator/heapdump`)

## Severity Reference
| Severity | Action |
|----------|--------|
| critical | Immediate validation, likely reportable |
| high | Validation required |
| medium | Manual review before reporting |
| low | Verify manually |
| info | Informational only, do not report |
