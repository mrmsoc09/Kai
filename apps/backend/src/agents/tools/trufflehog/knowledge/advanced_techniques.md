# Trufflehog Advanced Techniques

## Verified vs Unverified
Trufflehog can verify secrets by attempting validation. Verified findings are critical. Unverified may be false positives. Use --only-verified flag for high-confidence results.

## Git History Coverage
Scans all commits including deleted content. Finds secrets removed from current code but still in history. Essential for comprehensive audit.

## Complementary to Gitleaks
Both tools use different detection mechanisms. Trufflehog verification-based. Gitleaks regex-based. Run both for complete coverage. Different secrets may be caught by each.

## Credential Redaction Protocol
NEVER store or display actual secret values. Log detector type, file path, commit hash only. Redact everything else.

## Never Use Discovered Credentials
Credentials found are escalation evidence only. Reporting mechanism only. Never use for unauthorized access.
