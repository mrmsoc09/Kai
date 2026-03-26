# Report Phase 5: BBP Readiness + HiL Gate

This document describes the additive Phase 5 report flow implemented for Kai.

## Scope

Phase 5 extends report finalization and submission with a strict readiness gate for standard run-based submissions (`run_id` + `format_id`).

Lightweight compatibility mode remains for minimal/test payloads that omit `run_id` or `format_id`.

## Mandatory BBP Readiness Requirements

A report is considered ready only when all are present:

- full screen recording
- validated exploit evidence
- confidence score
- arbitration summary (`final_verdict`, `final_confidence`, `arbitration_reason`)

If any are missing, the report remains `DRAFT` and submission is blocked.

## Report States

Phase 5 report lifecycle state is tracked as:

- `DRAFT`
- `VALIDATED`
- `FINALIZED`

State and generated artifacts are stored under:

- `artifacts/reports/bbp_ready/<run_id>/report.json`
- `artifacts/reports/bbp_ready/<run_id>/report.md`
- `artifacts/reports/bbp_ready/<run_id>/report_state.json`

## HiL Requirement

When `report_ready == true`, human approval is still required before final submission/package:

- `hil_approved` must be `true`

Without HiL approval, finalization for submission is blocked.

## Finalization Immutability

After `FINALIZED`:

- report state is immutable
- evidence state is frozen via `EvidenceIntegrityService.finalize_run_evidence(...)`
- payload mutations that change the finalized report hash are rejected

## Endpoint Integration

The following routes now include Phase 5 behavior for strict-mode requests:

- `POST /reports/finalize`
- `POST /reports/submit_hil`
- `POST /reports/package`

Additional response fields are additive and backward-compatible, including:

- `report_state`
- `report_json_path`
- `report_markdown_path`
- optional `phase5` object on finalize response

## Generated Report Content

Phase 5 report artifacts include:

- vulnerability description
- reproduction steps
- screenshot references
- mandatory video recording path
- impact analysis
- confidence score
- arbitration summary
- chain-of-custody hashes
- attack chain context

Outputs are emitted as both JSON and Markdown.
