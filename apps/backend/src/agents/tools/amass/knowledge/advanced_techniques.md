# Amass — Advanced Techniques

## Passive Only (Safe for All Programs)
```bash
amass enum -passive -d target.com
```

## Active Enumeration (Verify Program Allows)
```bash
amass enum -d target.com -brute
```
Adds DNS brute force — finds more but slower.

## ASN Enumeration (Finds Related Infrastructure)
```bash
amass intel -org "Target Company Name"
```
Returns ASN numbers for the organization. Then:
```bash
amass enum -asn AS12345
```
Finds all domains registered to that ASN.

## With Config File for API Keys
```bash
amass enum -d target.com -config config.yaml
```
Config includes API keys for Shodan, Censys, etc.
