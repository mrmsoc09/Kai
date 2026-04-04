# Smuggler Use Cases

## Scenario 1: Proxy-Backend Desynchronization
Different proxy vs backend interpretations of headers enable request smuggling. High-impact if confirmed.

## Scenario 2: HTTP/2 Downgrade Attacks
Smuggling can facilitate HTTP/2 downgrade and header injection. Combined attack vector.

## Scenario 3: Cache Poisoning
Smuggled requests may poison intermediary cache. Affects all downstream users.

## Scenario 4: Session Hijacking
Inject requests into another user's session stream via smuggling.

## Scenario 5: Manual Validation Required
Positive smuggler result requires expert manual testing before reporting. Not auto-confirmed.
