K1 Workflows
- Core flow: Targets → OSINT Recon (passive→active) → HTTP Probe → Tech Fingerprint → Nuclei → LLM Triage → Human Validation → Report
- Loops: OODA (observe→orient→decide→act), GPEE (goal→plan→execute→evaluate), Reflection loop to refine next actions
- HiL: decisions at triage/validation/report; never auto-submit


## K1 System Contract
- Loops: GPEE (Goal→Plan→Execute→Evaluate) and OODA (Observe→Orient→Decide→Act) persisted in run records.
- HiL gating: mode=execute requires explicit human approval (hil_approved=true) and policy enabling.
- Evidence gates: No VALIDATED without a screen recording reference in artifacts.
- Policy defaults: test_mode=true, external_queries_enabled=false.
- Artifacts: Each run stores run.json and audit.json (when executed).
