# Operator Console Surfaces

This map reflects the current frontend console after Phase 8 cockpit integration.

## Analyst Cockpit (Primary)

| Surface | Route | Canonical Data Source | Coverage |
|---|---|---|---|
| Dashboard Home | `/overview` | `/api/v1/bug-bounty/programs`, `/schedules`, `/schedules/status`, `/candidates`, `/readiness-records`, `/phase7/recommendations`, `/api/v1/tools/health`, `/health`, `/readyz` | Fully backed |
| Bug Bounty Programs | `/programs` | `/api/v1/bug-bounty/programs` (+ target/schedule/candidate/yield/ranking joins) | Fully backed |
| Monitored Targets | `/targets` | `/api/v1/bug-bounty/programs/{id}/targets`, `/schedules`, `/readiness-records`, `/phase7/target-yields`, `/phase7/recommendations`, `/deltas` | Fully backed |
| Opportunity Rankings | `/opportunities` | `/api/v1/bug-bounty/phase7/opportunity-rankings`, `/phase7/recommendations`, `/phase7/predictions` | Fully backed |
| Candidate Findings Queue | `/triage` | `/api/v1/bug-bounty/candidates`, `/phase7/duplicate-risk`, `/phase7/evidence-completeness`, `/phase7/recommendations` | Fully backed |
| Predictions / Signals | `/predictions` | `/api/v1/bug-bounty/phase7/predictions`, `/signals`, `/deltas`, `/phase7/recommendations`, `/phase7/analyst-support` | Fully backed |
| Retrospective Intelligence | `/retrospective` | `POST /api/v1/bug-bounty/retrospective/run`, `/retrospective/summary`, `/retrospective/workflows`, `/retrospective/targets`, `/retrospective/recommendations`, `/retrospective/alerts` | Fully backed |
| Analyst Briefing / Draft Prep | `/briefing` | `/api/v1/bug-bounty/analyst-briefing`, `/phase7/analyst-support`, `/candidates`, `PATCH /candidates/{id}`, `POST /candidates/{id}/report-draft` | Fully backed |
| Alerts | `/alerts` | `/api/v1/bug-bounty/alerts`, `/alerts/sync`, `/alerts/summary`, `POST /alerts/{id}/acknowledge`, `POST /alerts/{id}/resolve`, `POST /alerts/{id}/case` | Fully backed |
| Cases Queue | `/cases` | `/api/v1/bug-bounty/cases`, `PATCH /cases/{id}`, `POST /cases/{id}/assign` | Fully backed |
| Case Detail | `/cases/[caseId]` | `/api/v1/bug-bounty/cases/{id}`, `PATCH /cases/{id}`, `POST /cases/{id}/assign`, `POST /cases/{id}/notes` | Fully backed |
| Operations / Health | `/system` | `/api/v1/bug-bounty/schedules/status`, `/schedules`, `/readiness-records`, `/adaptive-actions`, `/api/v1/tools/health`, `/health`, `/readyz` | Fully backed |

## Existing SOC Surfaces (Compatibility)

These routes remain available from the earlier SOC pass and are retained for continuity:

- `/attack-surface`
- `/recon`
- `/evidence`
- `/threat-intel`
- `/ioc`
- `/timeline`
- `/analytics`
- `/playbooks`
- `/diagnostics` (legacy diagnostics surface)

Some of these compatibility surfaces are campaign/findings-derived and should be treated as secondary to the analyst cockpit routes above for active bug bounty operations.
