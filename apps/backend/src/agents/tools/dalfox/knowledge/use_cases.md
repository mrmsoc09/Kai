# dalfox — Use Cases

## Standard Pipeline
```bash
# Phase 3: gf extracts XSS candidates
gf xss all_urls.txt > gf_xss_urls.txt

# Phase 4: dalfox confirms
cat gf_xss_urls.txt | dalfox pipe --skip-bav --worker 20
```

## Authenticated API XSS
```bash
dalfox url "https://api.target.com/endpoint?q=test" \
  --header "Content-Type: application/json" \
  --header "Authorization: Bearer token"
```

## High-Value Target — Full DOM Scan
```bash
dalfox url "https://admin.target.com/" --deep-domxss --header "Cookie: admin_session=..."
```
