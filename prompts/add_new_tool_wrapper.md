# Prompt: Add a New Tool Wrapper

You are extending Kai with a new tool wrapper.

Requirements:

- update `tools/registry/tool_registry.yaml`
- implement wrapper behavior through catalog-backed path unless specialized parser is required
- preserve safe execution (timeout, retries, exit-code, stdout/stderr)
- emit normalized output and provenance metadata
- add tests for success/failure/timeout parsing
- update `docs/tools.md` and relevant workflow docs

Constraints:

- no direct shell string interpolation
- no fake completion when tool is missing
- preserve existing API contracts where possible
