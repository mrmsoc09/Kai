# dnsx — Use Cases

## Primary Use Case
Always run after subfinder+amass, before httpx.

```bash
# Combine and deduplicate subfinder + amass output
cat subfinder_out.txt amass_out.txt | sort -u > all_subdomains.txt

# Resolve with CNAME detection
dnsx -l all_subdomains.txt -silent -a -resp -cname -json -o resolved.json
```

## Takeover Hunting
```bash
dnsx -l all_subdomains.txt -cname -silent | grep -E "github.io|amazonaws.com|azurewebsites.net|heroku"
```

## Large Lists with Wildcard Filtering
```bash
dnsx -l all_subdomains.txt -wd target.com -a -silent
```
