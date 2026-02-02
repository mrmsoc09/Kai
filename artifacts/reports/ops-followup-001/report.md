# Google VRP Report — Weak password reset flow

Stakeholder: google_vrp
Severity: medium  | CWE: n/a  | CVSS: n/a

## Summary
Predictable tokens + no rate limiting
## Impact

## Affected Scope
accounts.example.com
## Steps to Reproduce
1) Request reset; 2) Predict token; 3) Takeover
## Evidence

## Mitigation
Use cryptographically secure tokens; add rate limiting
## Timeline

## References

