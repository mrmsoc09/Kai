---
name: debug-tool-wrapper
description: Skill for debug-tool-wrapper
---

# debug-tool-wrapper

Purpose: diagnose wrapper failures quickly and deterministically.

## Procedure

1. Reproduce with minimal command.
   - run wrapper test first
   - then run one local workflow stage against a safe target
2. Inspect execution record fields.
   - command args
   - stdout/stderr
   - exit code
   - timeout/retry metadata
3. Validate installation source.
   - `python3 scripts/verify_tool_registry_install.py`
4. Validate wrapper parameter mapping.
   - confirm required params are present (`target/domain/host/url`)
5. Validate parse mode.
   - `lines`, `jsonl`, `json_or_lines`, `nmap_xml`
6. Add regression test before merging fix.

## Common Root Causes

- wrong binary on PATH (name conflict)
- incompatible CLI flags
- unhandled output format shift
- scope/authorization gate rejection
