# Subfinder — Advanced Techniques

## Default Run
```bash
subfinder -d target.com -silent
```

## Maximum Coverage
```bash
subfinder -d target.com -all -recursive -silent
```
- `-all` enables all sources including slower ones
- `-recursive` follows discovered subdomains as new targets

## API-Heavy Programs
```bash
subfinder -d target.com -silent -sources certspotter,crtsh,chaos,github,shodan
```

## Large Well-Known Programs
```bash
subfinder -d target.com -all -t 100 -timeout 30
```

## Rate Limiting
- `-t` controls threads (default 10)
- Reduce to `-t 5` if seeing empty results (may be rate-limited at source)

## Combining With Other Tools
Always run alongside amass in parallel. Deduplicate with `sort -u` before passing to dnsx. Combined output finds 30-40% more than any single tool.

## API Keys
Sources like GitHub, Shodan, Censys require API keys in `~/.config/subfinder/config.yaml`.
