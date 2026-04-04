# TestSSL Output Patterns

## Critical Findings
- SSLv3 or TLS 1.0/1.1 enabled (POODLE, BEAST)
- Expired certificates
- Self-signed certificates
- Invalid certificate chains

## High Severity
- Weak ciphers (RC4, DES, NULL)
- Missing HSTS header
- No OCSP stapling

## Medium
- Informational ciphers
- TLS compression enabled
## Noise
- Informational cipher listings only
