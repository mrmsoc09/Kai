import type { CampaignDiagnosticsResponse, CampaignStatusResponse } from "@/lib/types";

export type CockpitActionPriority = "HIGH" | "MEDIUM" | "LOW";

export type CockpitAction = {
  id: string;
  title: string;
  description: string;
  status: "READY" | "RUNNING" | "WAITING_APPROVAL" | "FAILED" | "COMPLETED";
  priority: CockpitActionPriority;
  href: string;
  lane: "AUTONOMOUS" | "MANUAL";
};

export type CockpitGuidanceStep = {
  id: string;
  title: string;
  detail: string;
  href: string;
};

export type MissionCockpitModel = {
  autonomyCoverage: number;
  manualCoverage: number;
  confidenceScore: number;
  autonomyStatus: CockpitAction["status"];
  manualStatus: CockpitAction["status"];
  confidenceStatus: CockpitAction["status"];
  pendingApprovals: number;
  findingsNeedingReview: number;
  failedToolExecutions: number;
  activeToolExecutions: number;
  evidenceCount: number;
  aiSignals: string[];
  actions: CockpitAction[];
  guidanceSteps: CockpitGuidanceStep[];
};

const signalMatchers: Array<{ label: string; pattern: RegExp }> = [
  { label: "Model-guided prioritization refreshed", pattern: /(prediction|recommendation|ranking|opportunit)/i },
  { label: "Agent execution heartbeat active", pattern: /(agent|autonomous|copilot|reasoning)/i },
  { label: "Campaign correlation pass completed", pattern: /(correlat|finding|evidence|artifact)/i },
  { label: "Approval pressure requires operator review", pattern: /(approval|gate|review)/i },
  { label: "Tool telemetry captured for replay", pattern: /(tool|execution|stdout|stderr|phase)/i }
];

const phaseGuidanceMatchers: Array<{ pattern: RegExp; title: string; detail: string; href: string }> = [
  {
    pattern: /(recon|discover|surface|enum|crawl|subdomain)/i,
    title: "Validate recon discoveries",
    detail:
      "Spot-check newly discovered hosts and URLs against scope boundaries, then flag false positives before deeper exploitation.",
    href: "/recon"
  },
  {
    pattern: /(web|http|endpoint|url|content|dir)/i,
    title: "Run targeted web verification",
    detail:
      "Use mission terminal to manually replay high-confidence requests and test auth-state variations, caching behavior, and edge-case payloads.",
    href: "/terminal"
  },
  {
    pattern: /(api|graphql|rest|json|schema)/i,
    title: "Probe API attack paths",
    detail:
      "Manually test parameter tampering, authorization boundaries, and error-path leakage on candidate API endpoints.",
    href: "/attack-surface"
  },
  {
    pattern: /(approval|export|report|submit|review)/i,
    title: "Close review and reporting gates",
    detail:
      "Resolve pending approvals and confirm evidence-readiness for findings so validated issues can advance to submission.",
    href: "/approvals"
  }
];

function clampPercent(value: number): number {
  return Math.max(0, Math.min(100, Math.round(value)));
}

function normalizeCount(value: number | undefined): number {
  return typeof value === "number" && Number.isFinite(value) ? value : 0;
}

function statusCount(map: Record<string, number> | undefined, status: string): number {
  return normalizeCount(map?.[status]);
}

function summarizeSignals(events: CampaignDiagnosticsResponse["recent_audit_events"]): string[] {
  const labels: string[] = [];
  for (const event of events) {
    const text = `${event.event_type} ${event.actor ?? ""} ${event.message ?? ""} ${JSON.stringify(event.payload ?? {})}`;
    for (const matcher of signalMatchers) {
      if (matcher.pattern.test(text) && !labels.includes(matcher.label)) {
        labels.push(matcher.label);
      }
    }
    if (labels.length >= 4) {
      break;
    }
  }
  if (labels.length === 0) {
    return ["Awaiting additional telemetry to derive AI signal highlights"];
  }
  return labels;
}

