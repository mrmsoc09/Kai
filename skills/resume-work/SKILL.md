---
name: resume-work
version: 1.0.0
description: Track work progress and resume where left off after interruptions
category: workflow
author: KaisonOne
triggers:
  - continue where I left off
  - resume work
  - what was I doing
  - work status
  - progress check
  - where were we
---

# Continue Where You Left Off

Track work progress and enable seamless resumption after interruptions.

## Purpose

Maintain a persistent work log that tracks:
- Current task being executed
- Completed items
- Remaining items
- Blockers or issues encountered
- Next steps

This allows resuming work without losing context after stops, crashes, or interruptions.

## Procedure

### Step 1: Update Work Log (After Each Task)

```bash
# Create/update work log
cat > output/worklog.json << 'EOF'
{
  "last_updated": "$(date -Iseconds)",
  "current_task": "Implementing nmap wrapper",
  "status": "in_progress",
  "milestone": "MVP Tool Wrappers",
  "completed": [
    "Fixed 3 syntax errors",
    "Added PentAGI/CAI submodules", 
    "Created Burp Suite wrapper"
  ],
  "remaining": [
    "nmap wrapper",
    "masscan wrapper",
    "ffuf wrapper"
  ],
  "blockers": [],
  "next_step": "Create nmap.py wrapper with XML parsing"
}
EOF
```

### Step 2: On Interruption/Stop

Automatically save current state:
```python
import json
import signal
import sys

def save_state(signum, frame):
    worklog = {
        "status": "interrupted",
        "last_action": current_action,
        "timestamp": datetime.now().isoformat()
    }
    with open('output/worklog.json', 'w') as f:
        json.dump(worklog, f, indent=2)
    sys.exit(0)

signal.signal(signal.SIGTERM, save_state)
signal.signal(signal.SIGINT, save_state)
```

### Step 3: Resume Work

When user says "continue where I left off":

```bash
# Load work log
python3 << 'EOF'
import json
try:
    with open('output/worklog.json') as f:
        log = json.load(f)
    print(f"Last task: {log.get('current_task', 'Unknown')}")
    print(f"Status: {log.get('status', 'Unknown')}")
    print(f"Completed: {len(log.get('completed', []))} items")
    print(f"Remaining: {len(log.get('remaining', []))} items")
    print(f"Next step: {log.get('next_step', 'Check TODO list')}")
except FileNotFoundError:
    print("No work log found. Starting fresh.")
EOF
```

### Step 4: Git Commit Work Log

```bash
# Commit work log with code changes
git add output/worklog.json
git commit -m "wip: $(cat output/worklog.json | jq -r '.current_task')"
git push origin main
```

## Work Log Format

```json
{
  "session_id": "uuid",
  "started_at": "2026-04-30T10:00:00Z",
  "last_updated": "2026-04-30T14:30:00Z",
  "project_phase": "MVP",
  "milestone": "Tool Wrappers",

  "current": {
    "task": "Task name",
    "description": "What we're doing",
    "started": "timestamp",
    "estimated_completion": "timestamp"
  },

  "completed": [
    {"item": "name", "completed_at": "timestamp", "commit": "hash"}
  ],

  "pending": [
    {"item": "name", "priority": "high/medium/low", "blocked_by": null}
  ],

  "blockers": [
    {"issue": "description", "severity": "high/medium/low"}
  ],

  "context": {
    "branch": "main",
    "last_commit": "abc123",
    "dirty_files": ["file1.py", "file2.py"],
    "notes": "Any important context"
  }
}
```

## Auto-Update on Tool Calls

Hook into tool execution to auto-update work log:
```python
# After successful tool execution
if tool_success:
    update_worklog(
        action=f"Completed: {tool_name}",
        result="success",
        files_modified=output_files
    )
```

## On Resume

1. Read worklog.json
2. Display status to user
3. Verify git state matches
4. Ask user: "Continue with [current task]?" or "Switch to [pending item]?"
5. Resume execution

## Files

- Work log: `output/worklog.json`
- Session backup: `output/worklog.backup.json`
