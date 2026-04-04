# Amass — Use Cases

## Scenario 1: Maximum Coverage First Scan
```bash
amass enum -d target.com -passive -o output.txt
```
Then: `amass intel -org "Company Name"` for ASN enumeration.

## Scenario 2: Quick Supplemental Scan
```bash
amass enum -passive -d target.com
```
Run parallel with subfinder, deduplicate results with `sort -u`.

## Scenario 3: Corporate Infrastructure Mapping
```bash
amass intel -org "Company Name"
amass enum -asn AS12345 -o asn_results.txt
```
Combine with main target results for complete picture.
