# Corsy — Output Patterns

## CRITICAL — Credentialed Wildcard
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Credentials: true
```
Rarest and highest-severity combination. Allows cross-origin reads of authenticated responses.

## HIGH — Reflected Origin With Credentials
```
Access-Control-Allow-Origin: https://attacker.com   (reflects input)
Access-Control-Allow-Credentials: true
```
Allows attacker.com to read responses from authenticated user session.

## MEDIUM — Reflected Origin Without Credentials
```
Access-Control-Allow-Origin: https://attacker.com   (reflects input)
Access-Control-Allow-Credentials: false
```
Limited exploitability — cannot read cookies/auth headers.

## LOW — Null Origin Accepted
```
Access-Control-Allow-Origin: null
```
Exploitable from sandboxed iframes. Requires social engineering.

## NOISE — Properly Configured
```
Access-Control-Allow-Origin: https://www.target.com
```
Specific allowlisted origin — correct behavior, not a finding.
