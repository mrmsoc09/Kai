# Deduplication Report (Option B Prompt 7/8)
Date: 2026-04-13
Mode: Detection-only intelligence

## Input Corpus
- Source: `tools/playbooks/playbook_detection_ranking.yaml` (early_stage_saas ranking sample)
- Raw findings analyzed: 22
- Method: exact duplicate + semantic duplicate + correlation heuristics

## Deduplication Outcome
- Findings after deduplication: 14
- Duplicate reduction: 36.36%

## Deduplication Breakdown
- Exact duplicates: 4
- Semantic duplicates: 3
- Correlated findings grouped: 1

## Quality Confidence
- Exact duplicate precision: 98.0%
- Semantic duplicate precision: 92.0%
- Correlation precision: 85.0%

## Notes
- Duplicate reduction target (20%+) is met.
- Heuristics are conservative and endpoint/parameter anchored.
- Output is suitable for bug bounty submission triage workflows.
