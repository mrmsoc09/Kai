# Subfinder — Use Cases

## Scenario 1: Large Program (500+ expected subdomains)
```bash
subfinder -d target.com -all -recursive -t 50 -timeout 60 -silent -o output.txt
```
Expect: 5-15 minute runtime

## Scenario 2: Well-Defended Target With WAF
```bash
subfinder -d target.com -silent
```
Passive only — WAF does not affect CT log queries. Subfinder is always safe regardless of WAF.

## Scenario 3: API-Heavy Target
```bash
subfinder -d target.com -all -silent
```
Pay special attention to: `api*`, `gateway*`, `graphql*`, `rest*`, `v1*`, `v2*`, `developer*` subdomains.

## Scenario 4: First Scan (No Prior Data)
Run `-all` flag for maximum coverage on first run. Memory will be empty — use conservative settings.

## Scenario 5: Follow-Up Scan (Prior Recon Complete)
Run default (no `-all`) for speed. Memory shows what was found before. Focus on new subdomains not in prior scan.
