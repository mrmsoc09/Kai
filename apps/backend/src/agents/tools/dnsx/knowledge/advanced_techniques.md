# dnsx — Advanced Techniques

## Basic Resolution
```bash
dnsx -l subdomains.txt -silent -a -resp
```

## Find Subdomain Takeover Candidates
```bash
dnsx -l subdomains.txt -cname -silent
```
Look for CNAMEs pointing to:
- `github.io`
- `s3.amazonaws.com`
- `azurewebsites.net`
- `herokudns.com`, `herokuapp.com`
- `ghost.io`, `fastly.net`, `surge.sh`
- `netlify.com`, `vercel.app`

## Wildcard Detection
```bash
dnsx -l subdomains.txt -wd target.com
```
Automatically filters wildcard DNS responses.

## Multiple Record Types
```bash
dnsx -l subdomains.txt -a -aaaa -cname -mx -ns
```
