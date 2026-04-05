# Wafw00f False Positives

## CDN and Reverse Proxy Confusion
Edge behavior can resemble WAF signatures even when no dedicated WAF is deployed.

## Rate-Limit-Only Defenses
Some applications enforce strict rate limiting without full WAF features, creating ambiguous fingerprinting.

## Path-Dependent Detection
Different paths may trigger different middleware stacks.

## Mitigation
Correlate with repeated checks and passive fingerprinting before finalizing downstream aggression profile.
