# Faraday-Community Use Cases

## Scenario 1: Multi-Tool Confirmation
Nikto, TestSSL, and nuclei_scan all flag "Weak TLS Cipher". Faraday creates single entry with 3-tool confirmation.

## Scenario 2: Dark Web Aggregation
Torbot, Onionsearch, Ahmia all find same breach on .onion. Faraday deduplicates to one critical finding.

## Scenario 3: Master Report Generation
Executive summary from master_findings.json. Single authoritative finding list.

## Scenario 4: Confidence Ranking
High-confidence = multi-tool confirmed. Low-confidence = single tool unconfirmed. Prioritize accordingly.

## Scenario 5: Evidence Assembly
For each finding, see which tools confirmed it. Supports validation and reporting.
