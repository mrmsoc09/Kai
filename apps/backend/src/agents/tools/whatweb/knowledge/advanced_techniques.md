# WhatWeb Advanced Techniques

## Passive-Friendly Command
```bash
whatweb --log-json=whatweb.json --aggression 1 target.com
```

## Aggression Discipline
Higher aggression increases request volume and detection depth but also increases operational noise. Keep level 1 for default autonomous runs.

## Template Routing
Map detected stack tokens (for example Spring, WordPress, Apache) into targeted nuclei template families.

## Version Correlation
Preserve version strings to support CVE-specific prioritization and exploit research.
