# httpx — Advanced Techniques

## Basic Probe with Tech Detection
```bash
httpx -l hosts.txt -silent -status-code -title -tech-detect -follow-redirects -json
```

## Web Server Identification
```bash
httpx -l hosts.txt -web-server -silent
```

## Filter by Response Codes
```bash
httpx -l hosts.txt -mc 200,201,204,301,302,401,403 -silent -json
```
401/403 on interesting subdomains = something exists behind auth — high value target.

## CDN Detection
```bash
httpx -l hosts.txt -cdn -silent
```
Identifies CDN-served hosts for deprioritization.

## Screenshot Capture
```bash
httpx -l hosts.txt -screenshot -silent
```
