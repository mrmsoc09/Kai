# Github-Subdomains

Github-Subdomains discovers hostnames leaked in public source code, configuration files, and infrastructure-as-code repositories. It surfaces internal or pre-production assets that may never appear in certificate transparency sources.

## Primary Purpose
Extract subdomain intelligence from code search signals.

## Authentication
`GITHUB_TOKEN` is strongly recommended. Tokened requests support roughly 5000 requests/hour vs 60 requests/hour unauthenticated.

## Pipeline Role
Runs during passive recon and can trigger secret-scanning follow-up on repositories that exposed candidate domains.

## Distinct Value
Frequently finds internal naming patterns and service endpoints missed by CT-focused tools.
