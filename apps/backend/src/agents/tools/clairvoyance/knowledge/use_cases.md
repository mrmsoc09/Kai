# Clairvoyance Use Cases

## Scenario 1: Introspection Disabled
API intentionally hides schema. Clairvoyance discovers field names via fuzzing.

## Scenario 2: Admin Field Discovery
Wordlist includes "admin". Discovers admin_panel, adminUsers, admin_token fields.

## Scenario 3: Password Field Recovery
Common pattern: password field may be hidden. Clairvoyance finds it.

## Scenario 4: Type Exploration
Discovers types like "User", "Admin", "InternalConfig" not in public schema.

## Scenario 5: Combined with GraphQL-Cop
GraphQL-Cop says introspection disabled. Clairvoyance recovers what was hidden.
