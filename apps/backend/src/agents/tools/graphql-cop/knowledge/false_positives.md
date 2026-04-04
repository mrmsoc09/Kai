# GraphQL-Cop False Positives

## Intentional Design
Some APIs intentionally allow introspection for developer experience. Document as accepted risk.

## Rate Limit Considerations
Batching may be rate limited indirectly via other mechanisms.

## Depth Enforcement
May be enforced at resolver level, not detected by simple testing.
