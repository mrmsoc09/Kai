# GraphQL-Cop Output Patterns

## Security Test Failures
- Introspection enabled
- Batching allowed
- Depth limits not enforced
- Alias abuse possible
- Circular queries allowed

## Severity
Each positive test = medium to high severity depending on vector.

## Handoff to Clairvoyance
If introspection disabled, Clairvoyance runs for schema recovery.
