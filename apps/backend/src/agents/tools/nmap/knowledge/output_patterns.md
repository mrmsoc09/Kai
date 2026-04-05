# Nmap Output Patterns

## High-Value Non-Standard Ports
- `9200` (Elasticsearch)
- `6379` (Redis)
- `5601` (Kibana)
- `27017` (MongoDB)
- `9090` (Prometheus)

These frequently expose sensitive data or admin functionality when misconfigured.

## Standard Web Ports
`80` and `443` are usually expected; they are useful but lower-priority compared to unexpected exposed services.

## Version Signal
Precise version strings unlock CVE-specific follow-up and reduce noisy template execution.
