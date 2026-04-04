# Kiterunner — Use Cases

## Scenario 1: API-Heavy Target (Coinbase, X.com APIs)
```bash
# Unauthenticated first pass
kr scan https://api.target.com -w routes-large.kite --output-format=json -o kr_unauthed.json

# Authenticated second pass
kr scan https://api.target.com -w routes-large.kite \
  -H "Authorization: Bearer [token]" \
  --output-format=json -o kr_authed.json
```

## Scenario 2: Target-Specific Wordlist From OpenAPI
```bash
# If OpenAPI/Swagger spec found during recon:
swagger2kiterunner convert openapi.yaml -o target_routes.kite
kr scan https://api.target.com -w target_routes.kite
```

## Scenario 3: Mobile App API Discovery
Mobile apps call API endpoints not in web documentation. Capture mobile traffic first via mitmproxy to seed additional paths.

## Scenario 4: Versioned API Discovery
```bash
# Old API versions often still live and less secured
kr scan https://api.target.com -w routes-large.kite \
  --output-format=json | grep -E "v0|v1|internal|admin|debug"
```

## Scenario 5: GraphQL Alongside REST
Run against GraphQL endpoint base too — `/graphql/admin`, `/graphql/internal` patterns exist.
