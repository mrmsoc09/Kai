# Assetfinder Advanced Techniques

## Default Enumeration
```bash
assetfinder --subs-only target.com
```

## Related Domain Recon
```bash
assetfinder target.com
```
Use this mode when acquisition mapping is in scope. It may introduce out-of-scope siblings, so enforce policy checks before testing.

## Merge Strategy
```bash
assetfinder --subs-only target.com >> combined_subdomains.txt
sort -u combined_subdomains.txt -o combined_subdomains.txt
```
Combine with subfinder and amass results to improve recall.

## Speed-First Tactic
Run assetfinder first to produce an initial queue for dnsx/httpx while slower passive tools complete.
