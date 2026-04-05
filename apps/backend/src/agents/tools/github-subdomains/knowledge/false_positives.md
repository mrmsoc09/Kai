# Github-Subdomains False Positives

## Legacy Code Artifacts
Repositories may reference domains that were valid historically but no longer resolve.

## Test Fixtures and Mock Hosts
Some matches are placeholders used in examples or tests. Validate DNS and HTTP before prioritizing.

## Fork/Third-Party Pollution
Public forks can contain irrelevant domains. Deduplicate and filter by organization ownership when possible.

## API Limits
Rate limiting can silently reduce coverage if unauthenticated; monitor request budget and retry strategy.
