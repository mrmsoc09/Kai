# TestSSL Advanced Techniques

## Fast vs Full Scan
--fast mode: Basic certificate and protocol checks. Minutes.
Full scan: All cipher suites, compatibility, performance. Hours.

## Protocol Versions
Tests SSLv2, SSLv3, TLS 1.0, 1.1, 1.2, 1.3. Alerts on deprecated/weak versions.

## Cipher Strength
Tests cipher suites. Identifies weak encryption (RC4, DES, NULL ciphers). Maps to severity.

## Certificate Validation
Checks expiration, chain, self-signed, wildcard issues. Critical findings.

## HSTS, OCSP Stapling, etc
Security headers and modern TLS features assessment.
