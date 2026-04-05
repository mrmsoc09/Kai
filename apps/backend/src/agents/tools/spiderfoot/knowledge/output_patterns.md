# SpiderFoot Output Patterns

## High-Impact Data Types
- `CREDENTIAL_COMPROMISED`
- `PASSWORD_COMPROMISED`
- `EMAILADDR_COMPROMISED`
- `LEAKED_INFO`
- `VULNERABILITY_CVE_*`
- `DARKWEB_MENTION`

## Metadata Fields
Record source module, data type, and value provenance to support downstream validation.

## Response Policy
Credential-related findings are treated as critical evidence and routed for immediate analyst escalation.
