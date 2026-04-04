# dalfox — Advanced Techniques

## Pipeline from gf (Recommended)
```bash
cat gf_xss_urls.txt | dalfox pipe --skip-bav --worker 20
```

## Single URL Testing
```bash
dalfox url "https://target.com/page?param=value"
```

## Authenticated Testing
```bash
dalfox url "https://target.com/page?q=test" \
  --header "Cookie: session=abc123" \
  --header "Authorization: Bearer token"
```

## DOM XSS Discovery
```bash
dalfox url "https://target.com/" --deep-domxss
```
More thorough but significantly slower. Use for high-value targets only.