function deriveGuidanceSteps(
  missionId: string,
  phaseJobs: CampaignStatusResponse["phase_jobs"],
  pendingApprovals: number,
  findingsNeedingReview: number
): CockpitGuidanceStep[] {
  const steps: CockpitGuidanceStep[] = [];
  const ordered = [...phaseJobs].sort((a, b) => a.phase_order - b.phase_order);

  for (const phase of ordered) {
    if (phase.status === "COMPLETED" || phase.status === "SKIPPED") {
      continue;
    }
    const match = phaseGuidanceMatchers.find((candidate) => candidate.pattern.test(phase.phase_name));
    if (!match) {
      continue;
    }
    if (steps.some((step) => step.title === match.title)) {
      continue;
    }
    const href = match.href === "/terminal" ? `/terminal?mission_id=${missionId}` : `${match.href}?mission_id=${missionId}`;
    steps.push({
      id: `phase:${phase.id}`,
      title: match.title,
      detail: match.detail,
      href
    });
    if (steps.length >= 4) {
      break;
    }
  }

  if (pendingApprovals > 0 && !steps.some((step) => step.title.includes("review"))) {
    steps.push({
      id: "approval:queue",
      title: "Resolve pending approvals",
      detail:
        "Review intention metadata and enforce scope constraints before approving actions that unlock additional autonomous execution.",
      href: "/approvals"
    });
  }

  if (findingsNeedingReview > 0 && !steps.some((step) => step.title.includes("reporting"))) {
    steps.push({
      id: "finding:validation",
      title: "Confirm exploitability and evidence",
      detail:
        "Prioritize high-impact findings for manual validation, then attach supporting artifacts to strengthen submission quality.",
      href: `/findings?campaign_id=${missionId}`
    });
  }

  if (steps.length === 0) {
    steps.push({
      id: "default:monitor",
      title: "Monitor autonomous mission flow",
      detail: "Track phase transitions and keep the terminal open for rapid intervention if scope, safety, or tool health changes.",
      href: `/terminal?mission_id=${missionId}`
    });
  }

  return steps.slice(0, 4);
}

