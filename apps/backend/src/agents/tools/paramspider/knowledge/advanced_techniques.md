# Paramspider Advanced Techniques

## Baseline Command
`paramspider -d target.tld -o paramspider.txt`

## Parameter Extraction
Parse query strings and normalize parameter names to create a unique list independent of exact URL duplicates.

## High-Risk Names
Flag names such as `id`, `file`, `url`, `path`, `redirect`, `callback`, `include`, `fetch` for prioritized testing.

## GF Correlation
Feed extracted URLs into gf category filters to pre-route SQLi/XSS/SSRF candidates before intrusive tooling.
