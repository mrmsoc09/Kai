# httpx — Use Cases

## Primary Pipeline Use
```bash
httpx -l dnsx_resolved.txt -silent -status-code -title -tech-detect -follow-redirects -json -o httpx_output.json
```

## Extract Live Hosts
```bash
cat httpx_output.json | jq -r '.url' > live_hosts.txt
```

## Find Auth-Blocked Interesting Targets
```bash
httpx -l hosts.txt -mc 401,403 -silent | grep -E "admin|api|internal|portal"
```
