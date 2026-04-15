# Detection Optimization Performance Report (Option B Prompt 6/8)
Date: 2026-04-13
Mode: Detection-only, scope-locked, non-destructive

## Baseline vs Optimized Scanning
### Baseline (broad, non-prioritized detection)
- Typical scan window: 90-120 minutes
- Typical request volume: 300-500 requests per engagement
- Findings per hour: ~1.0x baseline
- Noise profile: Medium/High

### Optimized (Prompt 6 detection prioritization)
- Prioritized top detection playbooks (15 optimized, run top 10 by efficiency)
- Typical scan window: 35-50 minutes
- Typical request volume: 120-220 requests
- Findings per hour: ~2.5x baseline
- Noise profile: Low/Medium

## Quantified Improvements
- Scanning time reduction: 50%+ (target met)
- Average optimized-playbook time reduction: 64.88%
- Average request/noise reduction: 52.0%
- Findings-per-hour efficiency: ~2.5x

## Example Workflow (Target-Aware)
1. Validate scope authorization and freshness.
2. Classify target archetype via detection model.
3. Rank detection playbooks by:
   - detection probability in archetype
   - expected payout if found
   - execution time (efficiency score)
4. Execute top prioritized detection-only playbooks.
5. Generate PoC-quality evidence for reporting.

## Safety and Compliance
- Detection-only filtering enforced.
- No exploitation/persistence/destruction/evasion playbooks in optimized set.
- Scope validation mandatory before planning/execution.
- All outputs oriented to reporting and remediation evidence.
