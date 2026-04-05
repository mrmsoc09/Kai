# Paramspider Use Cases

## Scenario 1: Passive Parameter Baseline
Build a first-pass parameter inventory without touching target infrastructure.

## Scenario 2: SSRF Candidate Harvest
Prioritize URLs containing `url`/`redirect`/`dest`/`path` style inputs.

## Scenario 3: SQLi Candidate Routing
Push ID-like parameters into sqlmap candidate queues.

## Scenario 4: XSS Candidate Routing
Extract callback/query/search parameter families for dalfox testing.

## Scenario 5: Historical Endpoint Recovery
Recover old but potentially active endpoint patterns missed by live crawling.
