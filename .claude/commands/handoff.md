Write or update docs/HANDOFF.md with current session state before context resets.

The handoff document must include:

CURRENT PHASE: [number and name]
PHASE STATUS: [COMPLETE | IN_PROGRESS | BLOCKED]

FILES CREATED THIS SESSION:
- [list every file path created]

FILES MODIFIED THIS SESSION:
- [list every file path modified]

ARCHITECTURAL DECISIONS MADE:
- [list every significant decision with rationale]

WHAT WORKED:
- [list approaches that succeeded]

WHAT FAILED OR WAS ABANDONED:
- [list approaches tried and rejected, with reason]

CURRENT BLOCKERS:
- [list anything blocking progress with file:line reference]

FAILING TESTS:
- [list test names and error messages]

NEXT ACTION:
- [exact next step for the agent loading this file]

LOAD THESE FILES ON RESUME:
- [list the 3-5 files most critical for the next agent to read first]

This file must be complete enough that an agent with no prior context
can load it and continue without asking questions.
