# sqlmap — Use Cases

## Standard Pipeline
```bash
# Phase 3: gf extracts SQLi candidates
gf sqli all_urls.txt > sqli_candidates.txt

# Phase 4: sqlmap safe detection
sqlmap -m sqli_candidates.txt --level 2 --risk 1 --batch --technique B
```

## Authenticated Scan
```bash
sqlmap -u "target?param=value" \
  --level 2 --risk 1 --batch \
  --headers="Cookie: session=abc123"
```

## API Endpoint
```bash
sqlmap -u "https://api.target.com/search" \
  --data='{"q":"test"}' \
  --level 2 --risk 1 --batch \
  --headers="Content-Type: application/json" \
  --headers="Authorization: Bearer token"
```
