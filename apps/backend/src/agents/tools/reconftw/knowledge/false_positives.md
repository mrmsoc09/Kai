# ReconFTW False Positives

## Meta-Tool Duplication
ReconFTW frequently repeats findings already captured by specialized agents.

## Parsing Drift
Version or module changes can alter line formats and break brittle summary parsers.

## Scope Bleed
Aggregated outputs can include collateral domains when source modules are permissive.

## Mitigation
Deduplicate aggressively, enforce scope policy, and treat output as supplemental intelligence.
