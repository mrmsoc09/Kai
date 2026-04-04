# SearchSploit False Positives

## Patched Versions
ExploitDB may list exploits for patched versions still in database. Check patch status.

## Environment-Specific
Exploit may require specific configuration. Doesn't work in all deployments.

## Mitigation
Use Nuclei templates to validate exploit applicability. Don't assume all matches are exploitable.

## DoS Exclusions
For bug bounty scope, often exclude DoS-only exploits. Configure output filter.
