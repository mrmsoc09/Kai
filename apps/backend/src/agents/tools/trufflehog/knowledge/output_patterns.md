# Trufflehog Output Patterns

## Critical Signals
- AWS access keys
- API tokens and keys
- Database credentials
- Private cryptographic keys
- OAuth tokens
- Any verified secret

## Detection Method
Entropy-based detection. Verification by attempting use. Verified = critical severity.

## False Positive Sources
- Placeholder text in documentation
- Fake keys in test data
- Non-functional key patterns
