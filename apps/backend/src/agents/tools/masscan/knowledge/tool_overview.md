# Masscan

Masscan is a high-speed port scanner used to quickly identify exposed network services across target hosts. In this pipeline it provides broad, fast coverage before deeper service fingerprinting with nmap.

## Primary Purpose
Rapidly map open ports for prioritized follow-up.

## Runtime Profile
Configured with conservative rate settings (`--rate 1000`) to balance speed and operational safety in autonomous runs.

## Output
JSON output is used for deterministic parsing and machine-to-machine handoff.

## Pipeline Role
Masscan discovers open ports; nmap then enriches those ports with service/version detail.
