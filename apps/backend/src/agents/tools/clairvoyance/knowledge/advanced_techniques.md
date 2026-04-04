# Clairvoyance Advanced Techniques

## Wordlist Selection
Generic GraphQL field wordlist from SecLists. Covers common names and sensitive patterns.

## Sensitive Field Targeting
Focus on: password, token, secret, admin, internal, key, private, credential fields.

## Timing
Only runs when Introspection disabled. Otherwise introspection is faster.

## Effective Against
Partially hidden schemas. APIs that hide some fields from introspection.

## Rate Limiting
May trigger rate limits. Use slow mode if needed. Timeouts normal.
