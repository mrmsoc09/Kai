# sqlmap — Advanced Techniques

## Safe Automated Scan (Default)
```bash
sqlmap -u "url?param=value" --level 2 --risk 1 --batch --technique B
```

## From File (Multiple URLs)
```bash
sqlmap -m urls.txt --level 2 --risk 1 --batch --technique B
```

## JSON/API Endpoints
```bash
sqlmap -u "url" \
  --data='{"key":"value"}' \
  --level 2 --risk 1 --batch \
  --headers="Content-Type: application/json"
```

## Boolean-Based Only (Safest, Non-Disruptive)
`--technique B` avoids time-based delays which are slow and potentially disruptive to the target application.

## Random User Agent
`--random-agent` reduces detection risk on WAF-protected targets.
