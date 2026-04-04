# Nikto Advanced Techniques

## Tuning Flags
-Tuning codes select test categories. 1=Apache, 2=CGI, 3=IIS, 4=Tests, 5=Info, 6=Injection, 9=Misc. Combine for selective scanning.

## WAF Evasion
Evasion mode (-evasion 1) randomizes requests and reduces detection signatures. Use when WAF detected.

## Default Credentials
High-value finding. Tests common default admin credentials per software version.

## Version Disclosure
Software version detection feeds into SearchSploit for CVE matching.

## Output Mapping
OSVDB IDs map to severity. Modern CVEs may not have OSVDB equivalents.
