# GAU — Advanced Techniques

## Basic Run
```bash
gau target.com
```

## Filter to Interesting Extensions
```bash
gau target.com | grep -E "\.(php|asp|aspx|jsp|json|xml|config|bak|sql|log)"
```

## Extract Unique Parameters
```bash
gau target.com | grep "?" | cut -d? -f2 | tr "&" "\n" | cut -d= -f1 | sort -u
```
Produces a list of all parameter names ever seen.

## Scope to Specific Subdomain
```bash
gau --subs api.target.com
```
More focused results for API surfaces.

## Multiple Providers
```bash
gau --providers wayback,otx,commoncrawl,urlscan target.com
```