export function deriveMissionCockpitModel(input: {
  missionId: string;
  campaign: CampaignStatusResponse;
  diagnostics: CampaignDiagnosticsResponse;
  findingsCount: number;
  approvalCount: number;
}): MissionCockpitModel {
  const { missionId, campaign, diagnostics, findingsCount, approvalCount } = input;
  const toolStatuses = diagnostics.status_breakdown.tool_executions;
  const approvalStatuses = diagnostics.status_breakdown.approval_gates;
  const phaseStatuses = diagnostics.status_breakdown.phase_jobs;

  const failedToolExecutions = statusCount(toolStatuses, "FAILED");
  const activeToolExecutions = statusCount(toolStatuses, "RUNNING") + statusCount(toolStatuses, "QUEUED");
  const completedToolExecutions = statusCount(toolStatuses, "COMPLETED");

  const pendingApprovals = Math.max(statusCount(approvalStatuses, "PENDING"), normalizeCount(approvalCount));
  const resolvedApprovals =
    statusCount(approvalStatuses, "APPROVED") +
    statusCount(approvalStatuses, "REJECTED") +
    statusCount(approvalStatuses, "DEFERRED") +
    statusCount(approvalStatuses, "CANCELED");

  const totalPhaseJobs = Math.max(campaign.phase_jobs.length, normalizeCount(diagnostics.counts.phase_jobs));
  const completedPhaseJobs = Math.max(
    campaign.phase_jobs.filter((job) => job.status === "COMPLETED").length,
    statusCount(phaseStatuses, "COMPLETED")
  );

  const autonomousDone = completedPhaseJobs + completedToolExecutions;
  const autonomousTotal = Math.max(
    autonomousDone + failedToolExecutions + activeToolExecutions,
    totalPhaseJobs + normalizeCount(diagnostics.counts.tool_executions),
    1
  );

  const autonomyCoverage = clampPercent((autonomousDone / autonomousTotal) * 100);

  const findingsNeedingReview = Math.max(0, normalizeCount(findingsCount));
  const manualResolved = resolvedApprovals;
  const manualTotal = Math.max(manualResolved + pendingApprovals + findingsNeedingReview, 1);
  const manualCoverage = clampPercent((manualResolved / manualTotal) * 100);

  const confidenceScore = clampPercent(
    90 -
      failedToolExecutions * 10 -
      pendingApprovals * 6 -
      findingsNeedingReview * 3 +
      Math.round((completedPhaseJobs / Math.max(totalPhaseJobs, 1)) * 15)
  );

  const autonomyStatus: CockpitAction["status"] =
    failedToolExecutions > 0
      ? "FAILED"
      : campaign.campaign.status === "COMPLETED"
        ? "COMPLETED"
        : activeToolExecutions > 0 || campaign.campaign.status === "RUNNING"
          ? "RUNNING"
          : "READY";

  const manualStatus: CockpitAction["status"] =
    pendingApprovals > 0 || findingsNeedingReview > 0
      ? "WAITING_APPROVAL"
      : pendingApprovals + findingsNeedingReview === 0 || manualCoverage >= 80
        ? "COMPLETED"
        : "READY";

  const confidenceStatus: CockpitAction["status"] =
    confidenceScore >= 80 ? "COMPLETED" : confidenceScore >= 60 ? "RUNNING" : confidenceScore >= 40 ? "WAITING_APPROVAL" : "FAILED";

  const actions: CockpitAction[] = [];

  if (campaign.campaign.status === "READY" || campaign.campaign.status === "PAUSED" || campaign.campaign.status === "BLOCKED") {
    actions.push({
      id: "autonomous:schedule",
      title: "Resume autonomous scheduling",
      description: "Queue eligible phase jobs and continue non-blocked recon, correlation, and enrichment tasks.",
      status: "READY",
      priority: "HIGH",
      href: `/mission-control/${missionId}`,
      lane: "AUTONOMOUS"
    });
  }

  if (activeToolExecutions > 0) {
    actions.push({
      id: "autonomous:monitor",
      title: "Monitor active tool executions",
      description: `${activeToolExecutions} tool execution(s) are active or queued. Keep terminal stream visible for drift or failure signals.`,
      status: "RUNNING",
      priority: "MEDIUM",
      href: `/terminal?mission_id=${missionId}`,
      lane: "AUTONOMOUS"
    });
  }

  if (pendingApprovals > 0) {
    actions.push({
      id: "manual:approvals",
      title: "Review approval gates",
      description: `${pendingApprovals} gate(s) are waiting for operator decision before mission progression can continue.`,
      status: "WAITING_APPROVAL",
      priority: "HIGH",
      href: "/approvals",
      lane: "MANUAL"
    });
  }

  if (findingsNeedingReview > 0) {
    actions.push({
      id: "manual:findings",
      title: "Validate prioritized findings",
      description: `${findingsNeedingReview} finding(s) are in queue. Confirm exploitability and attach evidence needed for export-ready submissions.`,
      status: "WAITING_APPROVAL",
      priority: "HIGH",
      href: `/findings?campaign_id=${missionId}`,
      lane: "MANUAL"
    });
  }

  if (failedToolExecutions > 0) {
    actions.push({
      id: "manual:tool-failures",
      title: "Triage failed tool runs",
      description: `${failedToolExecutions} execution(s) failed. Inspect logs and rerun scoped commands only after cause analysis.`,
      status: "FAILED",
      priority: "MEDIUM",
      href: `/system?mission_id=${missionId}`,
      lane: "MANUAL"
    });
  }

  if (actions.length === 0) {
    actions.push({
      id: "autonomous:steady",
      title: "Mission running with no immediate blockers",
      description: "Continue observing telemetry and periodic evidence quality checks.",
      status: "COMPLETED",
      priority: "LOW",
      href: `/mission-control/${missionId}`,
      lane: "AUTONOMOUS"
    });
  }

  return {
    autonomyCoverage,
    manualCoverage,
    confidenceScore,
    autonomyStatus,
    manualStatus,
    confidenceStatus,
    pendingApprovals,
    findingsNeedingReview,
    failedToolExecutions,
    activeToolExecutions,
    evidenceCount: normalizeCount(diagnostics.counts.artifacts) + normalizeCount(diagnostics.counts.observations),
    aiSignals: summarizeSignals(diagnostics.recent_audit_events),
    actions,
    guidanceSteps: deriveGuidanceSteps(missionId, campaign.phase_jobs, pendingApprovals, findingsNeedingReview)
  };
}
