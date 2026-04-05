# GF False Positives

## Pattern Over-Match
Regex-like pattern hits can identify benign parameter usage.

## Context Loss
A URL may match a risky pattern syntactically but be non-actionable without state or auth context.

## Category Drift
Generic terms can map one URL to multiple categories with uncertain exploitability.

## Mitigation
Treat GF as prioritization guidance, then validate with tool-specific behavior checks and response analysis.
