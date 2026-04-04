# Smuggler Output Patterns

## Variant Detection
- TE.CL: Server prioritizes Transfer-Encoding over Content-Length
- CL.TE: Server prioritizes Content-Length over Transfer-Encoding

## Confidence Levels
0.7 confidence typical. Requires manual validation. Different proxy/WAF combos may behave differently.

## Inconclusive Results
Timeout or no response: Inconclusive. Not necessarily vulnerable.
