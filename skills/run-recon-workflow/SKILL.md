# run-recon-workflow

Purpose: execute a template-based recon workflow through canonical campaign orchestration.

## Steps

1. Dry-run:
   - `python3 scripts/run_bugbounty_workflow.py --template workflow_recon_surface_map --target example.com --dry-run`
2. Real run:
   - `python3 scripts/run_bugbounty_workflow.py --template workflow_recon_surface_map --target example.com --program-name "Example Program" --initiated-by operator`
3. Monitor:
   - `GET /api/v1/campaigns/{campaign_id}`
   - `POST /api/v1/campaigns/{campaign_id}/schedule`

## Notes

- `safe_mode` blocks intrusive steps.
- workflow state is persisted in canonical campaign entities.
