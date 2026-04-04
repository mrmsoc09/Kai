# Torbot Use Cases

## Scenario 1: Initial Dark Web Reconnaissance
Fresh bug bounty program targeting a financial institution. Torbot depth-2 crawl identifies org name on 3 separate .onion credential markets. Escalate for evidence analysis.

## Scenario 2: Credential Exposure Verification
Breached customer list posted on dark web. Torbot search confirms org data is indexed and actively referenced by bad actors. Supports severity assessment.

## Scenario 3: Complementary Coverage
Torbot crawl + Onionsearch query + Ahmia index search gives full dark web coverage. Each tool covers different .onion indexing sources and search patterns.

## Scenario 4: Organizational Variations
Search for "Acme Inc", "AcmeInc", "Acme_Inc", "acme-inc" separately. Attackers may use different naming conventions.

## Scenario 5: Failure Handling
Tor service down = empty results. Not an error condition. Log it and continue with other agents.
