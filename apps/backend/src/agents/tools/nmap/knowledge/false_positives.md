# Nmap False Positives

## Service Banner Ambiguity
Some services obfuscate versions or present proxy banners that map to incorrect product identities.

## Middlebox Interference
Load balancers and WAF/CDN edges can mask backend topology and produce generic signatures.

## Transient Port States
Short-lived containerized services may appear/disappear between scans.

## Mitigation
Correlate nmap findings with application-layer probes and repeated checks before asserting exploitable service exposure.
