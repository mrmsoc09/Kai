# waybackurls — Advanced Techniques

## Basic Run
```bash
echo target.com | waybackurls
```

## With Dates (Find Old Content)
```bash
waybackurls -dates target.com
```
Shows when each URL was first archived. Old URLs (2015-2018) often have legacy endpoints.

## Filter Interesting Files
```bash
echo target.com | waybackurls | grep -E "\.(js|json|xml|php|bak|config)$"
```

## Combine with GAU
```bash
gau target.com > gau_urls.txt
echo target.com | waybackurls > wayback_urls.txt
cat gau_urls.txt wayback_urls.txt | sort -u > all_urls.txt
```
