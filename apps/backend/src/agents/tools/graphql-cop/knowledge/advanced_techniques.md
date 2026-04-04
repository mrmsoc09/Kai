# GraphQL-Cop Advanced Techniques

## Introspection Testing
Introspection = schema exposure = critical. Full schema reveals all fields including sensitive ones.

## Batching Attacks
Send multiple queries in single request. Bypass rate limits. Resource exhaustion vector.

## Field Suggestion
GraphQL auto-complete may suggest hidden fields. Information disclosure.

## Depth Limits
Prevent deeply nested queries for DoS protection. Test if implemented.

## Alias Abuse
Aliases allow sending many queries under single name. Evade rate limiting.

## Circular Queries
Circular dependencies can cause processing overhead. DoS vector.
