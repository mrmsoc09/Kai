# OWASP-ZAP Advanced Techniques

## Headless Execution
zap-cli quick-scan runs in headless mode. No GUI required. Container-friendly.

## Active Scanning
Full active scan mode tests with actual payloads. Higher noise rate but thorough coverage.

## Quick vs Full
Quick-scan: Basic active tests. Minutes.
Full scan: All checks, passive + active, plugins. Hours.

## Session Management
Can login before scanning. Tests for authentication bypass, session fixation.

## Risk Mapping
ZAP uses Risk: High/Medium/Low. Map to severity: critical/high/medium/low.

## Passive Component
Also includes passive scanning. Baseline without injection testing.
