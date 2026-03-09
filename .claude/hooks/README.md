# KAI Claude Code Hooks

Hook scripts validated here before activation in settings.json.
Test every script standalone before wiring into settings.

---

## Planned Hooks

### append_audit_log.sh
Trigger: PostToolUse → Write|Edit|MultiEdit
Action: Append structured entry to docs/audit_log.md
Format: timestamp | file | action | session_id

### run_tests_after_backend_edit.sh
Trigger: PostToolUse → Write|Edit|MultiEdit (backend/ paths only)
Action: Run pytest on the modified module
Behavior: Log result — do not block on failure (advisory only)

### scope_policy_check.sh
Trigger: PreToolUse → Bash
Action: Check command against Band policy classification
Behavior: Warn on Band 2 tools, block on Band 3 tools

### protect_sensitive_paths.sh
Trigger: PreToolUse → Write|Edit|MultiEdit
Action: Block writes to auth/ certs/ secrets/ .env
Override: Requires KAI_OVERRIDE_SENSITIVE=1 in env

### write_session_state.sh
Trigger: PreCompact
Action: Write docs/session_state.md with current phase and context snapshot
Behavior: Must complete before compaction proceeds

---

## Activation Pattern

After testing a script standalone, add to settings.json:

  "PreToolUse": [
    {
      "matcher": "Write|Edit|MultiEdit",
      "hooks": [
        {
          "type": "command",
          "command": "/bin/bash .claude/hooks/protect_sensitive_paths.sh"
        }
      ]
    }
  ]

---

## CAUTION
Hook commands execute arbitrary shell at trigger time.
Anthropic explicitly flags hooks as high-risk.
Never activate a hook in settings.json before testing it standalone.
