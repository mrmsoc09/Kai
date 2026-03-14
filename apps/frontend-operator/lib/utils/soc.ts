import type {
  AuditEvent,
  CampaignDiagnosticsResponse,
  CampaignStatusResponse,
  FindingDiagnosticsResponse,
  FindingQueueItem,
  SocAlert,
  SocAssetRow,
  SocIocRow,
  SocPlaybookRow,
  SocTimelineItem
} from "@/lib/types";

const technologyPatterns: Array<{ name: string; pattern: RegExp }> = [
  { name: "Nginx", pattern: /\bnginx\b/i },
  { name: "Apache", pattern: /\bapache\b/i },
  { name: "Node.js", pattern: /\bnode(\.js)?\b/i },
  { name: "Python", pattern: /\bpython\b/i },
  { name: "Django", pattern: /\bdjango\b/i },
  { name: "Flask", pattern: /\bflask\b/i },
  { name: "FastAPI", pattern: /\bfastapi\b/i },
  { name: "WordPress", pattern: /\bwordpress\b/i },
  { name: "React", pattern: /\breact\b/i },
  { name: "PostgreSQL", pattern: /\bpostgres(ql)?\b/i }
];

const iocPatterns = {
  ip: /\b(?:\d{1,3}\.){3}\d{1,3}\b/g,
  domain: /\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b/gi,
  url: /\bhttps?:\/\/[^\s"')]+/gi,
  sha256: /\b[a-fA-F0-9]{64}\b/g
};

function parseTime(value: string | null | undefined): number {
  if (!value) {
    return 0;
  }
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function pushAlert(target: SocAlert[], alert: SocAlert) {
  if (!target.some((existing) => existing.id === alert.id)) {
    target.push(alert);
  }
}

export function deriveOverviewAlerts(input: {
  diagnostics: CampaignDiagnosticsResponse[];
  findings: FindingQueueItem[];
  summaryGeneratedAt?: string;
}): SocAlert[] {
  const alerts: SocAlert[] = [];

  for (const diag of input.diagnostics) {
    const campaignId = diag.campaign.id;
    if (diag.campaign.status === "FAILED") {
      pushAlert(alerts, {
        id: `campaign-failed:${campaignId}`,
        severity: "HIGH",
        category: "CAMPAIGN",
        title: "Campaign failed",
        description: diag.campaign.last_error ?? "Campaign entered FAILED state.",
        campaignId,
        happenedAt: diag.campaign.updated_at
      });
    }
    if (diag.campaign.status === "BLOCKED") {
      pushAlert(alerts, {
        id: `campaign-blocked:${campaignId}`,
        severity: "MEDIUM",
        category: "CAMPAIGN",
        title: "Campaign blocked",
        description: diag.campaign.blocked_reason ?? "Campaign is blocked pending dependencies or approvals.",
        campaignId,
        happenedAt: diag.campaign.updated_at
      });
    }
    const pendingApprovals = diag.status_breakdown.approval_gates?.PENDING ?? 0;
    if (pendingApprovals > 0) {
      pushAlert(alerts, {
        id: `approval-pending:${campaignId}`,
        severity: "MEDIUM",
        category: "APPROVAL",
        title: "Pending approvals",
        description: `${pendingApprovals} approval gate(s) pending in campaign.`,
        campaignId,
        happenedAt: diag.campaign.updated_at
      });
    }
    const failedTools = diag.status_breakdown.tool_executions?.FAILED ?? 0;
    if (failedTools > 0) {
      pushAlert(alerts, {
        id: `tool-failed:${campaignId}`,
        severity: "HIGH",
        category: "EXECUTION",
        title: "Tool execution failures",
        description: `${failedTools} tool execution(s) failed.`,
        campaignId,
        happenedAt: diag.campaign.updated_at
      });
    }

    const exportValidationFailures = diag.recent_audit_events.filter(
      (event) => event.event_type === "submission_export.validation_failed"
    );
    for (const event of exportValidationFailures) {
      pushAlert(alerts, {
        id: `export-validation:${event.id}`,
        severity: "MEDIUM",
        category: "EXPORT",
        title: "Submission export validation failed",
        description: event.message ?? "Provider payload validation failed.",
        campaignId,
        findingId:
          typeof event.payload.finding_id === "string" ? event.payload.finding_id : undefined,
        happenedAt: event.happened_at,
        sourceEventType: event.event_type
      });
    }
  }

  for (const finding of input.findings) {
    if (finding.readiness_status.toUpperCase() === "INSUFFICIENT_EVIDENCE") {
      pushAlert(alerts, {
        id: `finding-insufficient:${finding.finding_id}`,
        severity: "LOW",
        category: "EXPORT",
        title: "Finding lacks evidence",
        description: `${finding.title} is not export-ready due to insufficient evidence.`,
        campaignId: finding.campaign_id,
        findingId: finding.finding_id
      });
    }
  }

  if (alerts.length === 0 && input.summaryGeneratedAt) {
    alerts.push({
      id: "no-alerts",
      severity: "INFO",
      category: "SYSTEM",
      title: "No active SOC alerts",
      description: "No campaign, approval, execution, or export alerts were derived.",
      happenedAt: input.summaryGeneratedAt
    });
  }

  return alerts.sort((a, b) => parseTime(b.happenedAt) - parseTime(a.happenedAt));
}

export function deriveAttackSurfaceRows(
  findings: FindingQueueItem[],
  findingDiagnostics: FindingDiagnosticsResponse[]
): SocAssetRow[] {
  const techByAsset = new Map<string, Set<string>>();
  for (const finding of findingDiagnostics) {
    const asset = finding.finding.asset || "unknown-asset";
    const bucket = techByAsset.get(asset) ?? new Set<string>();
    for (const observation of finding.recent_observations) {
      const text = `${observation.title ?? ""} ${observation.summary ?? ""}`;
      for (const tech of extractTechnologyHints(text)) {
        bucket.add(tech);
      }
    }
    techByAsset.set(asset, bucket);
  }

  const grouped = new Map<string, SocAssetRow>();
  for (const item of findings) {
    const key = `${item.campaign_id}:${item.asset}`;
    const existing = grouped.get(key);
    if (!existing) {
      grouped.set(key, {
        key,
        asset: item.asset,
        program: item.program,
        campaignId: item.campaign_id,
        findings: 1,
        evidenceCount: item.evidence_count,
        readinessStates: [item.readiness_status],
        technologies: Array.from(techByAsset.get(item.asset) ?? []),
        source: "canonical_findings_queue"
      });
      continue;
    }
    existing.findings += 1;
    existing.evidenceCount += item.evidence_count;
    if (!existing.readinessStates.includes(item.readiness_status)) {
      existing.readinessStates.push(item.readiness_status);
    }
  }
  return Array.from(grouped.values()).sort((a, b) => b.findings - a.findings);
}

export function extractTechnologyHints(text: string): string[] {
  const hints: string[] = [];
  for (const candidate of technologyPatterns) {
    if (candidate.pattern.test(text)) {
      hints.push(candidate.name);
    }
  }
  return hints;
}

export function extractIocs(input: {
  campaignDiagnostics: CampaignDiagnosticsResponse[];
  findingDiagnostics: FindingDiagnosticsResponse[];
  findings: FindingQueueItem[];
}): SocIocRow[] {
  const rows = new Map<string, SocIocRow>();

  function addRow(row: SocIocRow) {
    if (!rows.has(row.key)) {
      rows.set(row.key, row);
    }
  }

  for (const finding of input.findings) {
    if (finding.asset.includes(".")) {
      addRow({
        key: `asset:${finding.asset}`,
        indicator: finding.asset,
        type: "DOMAIN",
        confidence: "derived",
        source: "finding_asset",
        campaignId: finding.campaign_id,
        findingId: finding.finding_id
      });
    }
  }

  for (const diag of input.findingDiagnostics) {
    for (const observation of diag.recent_observations) {
      const content = `${observation.title ?? ""} ${observation.summary ?? ""}`;
      for (const value of matchAll(content, iocPatterns.ip)) {
        addRow({
          key: `ioc:ip:${value}`,
          indicator: value,
          type: "IP",
          confidence: "derived",
          source: "observation",
          findingId: diag.finding.id
        });
      }
      for (const value of matchAll(content, iocPatterns.domain)) {
        addRow({
          key: `ioc:domain:${value.toLowerCase()}`,
          indicator: value.toLowerCase(),
          type: "DOMAIN",
          confidence: "derived",
          source: "observation",
          findingId: diag.finding.id
        });
      }
      for (const value of matchAll(content, iocPatterns.url)) {
        addRow({
          key: `ioc:url:${value}`,
          indicator: value,
          type: "URL",
          confidence: "derived",
          source: "observation",
          findingId: diag.finding.id
        });
      }
      for (const value of matchAll(content, iocPatterns.sha256)) {
        addRow({
          key: `ioc:sha256:${value.toLowerCase()}`,
          indicator: value.toLowerCase(),
          type: "SHA256",
          confidence: "derived",
          source: "observation",
          findingId: diag.finding.id
        });
      }
    }
  }

  for (const campaign of input.campaignDiagnostics) {
    for (const event of campaign.recent_audit_events) {
      const content = `${event.message ?? ""} ${JSON.stringify(event.payload ?? {})}`;
      for (const value of matchAll(content, iocPatterns.sha256)) {
        addRow({
          key: `audit-sha256:${value.toLowerCase()}`,
          indicator: value.toLowerCase(),
          type: "SHA256",
          confidence: "derived",
          source: "audit",
          campaignId: campaign.campaign.id
        });
      }
    }
  }

  return Array.from(rows.values()).sort((a, b) => a.indicator.localeCompare(b.indicator));
}

export function deriveTimelineItems(input: {
  campaignId?: string;
  findingId?: string;
  campaignDiagnostics?: CampaignDiagnosticsResponse | null;
  findingDiagnostics?: FindingDiagnosticsResponse | null;
}): SocTimelineItem[] {
  const timeline: SocTimelineItem[] = [];

  if (input.campaignDiagnostics) {
    for (const event of input.campaignDiagnostics.recent_audit_events) {
      timeline.push({
        id: `campaign:${event.id}`,
        happenedAt: event.happened_at,
        eventType: event.event_type,
        actor: event.actor,
        message: event.message,
        campaignId: input.campaignDiagnostics.campaign.id,
        payload: event.payload
      });
    }
  }

  if (input.findingDiagnostics) {
    for (const event of input.findingDiagnostics.recent_audit_events) {
      timeline.push({
        id: `finding:${event.id}`,
        happenedAt: event.happened_at,
        eventType: event.event_type,
        actor: event.actor,
        message: event.message,
        findingId: input.findingDiagnostics.finding.id,
        payload: event.payload
      });
    }
  }

  return timeline.sort((a, b) => parseTime(b.happenedAt) - parseTime(a.happenedAt));
}

export function derivePlaybooks(campaigns: CampaignStatusResponse[]): SocPlaybookRow[] {
  const byPhase = new Map<string, SocPlaybookRow>();
  for (const campaign of campaigns) {
    const phaseNames = new Set<string>();
    for (const job of campaign.phase_jobs) {
      phaseNames.add(job.phase_name);
      const phase = byPhase.get(job.phase_name) ?? {
        key: job.phase_name,
        phaseName: job.phase_name,
        campaigns: 0,
        pending: 0,
        running: 0,
        blocked: 0,
        completed: 0,
        support: "backed" as const
      };
      const normalized = job.status.toUpperCase();
      if (normalized === "RUNNING" || normalized === "QUEUED") {
        phase.running += 1;
      } else if (normalized === "WAITING_APPROVAL" || normalized === "CREATED") {
        phase.pending += 1;
      } else if (normalized === "BLOCKED") {
        phase.blocked += 1;
      } else if (normalized === "COMPLETED" || normalized === "SKIPPED") {
        phase.completed += 1;
      }
      byPhase.set(job.phase_name, phase);
    }
    for (const phaseName of phaseNames) {
      const phase = byPhase.get(phaseName);
      if (phase) {
        phase.campaigns += 1;
      }
    }
  }
  return Array.from(byPhase.values()).sort((a, b) => a.phaseName.localeCompare(b.phaseName));
}

export function deriveReconPhaseRows(campaigns: CampaignStatusResponse[]): Array<{
  campaignId: string;
  phaseJobId: string;
  phaseName: string;
  status: string;
  approvalRequired: boolean;
  dependsOnJobId: string | null;
  workerTaskId: string | null;
}> {
  const reconHints = ["recon", "discovery", "validation", "analysis"];
  return campaigns.flatMap((campaign) =>
    campaign.phase_jobs
      .filter((job) =>
        reconHints.some((hint) => job.phase_name.toLowerCase().includes(hint))
      )
      .map((job) => ({
        campaignId: campaign.campaign.id,
        phaseJobId: job.id,
        phaseName: job.phase_name,
        status: job.status,
        approvalRequired: job.approval_required,
        dependsOnJobId: job.depends_on_job_id,
        workerTaskId: job.worker_task_id
      }))
  );
}

export function flattenRecentAuditEvents(input: {
  campaignDiagnostics: CampaignDiagnosticsResponse[];
  findingDiagnostics?: FindingDiagnosticsResponse[];
}): AuditEvent[] {
  const events = input.campaignDiagnostics.flatMap((diag) => diag.recent_audit_events);
  const findingEvents = (input.findingDiagnostics ?? []).flatMap((diag) => diag.recent_audit_events);
  return [...events, ...findingEvents].sort(
    (a, b) => parseTime(b.happened_at) - parseTime(a.happened_at)
  );
}

function matchAll(input: string, pattern: RegExp): string[] {
  const matches = input.match(new RegExp(pattern.source, pattern.flags)) ?? [];
  return Array.from(new Set(matches));
}
