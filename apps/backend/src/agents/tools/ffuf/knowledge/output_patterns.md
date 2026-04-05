# FFUF Output Patterns

## JSON Result Fields
Useful fields include URL, status, response length, word count, and line count.

## High-Signal Indicators
- Protected endpoints (`401/403`)
- Uncommon status behavior
- Distinct content-length responses

## Wildcard Pattern
If many candidates cluster on identical response lengths and behavior, treat as probable wildcard responses.
