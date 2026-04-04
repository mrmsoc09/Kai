# GAU — Use Cases

## Scenario 1: Large Domain with Long History
```bash
gau target.com --timeout 900
```
Expect: 10-15 minute runtime for large domains.

## Scenario 2: API-Focused Target
```bash
gau api.target.com --subs
```
Look for versioned endpoints (`/v1`, `/v2`, `/v3`). Old versions often have weaker auth.

## Scenario 3: Parameter Discovery Pipeline
```bash
gau target.com | grep "?" | cut -d? -f2 | tr "&" "\n" | cut -d= -f1 | sort -u > params.txt
```
Feed `params.txt` to arjun for parameter fuzzing.
