# Hakrawler False Positives

## External Link Leakage
Crawls often include external documentation, CDN, or social links that are out of scope.

## Marketing/Static Endpoints
Brand pages and static resources can inflate URL counts without security value.

## Duplicate Navigation Paths
Navigation templates can cause repeated links across many pages.

## Mitigation
Normalize URLs, filter by scope host, and remove static suffixes before downstream injection routing.
