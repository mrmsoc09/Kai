# Nikto Use Cases

## Scenario 1: Outdated Software Discovery
Nikto quickly identifies Apache 2.2.15 (ancient). Feeds version to SearchSploit for CVE matching.

## Scenario 2: Default Credential Testing
Discovers admin panel protected with default credentials (admin/admin123).

## Scenario 3: WAF Evasion Scenario
Target has basic WAF. Nikto evasion mode bypasses signature detection. Finds vulnerabilities other scans miss.

## Scenario 4: Complementary to Nuclei
Nuclei tests known CVE templates. Nikto pattern-based detection finds unknown patterns and configuration issues.

## Scenario 5: Backup File Discovery
Identifies .bak, .old, .tmp files containing sensitive configuration.
