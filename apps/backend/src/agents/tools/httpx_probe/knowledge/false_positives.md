# httpx — False Positives

## 403 from CDN vs Application
CDN blocks (Cloudflare, Akamai) show 403 on all blocked requests. Check if the 403 is from the CDN WAF or the actual application. Use `httpx -cdn` to identify CDN-served hosts.

## Technology Detection Accuracy
httpx tech detection is heuristic. Confirm detected technology before running tech-specific exploit templates — false tech detections lead to wasted scans.
