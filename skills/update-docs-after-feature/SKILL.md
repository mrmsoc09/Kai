# update-docs-after-feature

Purpose: keep repository documentation aligned with implemented behavior.

## Procedure

1. Identify changed code paths and public interfaces.
2. Update relevant docs under `docs/`:
   - architecture/workflows/tools/configuration/output schema/scope enforcement
3. Document:
   - implemented behavior
   - partial behavior
   - deferred behavior
4. Add command examples that actually run in this repo.
5. Remove stale claims and obsolete references.
6. Ensure new docs reference concrete files/endpoints.

## Exit Checklist

- no speculative claims
- no TODO-only placeholders for core behavior
- docs and tests describe the same status
