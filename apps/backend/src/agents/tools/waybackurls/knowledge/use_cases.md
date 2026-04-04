# waybackurls — Use Cases

## Primary Use Case
Run parallel with gau. Combine outputs and deduplicate.

```bash
# Run both in parallel
gau target.com > gau_urls.txt &
echo target.com | waybackurls > wayback_urls.txt &
wait

# Combine and deduplicate
cat gau_urls.txt wayback_urls.txt | sort -u > all_urls.txt
```

Combined URL list feeds paramspider and arjun in Phase 3.

## Legacy Endpoint Discovery
```bash
waybackurls -dates target.com | grep "^201[0-9]" | cut -d' ' -f2 | sort -u
```
Isolates URLs first archived between 2010-2019 for legacy endpoint research.
