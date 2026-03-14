# Operator Console Build

## Frontend App Location

- `apps/frontend-operator/`

The operator console is implemented as a separate Next.js app and consumes canonical backend APIs under `/api/v1`.

## Stack Used

- Next.js (App Router)
- React + TypeScript
- Tailwind CSS
- shadcn-style UI primitives (`components/ui/*`)
- TanStack Query for server-state

## What Existed Before SOC Extension

Initial operator console surfaces already implemented:

- `/campaigns`
- `/campaigns/[campaignId]`
- `/findings`
- `/findings/[findingId]`
- `/approvals`
- `/exports`
- `/diagnostics`

These remain intact and are still the canonical control workflows for campaign start/schedule, finding review, approvals, and export staging.

## SOC Extension Added In This Pass

New SOC-OPS routes added:

- `/overview`
- `/attack-surface`
- `/recon`
- `/triage`
- `/evidence`
- `/threat-intel`
- `/ioc`
- `/timeline`
- `/analytics`
- `/playbooks`
- `/alerts`
- `/system`

Sidebar navigation now groups routes into:

- Core Operations
- SOC Intelligence

## Component Architecture

Existing folders preserved:

- `components/ui/`
- `components/layout/`
- `components/status/`
- `components/data-display/`
- `components/campaigns/`
- `components/phases/`
- `components/findings/`
- `components/approvals/`
- `components/exports/`
- `components/diagnostics/`
- `components/forms/`

New SOC folder added:

- `components/soc/`

SOC reusable components added include:

- `OverviewSummaryCards`
- `AttackSurfaceTable`
- `ReconActivityTable`
- `FindingsTriagePanel`
- `EvidenceRepositoryTable`
- `ThreatIntelPanel`
- `IocTable`
- `InvestigationTimeline`
- `AnalyticsCards`
- `AnalyticsCharts`
- `PlaybookCatalog`
- `AlertsTable`
- `SystemDiagnosticsPanel`
- `TrackedCampaignSelector`
- `BackendSupportPending`

## API / Hook Architecture

Typed API modules now include:

- `lib/api/client.ts`
- `lib/api/campaigns.ts`
- `lib/api/findings.ts`
- `lib/api/approvals.ts`
- `lib/api/exports.ts`
- `lib/api/diagnostics.ts`
- `lib/api/soc.ts` (SOC read-only aggregator over canonical endpoints)

Types include:

- `lib/types/api.ts`
- `lib/types/campaigns.ts`
- `lib/types/findings.ts`
- `lib/types/diagnostics.ts`
- `lib/types/soc.ts`

SOC hooks added:

- `hooks/useTrackedCampaignIds.ts`
- `hooks/useTrackedCampaignData.ts`
- `hooks/useOverview.ts`
- `hooks/useAttackSurface.ts`
- `hooks/useReconActivity.ts`
- `hooks/useTimeline.ts`
- `hooks/useAnalytics.ts`
- `hooks/useAlerts.ts`
- `hooks/useSystemDiagnostics.ts`
- `hooks/useThreatIntel.ts`
- `hooks/useIoc.ts`
- `hooks/usePlaybooks.ts`

## Theme Semantics (Dark-First)

Base palette:

- Background: `#0B0F14`
- Panel: `#121821`
- Elevated: `#1A2330`
- Border: `#263241`
- Text: `#E6EDF3`
- Muted Text: `#9BA7B4`

Accent semantics:

- Blue `#3B82F6`: running/active
- Purple `#8B5CF6`: findings/evidence
- Indigo `#6366F1`: observations/intelligence
- Orange `#F59E0B`: review/approval action required
- Red-Orange `#F97316`: blocked/escalation
- Red `#EF4444`: failed/rejected/danger
- Green `#22C55E`: approved/ready/success

Status rendering remains centralized in:

- `components/status/StatusBadge.tsx`
- `lib/utils/status.ts`

## Backend Dependencies and Data Sources

This SOC pass did not add new backend mutation features.
It consumes existing canonical endpoints:

- campaign start/status/schedule/diagnostics/correlation
- approval decision
- findings review queue and finding diagnostics
- review/submission prep/export preview and staging
- diagnostics summary, liveness, readiness

SOC pages intentionally derive read-only intelligence views from canonical diagnostics and review queue data where dedicated backend inventory/intel APIs do not yet exist.

## Deferred / Honest Gaps

- No dedicated campaign list endpoint; many SOC views still rely on tracked campaign IDs.
- No canonical artifact/evidence global listing endpoint yet; evidence repository is currently aggregate-derived.
- No external threat-intel feed integration in this pass.
- No IOC-specific backend table/API; IOC view is deterministic regex extraction from canonical text payloads.
- No direct playbook-execution API from the frontend in this pass.
- No external provider submission integration; export remains preview/staging only.
- No SSE/WebSocket streaming yet; TanStack Query refetch/invalidation remains the state sync mechanism.
