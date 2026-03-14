# Phase 7: Vulnerability Prediction and Opportunity Selection Engine

Phase 7 extends the existing canonical bug bounty architecture (Phase 5/6) with deterministic prediction and selection records.

## Canonical Persistence Additions

Phase 7 adds DB-backed records in `apps/backend/src/models/bug_bounty.py`:

- `TargetYieldScoreRecord`
- `DuplicateRiskRecord`
- `EvidenceCompletenessRecord`
- `VulnerabilityPredictionRecord`
- `OpportunitySelectionRecord`
- `WorkflowRecommendationRecord`

Migration: `apps/backend/alembic/versions/0008_phase7_prediction_selection_engine.py`

These records remain linked to canonical entities (`Program`, `ScopeTarget`, `WorkflowRun`, `AnalystQueueItem`) and do not introduce a parallel persistence layer.

## Deterministic Scoring Model

Service: `apps/backend/src/core/phase7_prediction_service.py`

Inputs are pulled from canonical Phase 5/6 entities:

- `SignalIntelligenceRecord`
- `AnalystQueueItem`
- existing schedule state (`HuntScheduleJob`) for adaptive effort actions

Deterministic outputs include:

- target/program yield scoring
- duplicate-risk scoring
- evidence completeness scoring
- vulnerability prediction records (confidence/novelty/duplicate/reportability/evidence/opportunity)
- opportunity ranking records
- workflow recommendation records (next workflow + follow-up action)

No opaque AI-only state is used; every output is persisted and queryable.

## Adaptive Effort Control

When `apply_adaptive=true`, Phase 7 can write canonical adaptive actions:

- `action_type=phase7_effort_control`
- status written as `APPLIED`, `BLOCKED`, or `SKIPPED`
- recommendation status updated (`APPLIED`, `BLOCKED`, `DEFERRED`)

Adaptive actions do not bypass scope or policy gates. They only adjust schedule priority/run timing for existing active schedules.

## API Surface

Router: `apps/backend/src/routers/bug_bounty.py`

- `POST /api/v1/bug-bounty/phase7/run`
- `GET /api/v1/bug-bounty/phase7/predictions`
- `GET /api/v1/bug-bounty/phase7/opportunity-rankings`
- `GET /api/v1/bug-bounty/phase7/target-yields`
- `GET /api/v1/bug-bounty/phase7/duplicate-risk`
- `GET /api/v1/bug-bounty/phase7/evidence-completeness`
- `GET /api/v1/bug-bounty/phase7/recommendations`
- `GET /api/v1/bug-bounty/phase7/analyst-support`

## CLI Surface

Command group: `kai-cli bug-bounty`

- `phase7-run`
- `phase7-predictions`
- `phase7-rankings`
- `phase7-recommendations`
- `phase7-analyst-support`

## Safety and Scope Posture

- Safe mode and scope/policy checks remain enforced at workflow launch time in existing canonical paths.
- Phase 7 only prioritizes and recommends next actions; it does not auto-submit externally.
- Recommendations are explainable with linked supporting records and score fields.
