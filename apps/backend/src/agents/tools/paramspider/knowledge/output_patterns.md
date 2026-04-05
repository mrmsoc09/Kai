# Paramspider Output Patterns

## Typical Output
One parameterized URL per line, often with historical variants and alternate host/path combinations.

## Signal Heuristics
- Sensitive file/path parameters
- Redirect/callback style parameters
- API query endpoints carrying IDs or tokens

## Normalization Rule
Deduplicate by sorted parameter-name set, not full URL string, to reduce archive-induced repetition.
