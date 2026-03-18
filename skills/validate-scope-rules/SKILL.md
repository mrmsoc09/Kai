---
name: validate-scope-rules
description: Skill for validate-scope-rules
---

# validate-scope-rules

Purpose: verify scope enforcement policy before executing workflows.

## Procedure

1. Review policy file.
   - `config/scope_guardrails.yaml`
2. Validate representative targets.
   - in-scope domain
   - denied domain
   - wildcard child domain
   - localhost/internal/cidr cases
3. Run automated tests.
   - `python3 -m pytest -q tests/test_scope_guardrails.py`
4. Confirm audit log emission.
   - check `output/logs/scope_decisions.jsonl`
5. Verify safe mode handling for intrusive/manual tools.

## Rules

- denylist must always take precedence
- strict allowlist mode must reject unknown targets
- no out-of-scope execution should proceed to tool dispatch
