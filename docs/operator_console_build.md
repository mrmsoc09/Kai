# Operator Console Build (Phase 8 + Phase 9)

## App Location

- `apps/frontend-operator/`

The operator cockpit is a standalone Next.js app that consumes canonical backend contracts under `/api/v1`.

## Stack

- Next.js (App Router)
- React + TypeScript
- Tailwind CSS
- shadcn-style primitives in `components/ui/*`
- TanStack Query for server state

## Canonical Extension Approach

Phase 8 extends the existing console without replacing it:

- Existing routes for campaign/finding/approval/export remain available.
- New analyst cockpit surfaces are added on top of canonical bug bounty + Phase 6/7 APIs.
- No parallel frontend state system or duplicate API runtime was introduced.

## New Analyst Cockpit Routes

- `/overview` (bug bounty dashboard home)
- `/programs`
- `/targets`
- `/opportunities`
- `/triage` (candidate-finding queue)
- `/predictions`
- `/agents`
- `/retrospective`
- `/briefing`
- `/alerts` (canonical Phase 9 alerts)
- `/cases` (case queue)
- `/cases/[caseId]` (case detail workspace)
- `/system` (operations/health)

Legacy SOC and campaign routes remain in place for compatibility.

## Frontend Architecture Additions

### API Layer

Added:

- `lib/api/bug-bounty.ts`

Provides typed access to:

- program list
- monitored targets
- schedules + scheduler status
- readiness records
- delta records
- candidate queue + candidate update + report draft generation
- Phase 6 signals/opportunity/adaptive/briefing
- Phase 7 predictions/rankings/yields/duplicate/evidence/recommendations/support
- tool health dashboard

### Type Layer

Added:

- `lib/types/bug-bounty.ts`

Exports canonical frontend contracts for all bug bounty and Phase 6/7 payloads.

### Hooks

Added:

- `hooks/useBountyDashboard.ts`
- `hooks/useBountyPrograms.ts`
- `hooks/useMonitoredTargets.ts`
- `hooks/useOpportunityRankings.ts`
- `hooks/useCandidateQueue.ts`
- `hooks/usePredictionSignals.ts`
- `hooks/useAgentFramework.ts`
- `hooks/useAnalystBriefing.ts`
- `hooks/useRetrospective.ts`
- `hooks/useBountyOperations.ts`
- `hooks/useAlertCenter.ts`
- `hooks/useCaseQueue.ts`
- `hooks/useCaseDetail.ts`

### Reusable Components

Added:

- `components/status/ScoreBadge.tsx`
- `components/bugbounty/ProgramTable.tsx`
- `components/bugbounty/MonitoredTargetTable.tsx`
- `components/bugbounty/OpportunityRankingTable.tsx`
- `components/bugbounty/CandidateQueueTable.tsx`
- `components/bugbounty/PredictionTable.tsx`
- `components/bugbounty/AgentRegistryTable.tsx`
- `components/bugbounty/AgentExecutionTable.tsx`
- `components/bugbounty/AgentEvaluationTable.tsx`
- `components/bugbounty/AnalystBriefingPanel.tsx`
- `components/bugbounty/OperationsHealthPanel.tsx`
- `components/bugbounty/ReasoningSummaryPanel.tsx`
- `components/bugbounty/EvidenceLinkPanel.tsx`
- `components/bugbounty/AlertTable.tsx`
- `components/bugbounty/CaseQueueTable.tsx`
- `components/bugbounty/CaseDetailPanel.tsx`

## Backend Contracts Consumed

Primary routes used by new cockpit surfaces:

- `/api/v1/bug-bounty/programs`
- `/api/v1/bug-bounty/programs/{program_id}/targets`
- `/api/v1/bug-bounty/schedules`
- `/api/v1/bug-bounty/schedules/status`
- `/api/v1/bug-bounty/readiness-records`
- `/api/v1/bug-bounty/deltas`
- `/api/v1/bug-bounty/candidates`
- `/api/v1/bug-bounty/candidates/{queue_item_id}` (PATCH)
- `/api/v1/bug-bounty/candidates/{queue_item_id}/report-draft`
- `/api/v1/bug-bounty/signals`
- `/api/v1/bug-bounty/opportunity-scores`
- `/api/v1/bug-bounty/adaptive-actions`
- `/api/v1/bug-bounty/analyst-briefing`
- `/api/v1/bug-bounty/phase7/*`
- `/api/v1/bug-bounty/agents*`
- `/api/v1/bug-bounty/retrospective/*`
- `/api/v1/bug-bounty/alerts/sync`
- `/api/v1/bug-bounty/alerts`
- `/api/v1/bug-bounty/alerts/summary`
- `/api/v1/bug-bounty/alerts/{alert_id}`
- `/api/v1/bug-bounty/alerts/{alert_id}/acknowledge`
- `/api/v1/bug-bounty/alerts/{alert_id}/resolve`
- `/api/v1/bug-bounty/alerts/{alert_id}/case`
- `/api/v1/bug-bounty/cases`
- `/api/v1/bug-bounty/cases/{case_id}`
- `/api/v1/bug-bounty/cases/{case_id}/assign`
- `/api/v1/bug-bounty/cases/{case_id}/notes`
- `/api/v1/tools/health`
- `/health`
- `/readyz`

## Theme and Semantics

Dark-first palette and semantic color system remain unchanged:

- blue: active/running
- orange: review/action required
- red-orange/red: blocked/failed/rejected
- purple: findings/evidence context
- indigo: intelligence/correlation context
- green: ready/success/report-ready

All key states use both text + badge color.

## Local Development

From `apps/frontend-operator/`:

1. `npm install`
2. `npm run dev`

Optional API base override:

- `NEXT_PUBLIC_API_BASE_URL=http://localhost:8080`

## Validation Commands

From `apps/frontend-operator/`:

- `npm run typecheck`
- `npm test`
- `npm run build`

## Deferred / Honest Gaps

- No external platform report submission from frontend (staging/prep only).
- Case-level bulk actions are not implemented yet (single-case actions only).
- Some legacy SOC pages remain campaign-derived and are retained for backward compatibility.
