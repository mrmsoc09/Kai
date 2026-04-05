# Wafw00f Advanced Techniques

## Standard JSON Output
```bash
wafw00f target.com -o wafw00f.json -f json
```

## Host Selection
Run against each live host discovered by HTTP probing, not only root domains.

## Adaptive Routing
Use WAF detection output to set scanner-wide rates and payload caution notes in handoff metadata.

## Re-Check Timing
Re-run when target behavior changes (new CDN config, maintenance windows, major deploys).
