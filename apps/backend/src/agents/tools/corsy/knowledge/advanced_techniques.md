# Corsy — Advanced Techniques

## Basic Scan Against All Live Hosts
```bash
corsy -u https://target.com
```

## With Authentication (Reveals More Issues)
```bash
corsy -u https://api.target.com -H "Cookie: session=abc123"
```
Authenticated endpoints often have misconfigured CORS that unauthenticated scans miss.

## Custom Origin Testing
```bash
corsy -u https://target.com -H "Origin: https://attacker.com"
```

## With Thread Count
```bash
corsy -u https://target.com -t 10
```

## API Endpoints Specifically
APIs have higher rate of CORS misconfiguration than web UIs. Run against API base URLs separately:
```bash
corsy -u https://api.target.com
corsy -u https://api.target.com/v1
corsy -u https://api.target.com/v2
```
