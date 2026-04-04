# dalfox — False Positives

## Confirmation Model
dalfox confirms payloads actually execute, giving it a lower false positive rate than pattern-matching tools. Still run vision validation.

## CSP Blocking
A confirmed XSS payload may be blocked by Content-Security-Policy. Check CSP headers before reporting. A payload that executes in lab but is blocked by CSP in production is lower severity.

## Context Matters
Some confirmed payloads execute in non-exploitable contexts (inside HTML comments, data: attributes). Verify user impact.
