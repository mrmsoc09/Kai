# CORSy Overview
CORSy is a tool to test for Cross-Origin Resource Sharing (CORS) misconfigurations. It focuses on arbitrary origin reflection and credential usage.

## Exploitable Configs
- **Access-Control-Allow-Origin: * with Credentials**: Often blocked by browsers but still a misconfig.
- **Origin Reflection**: Backend reflects the `Origin` header in `Access-Control-Allow-Origin`.
- **Null Origin**: `Access-Control-Allow-Origin: null`.
