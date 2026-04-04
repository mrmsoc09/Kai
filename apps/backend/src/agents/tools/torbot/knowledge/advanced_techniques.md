# Torbot Advanced Techniques

## Depth Settings
Depth 1: Direct .onion pages only
Depth 2: Crawl up to one level of links (recommended for broad coverage)
Depth 3+: Disabled to prevent runaway scans and Tor exit node abuse

## Multi-Tool Coverage
Combine Torbot (crawl-based) with Onionsearch (query-based) and Ahmia-Client (clearnet index) for comprehensive dark web intelligence.

## Tor Service Dependency
Requires Tor service running on port 9050. Handle connection failures gracefully by logging and returning empty results. Never retry aggressively or change Tor circuit.

## Output Format
Returns JSON with URLs, content snippets, titles. All content is user-submitted text from .onion sites.

## Handling Connectivity Issues
Timeouts and connection refused errors are normal. Log them as informational. Empty results = no target mentions found.
