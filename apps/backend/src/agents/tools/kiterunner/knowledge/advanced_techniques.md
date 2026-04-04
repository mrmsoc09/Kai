# Kiterunner — Advanced Techniques

## Basic Scan With Large Wordlist
```bash
kr scan https://api.target.com \
  -w routes-large.kite \
  --output-format=json \
  -o kiterunner_output.json
```

## With Authentication (Finds Private Endpoints)
```bash
kr scan https://api.target.com \
  -w routes-large.kite \
  -H "Authorization: Bearer [token]" \
  --output-format=json
```
Authenticated scans typically find 3-5x more endpoints than unauthenticated.

## Multiple Targets
```bash
kr scan \
  https://api.target.com \
  https://api-v2.target.com \
  https://internal.target.com \
  -w routes-large.kite
```

## Thread Control
```bash
kr scan https://api.target.com -w routes-large.kite -c 20
```

## Fail Status Codes (Reduce Noise)
```bash
kr scan https://api.target.com -w routes-large.kite \
  --fail-status-codes 404,400
```

## Wordlist Options
- `routes-small.kite` — fast, ~10k routes
- `routes-large.kite` — thorough, ~500k routes
- Custom `.kite` from swagger2kiterunner for target-specific APIs:
```bash
swagger2kiterunner convert openapi.yaml -o target_routes.kite
kr scan https://api.target.com -w target_routes.kite
```
