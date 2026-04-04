# jwt_tool — Use Cases

## Scenario 1: API-Heavy Program (Coinbase, X.com)
```bash
# Capture JWT from authenticated API call
jwt_tool [captured_token] -M at
```
Focus on algorithm confusion — common in OAuth/OIDC implementations.

## Scenario 2: Mobile App Backend
Extract JWT from app traffic via mitmproxy. Mobile apps often use weaker JWT configurations than web apps.

## Scenario 3: OAuth Implementation
```bash
# Check for algorithm confusion in OAuth token validation
jwt_tool [access_token] -X a
# Check scope escalation via token claim manipulation
jwt_tool [access_token] -I -pc scope -pv admin
```

## Scenario 4: Privilege Escalation Test
```bash
# After finding weak secret, forge admin token
jwt_tool [token] -T   # tamper mode to modify claims
# Set role: admin, then test against admin endpoint
```

## Scenario 5: Microservices Architecture
Each service may validate JWTs differently. Test the same token against multiple API endpoints — service-to-service JWT validation may have different weaknesses than user-facing auth.
