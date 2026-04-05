# Paramspider False Positives

## Historical Drift
Archive entries may reference endpoints no longer alive.

## Static Resource Params
Some URLs include cache-busting parameters on static assets and are low-priority for vuln testing.

## Duplicate Variants
Large numbers of URLs can differ only in values while sharing identical parameter names.

## Mitigation
Filter static resource suffixes, dedupe by parameter-set signature, and validate liveness before active exploitation.
