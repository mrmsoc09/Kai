# TestSSL False Positives

## Certificate Chain Issues
- Intermediate CA missing from chain (fix: server config)
- Self-signed acceptable in dev/test (skip in prod)

## Compatibility vs Security
- Older clients require TLS 1.0 support (acceptable trade-off vs no encryption)
- Weak ciphers required for legacy device support (document and compensate)

## Misreported Issues
- Mitigation for POODLE via other means
- TLS compression disabled at OS level (not reported by TestSSL)
