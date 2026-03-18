---
name: normalize-output-parser
description: Skill for normalize-output-parser
---

# normalize-output-parser

Purpose: convert heterogeneous tool outputs into Kai normalized records.

## Procedure

1. Capture representative raw outputs.
   - success output
   - empty output
   - malformed/partial output
2. Extend parse handling in wrapper (`tool_adapters_bugbounty.py`) only as needed.
3. Map parsed fields in `apps/backend/src/core/workflow_normalizer.py`.
   - asset/dns/service/url/endpoint/parameter/tech/vuln/secret records
4. Preserve provenance.
   - source tool id
   - target
   - command metadata
5. Add fixture-based tests for all supported parse branches.
6. Verify downstream correlation consumes new normalized shape.

## Quality Rules

- parser must not throw on malformed lines
- unknown fields should be preserved in structured payload where possible
- avoid lossy transformations unless documented
