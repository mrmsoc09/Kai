# Phase 10 Retrospective and Feedback Learning Engine

Phase 10 extends Kai with deterministic retrospective learning built on canonical Phase 5-9 records. It does not introduce a parallel scoring engine.

## Purpose

Phase 10 closes the decision loop by measuring historical outcomes from:

- analyst cases
- alert lifecycles
- recommendation usage
- workflow signal/candidate production

These outcomes feed deterministic modifiers back into Phase 7 scoring.

## Canonical Data Model

Phase 10 persistence entities:

- `feedback_signal_records`
- `decision_outcome_records`
- `workflow_performance_records`
- `target_performance_records`
- `recommendation_outcome_records`
- `alert_outcome_records`

These records link back to canonical entities (`analyst_case_records`, `notification_alert_records`, `workflow_recommendation_records`, `workflow_runs`, `analyst_queue_items`, `scope_targets`, `programs`).

## Outcome Classification

Case outcomes are normalized into:

- `reportable_vulnerability`
- `duplicate_vulnerability`
- `dismissed_false_positive`
- `informational_finding`
- `insufficient_evidence`
- `unresolved_stale`

Recommendation outcomes are normalized into:

- `SUCCEEDED`
- `USED`
- `ABANDONED`
- `BLOCKED`
- `FAILED`

Alert outcomes are normalized into:

- `ESCALATED`
- `ACKNOWLEDGED`
- `IGNORED`
- `RESOLVED_ACTIONABLE`
- `RESOLVED_NOISE`
- `OPEN_TRACKING`

## Retrospective Service

Implementation: `apps/backend/src/core/phase10_retrospective_service.py`

Key responsibilities:

- ingest and classify case/alert/recommendation outcomes
- persist feedback and decision records with deterministic fingerprints
- compute workflow and target performance snapshots
- generate retrospective summary payloads for operators
- provide scoring modifiers for Phase 7

## Scoring Feedback Integration

Phase 7 (`phase7_prediction_service.py`) consumes Phase 10 modifiers from canonical retrospective records:

- `opportunity_multiplier`
- `yield_multiplier`
- `duplicate_risk_multiplier`
- `evidence_multiplier`
- `confidence_adjustment`

These modifiers adjust deterministic score components; they do not bypass safety/scope gates.

## API Surface

Added endpoints under `/api/v1/bug-bounty`:

- `POST /retrospective/run`
- `GET /retrospective/summary`
- `GET /retrospective/workflows`
- `GET /retrospective/targets`
- `GET /retrospective/recommendations`
- `GET /retrospective/alerts`

## CLI Surface

Added commands under `kai-cli bug-bounty`:

- `phase10-run`
- `phase10-summary`
- `phase10-workflows`
- `phase10-targets`
- `phase10-recommendations`

## Frontend Surface

Added route in operator console:

- `/retrospective` (Retrospective Intelligence)

The page exposes:

- retrospective summary
- top programs/targets
- workflow value leaders
- alert noise and recommendation success indicators
- manual `Run Phase 10` action

## Safety and Determinism

- No auto-submission behavior is introduced.
- No exploit logic is introduced.
- No parallel scoring subsystem is introduced.
- All retrospective decisions are persisted and auditable.
