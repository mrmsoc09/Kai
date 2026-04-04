# naabu — Output Patterns

## HIGH SIGNAL
- Port 9200 open → Elasticsearch, often accessible without auth
- Port 6379 open → Redis, often accessible without auth
- Port 5601 open → Kibana dashboard
- Port 8080/8443 alongside 80/443 → dev server exposed alongside prod
- Port 9090 → Prometheus metrics endpoint (unauthenticated)

## NOISE
- Port 80/443 only → standard web, already covered by httpx
- CDN hosts with many ports → CDN infrastructure, not app ports
