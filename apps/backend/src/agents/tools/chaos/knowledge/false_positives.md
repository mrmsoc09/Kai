# Chaos False Positives

## Stale Dataset Entries
A previously observed subdomain may have been retired after inclusion in the dataset.

## Program Scope Drift
Programs evolve scope. A chaos hit may be technically real but out-of-scope at current policy time.

## Validation Path
Require resolution and reachability checks before promoting hits to active scan targets.

## Practical Risk
False confidence from trusted datasets can waste downstream cycles unless recency and liveness are verified.
