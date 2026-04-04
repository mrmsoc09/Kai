# OWASP-ZAP False Positives

## SSTI Confusion
Server-side template injection tests may trigger on legitimate template output.

## Error-Based SQLi
Application error messages falsely indicate SQLi when they're just formatting.

## WAF Evasion
WAF blocking scanner may appear as vulnerability in results.

## Encoding Mismatches
Different character encodings may cause detection errors.

## Mitigation
Manual verification of high-confidence findings. Use confidence levels to filter.
