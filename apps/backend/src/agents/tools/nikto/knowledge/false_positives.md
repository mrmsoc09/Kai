# Nikto False Positives

## Common Misidentifications
1. **Version Detection Errors**: Reported version doesn't match actual
2. **False Default Creds**: Credentials don't actually work
3. **Expired OSVDB IDs**: Database entries for patched vulnerabilities
4. **Configuration False Alarms**: Intentional settings flagged as misconfig

## Verification
Manually verify default credentials. Check if reported version exists. Cross-reference OSVDB with modern CVE databases.
