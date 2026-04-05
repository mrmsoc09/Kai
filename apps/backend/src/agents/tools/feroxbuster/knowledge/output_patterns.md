# Feroxbuster Output Patterns

## High-Signal Paths
- `/admin/`
- `/api/`
- `/backup/`
- `/.git/`
- `/swagger/`
- `/actuator/`
- `/graphql`

## Status Code Interpretation
- `200`: directly accessible endpoint
- `401/403`: endpoint exists and is protected (often high value)
- `302`: redirected endpoint, follow chain

## Wildcard Indicator
When many different paths return the same content-length and similar metadata, suspect wildcard or generic error routing.
