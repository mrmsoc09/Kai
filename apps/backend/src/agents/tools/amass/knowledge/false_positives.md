# Amass — False Positives

## Out-of-Scope Domains from ASN Enumeration
Amass may return out-of-scope domains when doing ASN enumeration — the ASN may serve multiple organizations. Always verify scope before adding ASN-discovered domains to the target list.

## DNS Brute Force Verification
DNS brute force results should be verified with dnsx before being treated as confirmed subdomains. Not all brute-forced names will have DNS records.
