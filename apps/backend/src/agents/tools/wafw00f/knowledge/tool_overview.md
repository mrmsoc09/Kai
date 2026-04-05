# Wafw00f

Wafw00f fingerprints web application firewalls by analyzing HTTP response behavior and known detection signatures. In this platform, it is a critical control point that governs downstream active-scan aggressiveness.

## Primary Purpose
Detect WAF presence and vendor hints before intrusive tooling executes.

## Pipeline Role
Acts as a gatekeeper between reconnaissance and active exploitation phases.

## Operational Impact
Detected WAFs reduce rate limits and adjust payload strategy for all downstream scanners.

## Criticality
Incorrect WAF assumptions can cause blocks, noisy telemetry, or missed coverage.
