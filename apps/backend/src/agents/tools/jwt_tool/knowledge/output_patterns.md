# jwt_tool — Output Patterns

## CRITICAL — Authentication Bypass
- None algorithm accepted → server skips signature verification
- Algorithm confusion successful → attacker can forge tokens for any user

## HIGH — Weak Secret Found
- Brute force reveals HMAC secret → attacker can forge tokens for any user
- Key injection accepted → attacker controls signing key

## HIGH — Key Injection
- kid path traversal accepted
- JWK injection accepted

## MEDIUM — Misconfiguration
- Token reveals sensitive internal claims (user roles, internal IDs)
- Expired token accepted (no expiry enforcement)

## LOW
- Overly long expiry (tokens valid for days/weeks)
- No token rotation on logout
