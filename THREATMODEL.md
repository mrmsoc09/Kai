# Threat Model (K1)

## Overview
K1 is a plan-mode security research tool with policy gates for external execution.
This threat model focuses on policy enforcement, logging redaction, and evidence integrity.

## Assets
- Policy configuration (configs/policies.yaml)
- Logs and audit trails (artifacts/logs)
- Evidence artifacts (artifacts/evidence)
- Run records (artifacts/dork_runs)

## Assumptions
- Default operation is plan mode (no external queries).
- Human approval is required for execute mode on external targets.
- Local environment is trusted for development and testing.

## Threats and Mitigations
- Unauthorized execute-mode requests
  - Mitigation: HiL approval required; policy gate blocks by default.
- Secrets leaking into logs
  - Mitigation: redaction patterns in configs/knowledge.yaml; redaction in trace logging.
- Evidence tampering after finalization
  - Mitigation: immutable finalize gate; update endpoint blocks finalized artifacts.
- Over-broad CORS or auth misconfiguration
  - Mitigation: authenticated routes for sensitive data; document safe defaults.

## Residual Risks
- Misconfigured policy files could allow external calls.
- Redaction patterns may miss novel secrets.
- Local file permissions may be too permissive in shared environments.

## Next Steps
- Add negative tests for policy gates and redaction.
- Add periodic retention policies for logs and artifacts.
- Add optional SAST/secret scanning locally.
