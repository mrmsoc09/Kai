# nuclei — Use Cases

## Scenario 1: Technology-Aware Scan (Recommended)
```bash
nuclei -l live_hosts.txt \
  -t technologies/spring/ \
  -t exposures/ \
  -t misconfiguration/ \
  -s critical,high,medium \
  -rate-limit 20 -jsonl -o nuclei_results.json
```
3x faster than full scan, fewer false positives.

## Scenario 2: Comprehensive Scan (High-Value Targets)
```bash
nuclei -l live_hosts.txt \
  -t exposures/ -t misconfiguration/ \
  -t http/takeovers/ -t http/exposed-panels/ \
  -t token-spray/ -t ssl/ \
  -s medium,high,critical \
  -rate-limit 10 -jsonl
```

## WAF-Protected Targets
Reduce rate limit aggressively: `-rate-limit 5 -bulk-size 5`
