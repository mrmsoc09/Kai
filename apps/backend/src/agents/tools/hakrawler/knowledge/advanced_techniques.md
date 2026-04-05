# Hakrawler Advanced Techniques

## Baseline Command
`hakrawler -url https://target.tld -depth 3 -plain`

## Scope Hygiene
Filter external domains aggressively before handoff to avoid out-of-scope drift and unnecessary scan spend.

## Form Discovery
Track form actions and auth-related routes for follow-up injection testing queues.

## Engine Complement
Use hakrawler for fast first-pass link extraction, then katana for deeper JS-aware traversal.
