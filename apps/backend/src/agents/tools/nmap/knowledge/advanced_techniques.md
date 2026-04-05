# Nmap Advanced Techniques

## Version Detection Profile
```bash
nmap -sV --open -p 80,443,8080,8443,... -oX nmap_output.xml target.com
```

## Targeted Input Mode
If masscan has already identified open ports/hosts, use list input mode to avoid redundant probing and accelerate service fingerprinting.

## Timeout Guardrails
Host and script timeouts reduce hangs and keep autonomous flows deterministic.

## CVE Pipeline Integration
Normalize service/version strings and hand them to searchsploit and template selectors for focused scanning.
