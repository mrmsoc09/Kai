# SearchSploit Advanced Techniques

## Input Format
Version strings from nmap/whatweb (e.g., "Apache 2.2.15"). SearchSploit queries offline database.

## Severity Mapping
RCE = critical. Privilege escalation = high. SQLi = high. Auth bypass = high. XSS = medium. DoS = low/noise for BBP.

## CVE to Template
Map SearchSploit CVE IDs to Nuclei templates for automated validation.

## Accuracy
ExploitDB has known false positives. Different sources report different severity. Cross-reference.

## Never Execute
SearchSploit returns exploit code references. NEVER download or execute. Lookup and validation only.
