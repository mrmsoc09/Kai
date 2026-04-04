# Corsy — Use Cases

## Scenario 1: API-Heavy Program (Coinbase, X.com)
Run against all API endpoints specifically. APIs have the highest CORS misconfiguration rate.
```bash
corsy -u https://api.target.com -H "Cookie: session=valid_token"
```

## Scenario 2: Single-Page Application Backend
SPA backends often have overly permissive CORS left over from development workflows.

## Scenario 3: Mobile App API
Mobile apps sometimes have CORS disabled entirely for "convenience" — highest severity when combined with sensitive data exposure.

## Scenario 4: Staging Environments in Scope
Staging CORS is almost always misconfigured — often reflects any origin for developer convenience.
```bash
corsy -u https://staging-api.target.com -H "Origin: https://attacker.com"
```

## Scenario 5: OAuth and Auth Endpoints
Auth callback endpoints with CORS misconfigurations can lead to token theft.
Always test `/auth/`, `/oauth/`, `/token/` endpoints specifically.
