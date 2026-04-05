# Masscan Advanced Techniques

## Baseline Command
```bash
masscan target.com -p 80,443,8080,8443,3000,4000,5000,8000,8888,9000,9090 \
  --rate 1000 --output-format json --output-filename masscan_output.json
```

## Sequencing
Run masscan first for speed, then hand discovered ports into targeted nmap runs for accurate fingerprinting.

## Rate Tuning
Increase rate only when infrastructure and policy allow. Keep conservative defaults for shared or sensitive environments.

## Retry Strategy
Repeat scans on unstable targets to reduce transient misses.
