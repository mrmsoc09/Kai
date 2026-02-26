# Security Policy (K1)

## Scope
- Applies to the local K1 codebase and artifacts.
- Plan-mode only by default; external execution is disabled unless explicitly approved and enabled.

## Safety and Autonomy Gates
- Plan mode is Tier 0 (AUTO).
- Execute mode on external targets is Tier 2 (APPROVE) and requires human-in-the-loop approval.
- Evidence export or sharing is Tier 3 (HARD_STOP).

## Redaction and Logging
- Logs must be redaction-first and avoid raw chain-of-thought.
- Sensitive tokens and secrets must be redacted at ingestion.
- Audit logs are append-only and stored locally under artifacts/.

## External Calls
- External network calls are disabled by default (configs/policies.yaml).
- No external scans or data exfiltration without explicit user approval and scope confirmation.

## Reporting
- Report security issues privately to the project owner.
- Include reproducible steps and affected components.
