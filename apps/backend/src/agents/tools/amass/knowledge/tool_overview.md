# Amass — Tool Overview

Amass performs in-depth subdomain enumeration using a different set of sources than subfinder. It performs DNS brute forcing, certificate transparency, search engine scraping, and passive DNS lookups.

## CLI Syntax Note
**Amass v5.0.0 changed CLI syntax significantly.**
- Correct v5 syntax: `amass enum -d target.com`
- Old v3/v4 syntax (deprecated): `amass enum -passive -d target.com`
Always verify version before running.

## Output Format
One subdomain per line in default mode. JSON available with `-json` flag.

## What Amass Finds That Subfinder Misses
- DNS brute force results
- WHOIS-related domains
- ASN enumeration finds related company infrastructure

## Pipeline Role
Phase 1 parallel to subfinder. Results combined and deduplicated before dnsx.
