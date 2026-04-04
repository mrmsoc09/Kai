# Ahmia-Client Advanced Techniques

## Why Ahmia Over Tor Tools
- No Tor service required (clearnet HTTP)
- Fast query responses (seconds vs minutes)
- Indexed content only (not live crawling)
- Complements other tools with unique index

## Query Types
- Organization: "companyname"
- Breach data: "companyname leaked"
- Credential terms: "companyname password"
- Database exports: "database dump companyname"

## Index Coverage
Ahmia covers Tor2Web mirrors and selected .onion sites. Partial coverage vs. complete dark web. Use alongside other tools.

## Response Format
HTML results with .onion link references. Parse for target mentions and URLs for further investigation.
