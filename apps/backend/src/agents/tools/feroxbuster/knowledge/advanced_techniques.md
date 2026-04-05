# Feroxbuster Advanced Techniques

## Baseline Run
Use raft-medium for balanced breadth and speed:
`feroxbuster --url https://target.tld --wordlist raft-medium-directories.txt --json --silent`

## WAF-Aware Throttling
Use low thread/rate settings when WAF is detected (for example `--threads 5 --rate-limit 2`) versus normal high-throughput mode (`--threads 20`).

## Extension Targeting
For deeper file discovery on high-value targets:
`-x php,asp,json,bak,zip`

## Recursion Trade-Off
`--no-recursion` keeps scan blast radius predictable. Enable recursion only for targeted scopes where deeper depth is justified.

## Wildcard Filtering
Use content-length clustering or `--filter-size` to remove wildcard-routed false positives.
