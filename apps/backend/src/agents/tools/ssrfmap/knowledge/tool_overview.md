# SSRFMap Overview
SSRFMap is a tool to automate SSRF vulnerability discovery and exploitation. It includes modules for reading files, exfiltrating cloud metadata, and scanning internal ports.

## Key Features
- **Cloud Metadata Module**: Specifically targets AWS, GCP, and Azure metadata endpoints.
- **Internal Scanning**: Uses SSRF to scan ports in the internal network (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16).
- **Data Exfiltration**: Attempts to read `/etc/passwd` or other sensitive files via SSRF.
