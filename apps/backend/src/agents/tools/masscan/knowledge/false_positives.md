# Masscan False Positives

## Packet Loss and Timing
Aggressive timing can produce inconsistent host/port visibility.

## Network Filtering Artifacts
IDS/IPS or cloud edge controls can yield partial/blocked visibility.

## Stateless Nature
Masscan does not perform full service negotiation; open-port indication should be validated by nmap.

## Practical Guardrail
Treat masscan as discovery telemetry, not final service attribution.
