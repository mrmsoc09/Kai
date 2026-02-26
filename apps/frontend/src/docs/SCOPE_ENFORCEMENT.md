# Scope Enforcement

- Policy table: program_scopes (allowed/excluded assets & domains, min_severity)
- Enforcement: occurs at HiL approval; violations return 403 and block approval.
- API:
  - GET  /scopes/{program}
  - POST /scopes/{program} (admin)
- Matching: substring contains check for assets/domains; severity threshold enforced (INFO<LOW<MEDIUM<HIGH<CRITICAL).
- Recommendation: Use specific domain strings (e.g., ".example.com") to reduce false matches.
