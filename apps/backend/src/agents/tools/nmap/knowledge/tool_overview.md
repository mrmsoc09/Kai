# Nmap

Nmap is a service discovery and version fingerprinting standard. In this workflow it is used after initial host/port discovery to identify exposed services and collect version strings for vulnerability correlation.

## Primary Purpose
Map open ports to service identities and versions for exploitability triage.

## BBP-Focused Profile
The configured profile emphasizes common web and app-adjacent ports to balance depth, speed, and safety.

## Output Artifacts
XML output is generated for structured post-processing, while plaintext output can be parsed for quick findings.

## Pipeline Role
Consumes prioritized targets from earlier phases and forwards version intelligence to nuclei/searchsploit.
