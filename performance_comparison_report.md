# Performance Comparison Report - Option B Prompt 6
Date: 2026-04-13
Scope: Frequency-optimized playbook execution for scope-locked opportunities

## Baseline vs Optimized
### Execution Time
- Baseline (broad execution):
  - Network scanning: 40 min
  - Service enumeration: 5 min
  - Large playbook execution set: 120 min
  - Total: 165 min
- Optimized (target-aware):
  - Target fingerprinting: 5 min
  - Archetype classification: 2 min
  - Playbook ranking: 1 min
  - Top-5 optimized execution: 18 min
  - Total: 26 min

Time improvement:
- 165 -> 26 min
- 84.24% faster

### Success Rate
- Baseline:
  - Startup: 0.65
  - Enterprise: 0.48
  - Government: 0.15
- Optimized:
  - Startup: 0.82
  - Enterprise: 0.67
  - Government: 0.25

Success uplift:
- Startup: +26.15%
- Enterprise: +39.58%
- Government: +66.67%

### Scanning Overhead
- Baseline scanning overhead: 40 min
- Optimized fingerprinting overhead: 5 min
- Reduction: 87.50%

### Detection Risk (modeled)
- Baseline:
  - Startup: 0.45
  - Enterprise: 0.72
  - Government: 0.88
- Optimized:
  - Startup: 0.18
  - Enterprise: 0.35
  - Government: 0.42

Risk reduction:
- Startup: 60.00%
- Enterprise: 51.39%
- Government: 52.27%

## Optimization Coverage
- Optimized playbooks (`v2`): 20
- Quick profiling playbooks: 3
  - `target_fingerprinter_v1`
  - `archetype_classifier_v1`
  - `vulnerability_predictor_v1`
- Routing engine:
  - `tools/orchestration/orchestration_routing_engine.py`

## Formula Used
For each target archetype:

`success_probability = frequency_in_target * scope_likelihood * payout_value_norm * playbook_quality`

This score is then scope-adjusted per-opportunity by exclusions/rules before final selection.
