# GraphQL-Cop Use Cases

## Scenario 1: API Security Assessment
GraphQL endpoint discovered by Katana. GraphQL-Cop tests standard vulnerabilities.

## Scenario 2: Introspection Exposure
Introspection enabled = full schema exposure. Critical finding.

## Scenario 3: Rate Limit Bypass
Batching allows sending 100 queries as 1 request. Evades per-query rate limit.

## Scenario 4: Schema Recovery Path
Introspection disabled? Clairvoyance runs for wordlist-based schema recovery.

## Scenario 5: Multi-Query Attack
Alias abuse + circular queries = DoS vector.
