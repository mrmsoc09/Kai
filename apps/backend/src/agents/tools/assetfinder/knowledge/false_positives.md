# Assetfinder False Positives

## Wildcard DNS
A wildcard record can make arbitrary hostnames resolve, inflating passive enumeration. Detect this with random labels and compare answers.

## Certificate Historical Artifacts
CT logs can retain retired hostnames that no longer exist. De-prioritize stale hosts after DNS and HTTP checks fail repeatedly.

## Related Domain Leakage
Running without `--subs-only` can include sibling domains that are out of scope. Scope guardrails must be applied before active testing.

## Practical Filter
Treat unresolved hosts and wildcard-colliding labels as noise unless corroborated by additional tools or recent evidence.
