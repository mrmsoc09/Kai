# Feroxbuster Use Cases

## Scenario 1: Baseline Discovery
Run medium wordlist with JSON output to seed initial path inventory.

## Scenario 2: WAF-Constrained Recon
Reduce thread and request rate to avoid immediate blocking while preserving signal.

## Scenario 3: Extension-Focused Hunt
Enable `-x php,asp,json,bak,zip` for environments likely exposing backup or debug files.

## Scenario 4: High-Value Host Deep Dive
Increase depth only on confirmed high-value hosts after scope checks.

## Scenario 5: Wildcard Cleanup
Cluster by content-length and remove repetitive wildcard responses before handoff.
