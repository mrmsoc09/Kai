# dnsx — False Positives

## Empty Results Are Not False Positives
Empty results (NXDOMAIN) mean the subdomain does not resolve. This is legitimate output, not a tool failure.

## Prior Session Note
43/45 empty results in a prior session was correct behavior for non-resolving subdomains — not a bug.

## Wildcard DNS
Without `-wd` flag, wildcard DNS will make every subdomain appear to resolve. Always use wildcard detection on large lists.
