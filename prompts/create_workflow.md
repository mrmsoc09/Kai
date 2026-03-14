# Prompt: Create a New Workflow

Design and implement a new Kai workflow template.

Required outputs:

- stage list with dependencies
- safe-mode behavior
- scope validation behavior
- workflow template definition
- planner/executor compatibility
- tests for planning and execution
- docs updates in `docs/workflows.md`

Rules:

- do not invent unsupported backend states
- keep intrusive actions approval-aware
- ensure artifacts/summary are generated even on partial failures
