# Gitleaks False Positives

## Test Fixture Confusion
1. Fake credentials in test_data/fixtures
2. Mock API keys in examples
3. Placeholder tokens in documentation

## Mitigation
- Exclude test directories from scan
- Use gitleaks config to skip known test paths
- Manual review of suspected test fixtures
- Compare with Trufflehog results

## Path-Based Filtering
Configure .gitleaksignore to skip test, fixture, example, stub directories.
