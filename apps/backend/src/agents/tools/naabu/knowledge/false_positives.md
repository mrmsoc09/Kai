# naabu — False Positives

## CDN Port Confusion
CDN hosts show many ports open — these are CDN infrastructure ports, not application ports. Use `-exclude-cdn` to skip them.

## Firewall Filtered Ports
Some firewalls return RST instead of dropping packets. Verify with direct service probe before reporting.
