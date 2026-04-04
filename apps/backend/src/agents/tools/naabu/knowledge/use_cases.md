# naabu — Use Cases

## Standard BBP Port Scan
```bash
naabu -l live_hosts.txt -p 80,443,8080,8443,3000,5000,8000,8888,9000,9090,9200,6379,5601 -silent -o open_ports.txt
```

## Quick Web + High Value Services
Run after httpx. Feed results to nmap for service version detection. Non-standard open ports are high priority for active scanning.
