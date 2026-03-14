# Frontend Analyst Cockpit

## Purpose

Phase 8 + Phase 9 introduce an analyst-focused cockpit over canonical bug bounty execution data.

The UI is intentionally operational:

- program and target visibility
- queue triage
- prediction/recommendation review
- alert and case workflow follow-through
- scheduler and tool-health operations

No frontend-only workflow truth is introduced.

## Primary Views

- `/overview`: dashboard summary (programs, schedules, candidate pressure, readiness blocks, health)
- `/programs`: bug bounty opportunity list and program-level yield indicators
- `/targets`: monitored target inventory with readiness/yield/next action
- `/opportunities`: Phase 7 ranked opportunity selections
- `/triage`: candidate finding queue with status transitions and report draft generation
- `/predictions`: vulnerability predictions + signal intelligence + recommendation reasoning
- `/agents`: Phase 10.5 specialized agent registry/execution/evaluation telemetry
- `/retrospective`: Phase 10 historical outcome intelligence and score-feedback visibility
- `/briefing`: analyst briefing and Phase 7 decision-support summaries
- `/alerts`: persisted Phase 9 alert queue with acknowledge/resolve/case creation actions
- `/cases`: case queue with ownership and lifecycle state controls
- `/cases/[caseId]`: detailed case workspace (status/priority/assignment/notes)
- `/system`: scheduler/readiness/adaptive action + tool health operations

## State Management

TanStack Query is used for all backend state fetches and mutations.

After mutations (`PATCH candidate`, `POST report-draft`, `POST phase7/run`, alert acknowledge/resolve, case updates), relevant bug bounty query keys are invalidated and refetched.

## Canonical Backend Dependencies

The cockpit depends on:

- `/api/v1/bug-bounty/*`
- `/api/v1/bug-bounty/phase7/*`
- `/api/v1/bug-bounty/agents*`
- `/api/v1/bug-bounty/retrospective/*`
- `/api/v1/bug-bounty/alerts*`
- `/api/v1/bug-bounty/cases*`
- `/api/v1/tools/health`
- `/health`, `/readyz`

## Score / Status Rendering

Shared score/status components are used everywhere:

- `StatusBadge`
- `ScoreBadge`
- `SeverityBadge`

This keeps confidence/reportability/duplicate/evidence semantics consistent across tables and panels.

## What Is Deferred

- External provider submission from UI (staging/prep only)
- Case-level bulk operations (single-record workflow is canonical today)
- Live streaming updates (query polling/refetch model remains canonical)
