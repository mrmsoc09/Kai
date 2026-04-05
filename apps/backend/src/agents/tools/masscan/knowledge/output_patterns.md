# Masscan Output Patterns

## JSON Structure
Typical records include host IP and a list of open ports:
- `ip`
- `ports[].port`
- `ports[].proto`

## Priority Ports
High-value exposure indicators include:
- `9200` Elasticsearch
- `6379` Redis
- `5601` Kibana
- `9090` Prometheus

## Standard vs Non-Standard
`80/443` are common and lower-priority. Unexpected ports generally deserve immediate enrichment.
