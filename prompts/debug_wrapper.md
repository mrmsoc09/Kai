# Prompt: Debug a Tool Wrapper

Investigate and fix a failing Kai tool wrapper.

Process:

1. reproduce failure with a focused test
2. inspect command, params, stdout/stderr, exit code
3. verify tool install command from catalog
4. validate parser mode and normalization logic
5. apply smallest safe fix
6. add regression test
7. report root cause and constraints

Rules:

- do not bypass scope/safety gates
- do not suppress errors silently
- keep behavior deterministic
