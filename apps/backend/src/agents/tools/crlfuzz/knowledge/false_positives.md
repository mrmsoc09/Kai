# crlfuzz — False Positives

## WAF Stripping
Some WAFs strip CRLF sequences before passing to the app — response looks clean but WAF intercepted the payload. The app may still be vulnerable in other contexts (different encoding).

## URL Encoding Normalization
Some apps decode `%0d%0a` in URL but not in headers. Test both:
- Standard: `%0d%0a`
- Double-encoded: `%250d%250a`

## Body Reflection ≠ Header Injection
Verify injected content appears in HTTP **headers**, not the page body. Body reflection is a different (lower severity) issue.

## CDN Cached Responses
CDN caching may serve old responses. Add `Cache-Control: no-cache` to requests and verify injection is reproducible on cache miss.
