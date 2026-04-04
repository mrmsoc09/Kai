# GAU (GetAllUrls) — Tool Overview

GAU fetches known URLs for a domain from multiple sources: Wayback Machine, OTX, Common Crawl, URLScan. It collects historical URL data without making requests to the target.

## Output Format
One URL per line.

## Key Value
Finds old endpoints, parameters, and paths that may no longer be in the sitemap but still function on the backend. Old functionality often has weaker security than new code.

## Timeout Note
**Wayback Machine queries for large domains can take 10-15 minutes.**
The timeout is set to 900s. The previous 240s timeout caused 81% of runs to fail.

## Pipeline Role
Phase 2 URL discovery. Run after subfinder/dnsx phase. Output feeds paramspider and arjun.
