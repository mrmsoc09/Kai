# crlfuzz — Tool Overview

crlfuzz detects CRLF (Carriage Return Line Feed) injection vulnerabilities. It injects `%0d%0a` sequences into URL parameters and headers to test whether the application reflects them into HTTP response headers.

## Impact
- HTTP response splitting
- Cookie injection (session fixation)
- XSS via injected headers
- Cache poisoning via injected cache headers
- Open redirect via Location header injection

## Output Format
Plaintext with vulnerable URL listed when injection is confirmed.

## Pipeline Role
Phase 7 vulnerability scanning. Runs against all live hosts from httpx output. Host-level vulnerability — not parameter-specific.
