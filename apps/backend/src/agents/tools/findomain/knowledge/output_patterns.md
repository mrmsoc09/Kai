# Findomain Output Patterns

## Typical Signal
Findomain often returns clean hostnames tied to certificate issuance history.

Examples:
- `api.target.com`
- `staging.target.com`
- `portal.target.com`
- `jenkins.target.com`

## Priority Indicators
Admin, API, staging, internal, dashboard, and CI-related labels should be treated as high-value routing targets.

## Validation Note
No passive output should be treated as alive until dnsx and HTTP probing confirm reachability.
