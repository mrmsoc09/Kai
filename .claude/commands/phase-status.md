Use the orchestrator subagent to produce a current build status report.

Read docs/build_status.md if it exists.
Read docs/HANDOFF.md if it exists.
Inspect the repo to verify claimed completions.

Report must cover:
- Which phases are COMPLETE (with deliverables confirmed)
- Which phases are IN_PROGRESS (with current step)
- Which phases are BLOCKED (with exact blocker)
- Which phases are PENDING (with dependencies not yet met)
- Any broken imports, failed tests, or unresolved stubs found
- Next recommended action with specific command to run

Update docs/build_status.md with the current report.
