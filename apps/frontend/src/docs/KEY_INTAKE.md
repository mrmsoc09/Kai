# Provider Key Intake & Selection (User-Managed)

Goal: Let users selectively enable data sources and securely store credentials in Vault (KV v2). No keys in code or DB.

Artifacts:
- Registry: k1/configs/provider_registry.yaml (providers grouped by market with docs and signup links)
- Vault paths:
  - secret/data/osint/{provider_id} — key/token and metadata
  - secret/data/osint_selections/{market} — list of selected provider ids

API (FastAPI):
- GET  /providers/catalog?market=healthcare|finance|ecommerce|government_contracts_grants|supply_chain
- GET  /providers/selection?market=...
- POST /providers/selection (admin) { market, selected_ids: [] }
- POST /providers/{id}/key (admin) { api_key|token|client_id|client_secret, rate_limit?, tos_version?, notes? }

UI Suggestions:
- Checkbox list per market. Each provider shows: name, docs link, signup link, quota, rate_limit, PII flags.
- Key entry modal (never echo back the secret). After save, show a green check that Vault has a record (metadata only).
- Per-scan advanced options: toggle use of selections; override to add/remove providers for the current run.

Security:
- RBAC required: MANAGE_CONFIG to write keys or selections.
- Keys are never returned via API; only presence metadata is displayed.
- Rotation: allow overwrite; keep audit trail in separate immutable log.

Validation:
- Optional: add a background job to test connectivity with provider; requires user consent due to potential outbound calls.
