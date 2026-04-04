# naabu — Advanced Techniques

## Web Ports Only (Fast, BBP-Appropriate)
```bash
naabu -l hosts.txt -p 80,443,8080,8443,3000,4000,5000,8000,8081,8888,9000,9090,9200,9443,6379,5601 -silent
```

## Top 1000 Ports (Thorough)
```bash
naabu -l hosts.txt -top-ports 1000 -silent
```

## Exclude CDN IPs (Faster)
```bash
naabu -l hosts.txt -p 80,443 -exclude-cdn -silent
```

## High Value Non-Standard Ports
| Port | Service |
|------|---------|
| 3000 | Node.js/React dev server |
| 5000 | Flask/development |
| 8080 | Alternative HTTP, often less secured |
| 9090 | Prometheus metrics (often unauthenticated) |
| 9200 | Elasticsearch (often unauthenticated) |
| 6379 | Redis (often unauthenticated) |
| 5601 | Kibana dashboard |
| 27017 | MongoDB |
| 2379 | etcd |
