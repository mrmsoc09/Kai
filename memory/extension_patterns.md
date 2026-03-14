# Extension Patterns Memory

Preferred extension path:

1. define catalog metadata
2. use generic wrapper if possible
3. add parser specialization only when required
4. normalize into existing schema records
5. add tests
6. update docs

Workflow extension pattern:

1. add stage/tool step to template
2. validate scope and safe-mode behavior
3. verify dependency order
4. run smoke workflow

Hook extension pattern:

1. use optional hooks under `hooks/`
2. keep hook failures non-fatal unless security-critical
3. never bypass core authorization/scope controls inside hooks

Anti-patterns:

- adding direct subprocess logic in API routers
- introducing wrapper-specific output shapes without normalization
- silent fallback that hides missing tool/runtime issues
