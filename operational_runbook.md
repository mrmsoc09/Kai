# Operational Runbook - Option B Detection Workflow
Date: 2026-04-13

## Run Sequence
1. Load active opportunity scope from platform (H1/Bugcrowd/Intigriti/direct).
2. Construct `OpportunityScope` with authorization and freshness metadata.
3. Initialize orchestrator:
   - `BugBountyAutomationOrchestrator(opportunity_scope=..., opportunity_metadata=...)`
4. Execute workflow:
   - `run_complete_workflow()`
5. Review outputs:
   - `submission_ready_report`
   - `workflow_metrics`
   - `validation_log`
6. Submit deduplicated and enriched findings to platform workflow.

## Governance Controls
- Never bypass scope validation phase.
- Never run with non-detection playbooks in Option B mode.
- Keep findings non-destructive; evidence must be safe PoC signals only.
- Re-run scope load if opportunity metadata changes.

## Operational Cadence
- Per opportunity: execute once per authorized scan cycle.
- Monthly: refresh frequency/ranking artifacts and recalibrate severity multipliers.
- Quarterly: benchmark and drift check against payout outcomes.
