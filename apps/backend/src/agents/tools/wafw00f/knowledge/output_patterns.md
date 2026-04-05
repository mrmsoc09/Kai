# Wafw00f Output Patterns

## Core Fields
- `waf_detected` boolean
- `waf_name` vendor/engine clue
- `confidence` detection confidence

## Interpretation
- WAF detected: switch to low-rate, low-signature mode
- No WAF detected: baseline scan profile

## Downstream Consumers
nuclei_scan, nikto, dalfox, sqlmap, ssrfmap, corsy, crlfuzz, smuggler, testssl, and searchsploit should all inherit this decision profile.
