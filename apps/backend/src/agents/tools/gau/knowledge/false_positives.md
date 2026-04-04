# GAU — False Positives

## Historical URLs May 404 Now
GAU returns historical URLs — some will return 404 currently. Do not assume all discovered URLs are live. Feed to httpx for live verification before testing.

## Out-of-Scope Subdomains
Some URLs may be from subdomains out of scope. Filter by scope before passing to downstream agents.

## Duplicate URLs
GAU may return the same URL multiple times from different sources. Deduplicate with `sort -u` before processing.
