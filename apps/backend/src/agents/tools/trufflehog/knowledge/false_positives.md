# Trufflehog False Positives

## Unverified Results
- Entropy-high strings that aren't secrets
- Placeholder text with secret-like patterns
- Deliberately non-functional example keys

## Mitigation
Use --only-verified flag. Verified results are critical. Unverified may be false positives but warrant investigation.

## Test Fixtures
Test data and mock credentials. Filtered by gitleaks but not always by trufflehog.
