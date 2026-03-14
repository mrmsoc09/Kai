# Workflow Graph Memory

Canonical stage sequence:

1. target intake
2. scope validation
3. passive recon
4. active recon
5. live host validation
6. web crawling
7. endpoint discovery
8. parameter discovery
9. vuln scan
10. secret scan
11. tech fingerprint
12. prioritization and correlation
13. report prep

Current template entrypoint:

- `apps/backend/src/core/bugbounty_workflow_engine.py`

Minimum implemented templates:

- `workflow_recon_surface_map`
- `workflow_web_attack_surface`
- `workflow_quick_vuln_sweep`
- `workflow_secret_exposure_scan`
- `workflow_priority_target_ranking`

Execution rules:

- stage dependency ordering is explicit
- safe mode and scope checks gate execution
- workflow output artifacts are generated even when some tools fail
