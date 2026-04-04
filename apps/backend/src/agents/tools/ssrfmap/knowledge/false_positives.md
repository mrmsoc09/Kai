# SSRFmap — False Positives

## DNS Ping ≠ Full SSRF
DNS resolution of a controlled domain proves a request was initiated — but this alone is **low severity**.
Full SSRF requires response data to reach the attacker.

Distinguish carefully:
- DNS ping only → Low severity (blind SSRF)
- HTTP request confirmed via OOB but no response data → Medium
- Full response data returned to attacker → High/Critical

## Cloud Metadata False Reports
Verify cloud metadata responses contain real credential fields (`iam/security-credentials`) before escalating to Critical.

## Time-Based Indicators
Response time differences are weak evidence. Prefer response-based or OOB-callback confirmation.

## Legitimate URL Fetching
Some applications legitimately fetch URLs (social previews, RSS feeds). Verify the fetched URL is attacker-controlled and reaches internal infrastructure before reporting.
